import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.analyst.states import AnalystState
from app.database import get_db
from app.dependencies import get_current_user, get_storage_service
from app.models.artifact import Artifact
from app.models.dataset import Dataset
from app.models.message import Message, MessageRole
from app.models.session import Session
from app.models.user import User
from app.services.analyst import materialize_dashboard_html, save_dashboard_html
from app.services.storage import DatasetStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


def _decode_data_type(raw_data_type: str | list[str] | None) -> str | list[str]:
    if isinstance(raw_data_type, list):
        return raw_data_type
    if not raw_data_type:
        return "unknown"
    try:
        decoded = json.loads(raw_data_type)
    except (json.JSONDecodeError, TypeError):
        return raw_data_type

    return decoded if isinstance(decoded, (str, list)) else raw_data_type


def _resolve_dataset_path(storage_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (storage_root.parent / path).resolve()


def _to_graph_message(message: Message):
    role = getattr(message.role, "value", message.role)
    if role == MessageRole.USER.value:
        return HumanMessage(content=message.content)
    if role == MessageRole.ASSISTANT.value:
        return AIMessage(content=message.content)
    return SystemMessage(content=message.content)


def _extract_final_message(final_state: dict) -> str:
    messages = final_state.get("messages", [])
    if not messages:
        raise RuntimeError("Analyst graph returned no messages")

    last_message = messages[-1]
    if not isinstance(last_message, AIMessage):
        raise RuntimeError("Analyst graph did not end with an assistant message")
    if getattr(last_message, "tool_calls", []):
        raise RuntimeError("Analyst graph ended with unresolved tool calls")

    content = str(last_message.content or "").strip()
    if not content:
        raise RuntimeError("Analyst graph returned an empty assistant message")

    return content


async def _load_latest_artifact(
    db: AsyncSession,
    session_id: UUID,
) -> Artifact | None:
    statement = (
        select(Artifact)
        .where(Artifact.session_id == session_id)
        .order_by(Artifact.iteration.desc())
    )
    result = await db.exec(statement)
    artifacts = result.all()
    return artifacts[0] if artifacts else None


async def _persist_chat_turn(
    db: AsyncSession,
    *,
    session_id: UUID,
    question: str,
    final_message: str,
    artifact_action: str | None,
    latest_artifact_id: UUID | None,
    latest_artifact_iteration: int,
    final_state: dict,
    dashboard_path: Path | None,
) -> None:
    """Persist the clean turn and any artifact update in one database transaction."""
    message_statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence.desc())
    )
    message_result = await db.exec(message_statement)
    latest_message = message_result.first()
    next_sequence = (latest_message.sequence if latest_message else 0) + 1

    db.add(
        Message(
            session_id=session_id,
            sequence=next_sequence,
            role=MessageRole.USER,
            content=question,
        )
    )
    db.add(
        Message(
            session_id=session_id,
            sequence=next_sequence + 1,
            role=MessageRole.ASSISTANT,
            content=final_message,
        )
    )

    if artifact_action == "analysis":
        db.add(
            Artifact(
                session_id=session_id,
                iteration=latest_artifact_iteration + 1,
                hypotheses_evidence_json=final_state.get("hypotheses_evidence"),
                narrative_json=final_state.get("narrative"),
                dashboard_path=str(dashboard_path) if dashboard_path else None,
            )
        )
    elif artifact_action == "dashboard_edit":
        if latest_artifact_id is None:
            raise RuntimeError("Dashboard edit completed without an existing artifact")
        if dashboard_path:
            await db.exec(
                update(Artifact)
                .where(Artifact.id == latest_artifact_id)
                .values(dashboard_path=str(dashboard_path))
            )

    await db.commit()


@router.post("/{session_id}/chat")
async def chat(
    session_id: UUID,
    payload: ChatRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage_service: Annotated[DatasetStorageService, Depends(get_storage_service)],
):
    question = payload.message.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be blank",
        )

    # Check if session matches with the current user
    ownership_statement = (
        select(Session, Dataset)
        .join(Dataset, Dataset.id == Session.dataset_id)
        .where(
            Session.id == session_id,
            Dataset.user_id == current_user.id,
        )
    )
    ownership_result = await db.exec(ownership_statement)
    session_context = ownership_result.one_or_none()
    if session_context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session, dataset = session_context

    # Obtain the previous message from DB to enrich the graph
    message_statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence)
    )
    message_result = await db.exec(message_statement)
    stored_messages = message_result.all()

    # Obtain the latest artifact for the session to enrich the graph
    latest_artifact = await _load_latest_artifact(db, session_id)
    latest_artifact_id = latest_artifact.id if latest_artifact else None
    latest_artifact_iteration = latest_artifact.iteration if latest_artifact else 0

    storage_root = storage_service.storage_root.resolve()
    session_dir = storage_root / "sessions" / str(session_id)
    figures_dir = session_dir / "figures"
    await asyncio.to_thread(figures_dir.mkdir, parents=True, exist_ok=True)

    dashboard_path = latest_artifact.dashboard_path if latest_artifact else None
    settings = request.app.state.settings

    initial_state = AnalystState(
        dataset_path=str(_resolve_dataset_path(storage_root, dataset.storage_path)),
        figures_dir=str(figures_dir),
        messages=[
            *[_to_graph_message(message) for message in stored_messages],
            HumanMessage(content=question),
        ],
        profile={"data_type": _decode_data_type(dataset.data_type)},
        hypotheses_evidence=(
            latest_artifact.hypotheses_evidence_json if latest_artifact else None
        ),
        narrative=latest_artifact.narrative_json if latest_artifact else None,
        dashboard_path=dashboard_path,
        dashboard_html=None,
        critic_score=None,
        critic_feedback=None,
        iteration_count=0,
        artifact_action=None,
        llm_calls=0,
        max_llm_calls=getattr(settings, "max_analyst_llm_calls", 50),
    )

    # Do not hold a database transaction/connection while the graph calls the LLM.
    await db.rollback()

    try:
        final_state = await request.app.state.analyst_graph.ainvoke(initial_state)
        final_message = _extract_final_message(final_state)

        persisted_dashboard_path = None
        materialized_dashboard = None
        dashboard_html = final_state.get("dashboard_html")
        if dashboard_html is not None:
            if not isinstance(dashboard_html, str):
                raise RuntimeError("Analyst graph returned invalid dashboard HTML")

            persisted_dashboard_path = await save_dashboard_html(
                session_id,
                dashboard_html,
                storage_root,
            )
            persisted_html = await asyncio.to_thread(
                persisted_dashboard_path.read_text,
                encoding="utf-8",
            )
            materialized_dashboard = await asyncio.to_thread(
                materialize_dashboard_html,
                persisted_html,
                figures_dir,
            )

        await _persist_chat_turn(
            db,
            session_id=session_id,
            question=question,
            final_message=final_message,
            artifact_action=final_state.get("artifact_action"),
            latest_artifact_id=latest_artifact_id,
            latest_artifact_iteration=latest_artifact_iteration,
            final_state=final_state,
            dashboard_path=persisted_dashboard_path,
        )
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        reference_id = uuid4()
        logger.exception("Analyst graph failed reference_id=%s", reference_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed. Reference ID: {reference_id}",
        ) from exc

    return {
        "message": {"role": MessageRole.ASSISTANT.value, "content": final_message},
        "dashboard_html": materialized_dashboard,
    }

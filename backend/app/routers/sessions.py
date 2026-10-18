from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_storage_service
from app.models.message import MessageRole
from app.models.user import User
from app.services.chat import run_chat_turn
from app.services.exceptions import AnalysisFailedError, SessionNotFoundError
from app.services.sessions import get_session_detail
from app.services.storage import DatasetStorageService

router = APIRouter(prefix="/sessions", tags=["sessions"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage_service: Annotated[DatasetStorageService, Depends(get_storage_service)],
):
    try:
        detail = await get_session_detail(
            db,
            session_id=session_id,
            user_id=current_user.id,
            storage_root=storage_service.storage_root,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from exc

    return {
        "session_id": str(detail.session.id),
        "dataset_id": str(detail.session.dataset_id),
        "created_at": detail.session.created_at,
        "updated_at": detail.session.updated_at,
        "messages": [
            {
                "id": str(message.id),
                "role": message.role.value,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in detail.messages
        ],
        "dashboard_html": detail.dashboard_html,
    }


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

    try:
        turn = await run_chat_turn(
            db,
            session_id=session_id,
            user_id=current_user.id,
            question=question,
            graph=request.app.state.analyst_graph,
            max_analyst_llm_calls=request.app.state.settings.max_analyst_llm_calls,
            storage_root=storage_service.storage_root,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        ) from exc
    except AnalysisFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed. Reference ID: {exc.reference_id}",
        ) from exc

    return {
        "message": {"role": MessageRole.ASSISTANT.value, "content": turn.final_message},
        "dashboard_html": turn.dashboard_html,
    }

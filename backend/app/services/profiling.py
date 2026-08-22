import json
import logging
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from app.agents.profiler.states import ProfilerState
from app.database import AsyncSessionLocal
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)


async def run_profiler_graph(
    storage_path: str,
    graph: CompiledStateGraph,
    max_llm_calls: int,
) -> dict:
    initial_state = ProfilerState(
        storage_path=storage_path,
        llm_calls=0,
        max_llm_calls=max_llm_calls,
        messages=[HumanMessage(content=f"Path to my uploaded data: '{storage_path}'")],
    )
    final_state = await graph.ainvoke(initial_state)
    last_message = final_state["messages"][-1]
    return json.loads(last_message.content)


async def update_dataset_profile(
    dataset_id: UUID,
    storage_path: str,
    graph: CompiledStateGraph,
    max_llm_calls: int,
) -> None:
    """Run the profiler and persist data_type on the Dataset row.

    Exceptions are swallowed and logged so that upload is not affected.
    """
    try:
        profile = await run_profiler_graph(storage_path, graph, max_llm_calls)
    except Exception:
        logger.exception("Profiling failed for dataset %s", dataset_id)
        return

    async with AsyncSessionLocal() as session:
        try:
            dataset = await session.get(Dataset, dataset_id)
            if dataset is None:
                logger.warning("Dataset %s not found for profiling update", dataset_id)
                return

            data_type = profile.get("data_type")
            dataset.data_type = (
                json.dumps(data_type) if isinstance(data_type, list) else data_type
            )
            await session.commit()
        except Exception:
            logger.exception("Failed to update dataset %s profile", dataset_id)

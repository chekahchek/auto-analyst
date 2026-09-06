import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from langchain_openai import ChatOpenAI
from app.config import Settings
from app.agents.profiler.nodes import build_profiler_graph
from app.services.profiling import run_profiler_graph

# logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.basicConfig(handlers=[logging.NullHandler()], force=True)
logger = logging.getLogger(__name__)

SKILLS_DIR = BACKEND_DIR.parent / "skills"
settings = Settings.from_ini()

async def call_api(prompt, options, context):
    raw_storage_path = context["vars"]["storage_path"]
    storage_path = (
        Path(raw_storage_path)
        if Path(raw_storage_path).is_absolute()
        else BACKEND_DIR / raw_storage_path
    )
    model_name = context["vars"].get("model", "kimi-k2.5")

    logger.info("storage_path=%s model=%s", storage_path, model_name)
    if not storage_path.exists():
        logger.error("storage_path does not exist: %s", storage_path)
        return {"output": json.dumps({"error": f"storage_path not found: {storage_path}"})}

    model = ChatOpenAI(
            model=model_name,
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            reasoning_effort=settings.reasoning_effort or None,
        )

    compiled_graph = build_profiler_graph(SKILLS_DIR, model)

    try:
        result = await run_profiler_graph(
            storage_path=str(storage_path),
            graph=compiled_graph,
            max_llm_calls=10,
        )
    except Exception as exc:
        logger.error("run_profiler_graph failed: %s", exc)
        logger.debug(traceback.format_exc())
        return {"output": json.dumps({"error": str(exc), "traceback": traceback.format_exc()})}

    logger.info("profiler result=%s", result)
    return {"output": json.dumps(result)}


def call_api_sync(prompt, options, context):
    return asyncio.run(call_api(prompt, options, context))
from typing import Annotated, Sequence, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ProfilerState(TypedDict):
    storage_path: str
    llm_calls: int
    max_llm_calls: int
    messages: Annotated[Sequence[BaseMessage], add_messages]

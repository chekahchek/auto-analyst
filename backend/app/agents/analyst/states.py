from typing import Annotated, Literal, Sequence, TypedDict, Union

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DatasetProfile(TypedDict):
    data_type: str | list[str]


class EvidenceChart(TypedDict):
    title: str
    insight_index: int
    description: str
    figure: dict


class HypothesesEvidence(TypedDict):
    insights: list[str]
    charts: list[EvidenceChart]


class TextContent(TypedDict):
    type: Literal["text"]
    content: str


class ChartRef(TypedDict):
    type: Literal["chart"]
    chart_index: int


ContentItem = Union[TextContent, ChartRef]


class Slide(TypedDict):
    slide_number: int
    title: str
    contents: list[ContentItem]


class NarrativeChart(TypedDict):
    title: str
    description: str
    figure: dict


class Narrative(TypedDict):
    central_question: str
    slides: list[Slide]
    charts: list[NarrativeChart]


# hypotheses_evidence, narrative, dashboard_html are not stored as array even though user can have
# multiple artifacts. This is because for follow-up convo, we append them to the system prompt
# and the state here is used for langgraph invocation only.
class AnalystState(TypedDict):
    dataset_path: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    profile: DatasetProfile
    hypotheses_evidence: HypothesesEvidence | None
    narrative: Narrative | None
    dashboard_path: str | None
    dashboard_html: str | None
    critic_score: float | None
    critic_feedback: str | None
    iteration_count: int
    llm_calls: int
    max_llm_calls: int

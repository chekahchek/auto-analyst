from deepeval.models import DeepEvalBaseLLM
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel


class JudgeModel(DeepEvalBaseLLM):
    """Adapts the app's chat model to DeepEval's judge interface.

    Returns plain text and lets DeepEval extract the JSON itself, so no
    ``response_format`` is sent: the DeepSeek endpoint rejects json_schema.
    """

    def __init__(self, chat_model: BaseChatModel, model_name: str) -> None:
        self._chat_model = chat_model
        self._model_name = model_name
        super().__init__(model=model_name)

    def load_model(self) -> BaseChatModel:
        return self._chat_model

    def get_model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> str:
        return self._chat_model.invoke(prompt).text

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> str:
        return (await self._chat_model.ainvoke(prompt)).text

"""Chat model that round-trips DeepSeek-style ``reasoning_content``.

Thinking models return ``reasoning_content`` with every reply and reject a
follow-up request unless it is sent back on the assistant message. langchain-openai
drops that non-standard field, so this subclass copies it onto the AIMessage and
re-attaches it when the message history is sent.
"""

from typing import Any

import openai
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI

REASONING_KEY = "reasoning_content"


class ChatOpenAIWithReasoning(ChatOpenAI):
    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        if not isinstance(response, openai.BaseModel):
            return result

        for generation, choice in zip(result.generations, response.choices):
            reasoning = getattr(choice.message, REASONING_KEY, None)
            if reasoning is not None:
                generation.message.additional_kwargs[REASONING_KEY] = reasoning
        return result

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "messages" not in payload:
            return payload

        messages = self._convert_input(input_).to_messages()
        for message_dict, message in zip(payload["messages"], messages, strict=True):
            if (
                isinstance(message, AIMessage)
                and REASONING_KEY in message.additional_kwargs
            ):
                message_dict[REASONING_KEY] = message.additional_kwargs[REASONING_KEY]
        return payload

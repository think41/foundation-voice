from loguru import logger
from typing import List, Optional
from dataclasses import dataclass

from openai.types.chat import ChatCompletionMessageParam

from pipecat.frames.frames import Frame
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext


class AgentChatContext:
    """
    An agent chat context to keep track of the agent and the messages
    """

    def __init__(
        self,
        agent: str | None = None,
        messages: Optional[List[ChatCompletionMessageParam]] | None = None,
        context=None,
    ):
        self._agent = agent
        self._messages = messages if messages is not None else []
        self._context = context

    @staticmethod
    def upgrade_to_agent(obj: OpenAILLMContext):
        if isinstance(obj, OpenAILLMContext) and not isinstance(obj):
            logger.debug(f"Upgrading OpenAILLMContext to AgentChatContext: {obj}")
            obj.__class__ = AgentChatContext
            obj._restructure_from_openai_messages()
        return obj

    @staticmethod
    def from_messages(messages: List[dict]) -> "AgentChatContext":
        context = AgentChatContext()

        for message in messages:
            context.add_message(message)
        return context

    @property
    def messages(self) -> List[ChatCompletionMessageParam]:
        return self._messages

    @property
    def agent(self) -> str | None:
        return self._agent

    @property
    def context(self):
        return self._context

    @agent.setter
    def agent(self, agent: str):
        self._agent = agent

    def add_message(self, message: ChatCompletionMessageParam):
        self._messages.append(message)

    def add_messages(self, messages: List[ChatCompletionMessageParam]):
        self._messages.extend(messages)

    def set_messages(self, messages: List[ChatCompletionMessageParam]):
        self._messages[:] = messages

    def get_messages(self) -> List[ChatCompletionMessageParam]:
        return self._messages

    def _restructure_from_openai_messages(self):
        self._messages = [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in self._context.messages
        ]


@dataclass
class AgentChatContextFrame(Frame):
    context: AgentChatContext

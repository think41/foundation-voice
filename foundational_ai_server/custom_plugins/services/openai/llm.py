from typing import List
from dataclasses import dataclass
from pipecat.services.openai.llm import (
    OpenAILLMService as _OriginalOpenAILLMService, 
    OpenAIUserContextAggregator as _OriginalUserContextAggregator, 
    OpenAIAssistantContextAggregator
)
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantAggregatorParams,
    LLMUserAggregatorParams,
)
from openai.types.chat import ChatCompletionMessageParam
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

class OpenAIUserContextAggregator(_OriginalUserContextAggregator):
    def get_messages(self) -> List[ChatCompletionMessageParam]:
        return self._context.get_messages()


@dataclass
class OpenAIContextAggregatorPair:
    _user: OpenAIUserContextAggregator
    _assistant: OpenAIAssistantContextAggregator

    def user(self) -> OpenAIUserContextAggregator:
        return self._user

    def assistant(self) -> OpenAIAssistantContextAggregator:
        return self._assistant


class OpenAILLMService(_OriginalOpenAILLMService):
    def create_context_aggregator(
        self,
        context: OpenAILLMContext,
        *,
        user_params: LLMUserAggregatorParams = LLMUserAggregatorParams(),
        assistant_params: LLMAssistantAggregatorParams = LLMAssistantAggregatorParams(),
    ) -> OpenAIContextAggregatorPair:
        context.set_llm_adapter(self.get_llm_adapter())
        user = OpenAIUserContextAggregator(context, params=user_params)
        assistant = OpenAIAssistantContextAggregator(context, params=assistant_params)
        return OpenAIContextAggregatorPair(_user=user, _assistant=assistant)
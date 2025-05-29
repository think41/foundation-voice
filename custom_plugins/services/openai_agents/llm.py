from typing import Optional
from dataclasses import dataclass

from pipecat.services.llm_service import LLMService
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMMessagesFrame,
    EndFrame,
    ErrorFrame,
    TTSSpeakFrame 
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantContextAggregator,
    LLMUserContextAggregator,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
from pipecat.processors.aggregators.openai_llm_context import (
    OpenAILLMContextFrame,
)

from openai.types.chat import ChatCompletionMessageParam

from custom_plugins.services.openai_agents.agents_sdk.handler import AgentHandler
from custom_plugins.frames.frames import (
    ToolCallFrame,
    ToolResultFrame,
    AgentHandoffFrame,
    GuardrailTriggeredFrame,
)
from custom_plugins.processors.aggregators.agent_context import AgentChatContext, AgentChatContextFrame


# Aggregators for user and assistant context
class AgentUserContextAggregator(LLMUserContextAggregator):
    def add_message(self, message: ChatCompletionMessageParam):
        self._context.add_message(message)


class AgentAssistantContextAggregator(LLMAssistantContextAggregator):
    def add_message(self, message: ChatCompletionMessageParam):
        self._context.add_message(message)


@dataclass
class AgentContextAggregatorPair:
    """
    An agent context aggregator pair to keep track of the user and assistant context
    """

    _user: AgentUserContextAggregator
    _assistant: AgentAssistantContextAggregator

    def user(self) -> AgentUserContextAggregator:
        return self._user

    def assistant(self) -> AgentAssistantContextAggregator:
        return self._assistant


class OpenAIAgentPlugin(LLMService):
    """
    
    Custom agent plugin for OpenAI-Agents-SDK. 
    Extends the LLMService class provided by pipecat.

    Args: 
        agent_config: AgentConfig :- Configuration for the agent
        tools: dict | None :- userdefined tools for the agent
        rtvi: Optional[RTVIProcessor] :- RTVI processor for the agent
        **kwargs: :- Additional keyword arguments

    """
    def __init__(
        self,
        agent_config,
        data,
        **kwargs,
    ):
        super().__init__(**kwargs)
        
        self._rtvi = data.get("rtvi")
        self._create_agents(agent_config, data.get("context"), data.get("tools"))

    def _create_agents(self, config, context, tools):
        if not config:
            raise ValueError("Missing agent config")
        self._client = AgentHandler(config, context, tools)

    async def _process_context(self, context: AgentChatContext):
        """
        Processes the context and emits events based on the agent's response.
        Returns a streaming response
        """
        async for event in self._client.run_streamed(
            context.agent, 
            context.messages, 
            context.context
        ):

            if event.type == "error_event":
                # Push error frame when an error occurs when agent is running
                await self.push_frame(
                    ErrorFrame(event.data.text)
                )

            elif event.type == "raw_response_event":
                # Streaming response chunks. Push text frame for each chunk
                await self.push_frame(TextFrame(event.data.delta))

            elif event.type == "tool_call_item":
                # Push tool call frame when the agent makes a tool call
                await self.push_frame(
                    ToolCallFrame(
                        agent_name=event.data.agent,
                        tool_name=event.data.tool_name,
                        input=event.data.input,
                        call_id=event.data.call_id
                    )
                )
            
            elif event.type == "tool_call_output_item":
                # Push tool result frame when tool call finishes with a result
                await self.push_frame(ToolResultFrame(
                    result=event.data.tool_result,
                    call_id=event.data.call_id
                ))

            elif event.type == "agent_updated_stream_event":
                # Push a frame to display agent handoff
                await self.push_frame(AgentHandoffFrame(
                    from_agent=event.data.from_agent,
                    to_agent=event.data.to_agent
                ))
            
            elif event.type == "guardrail_triggered_event":
                await self.push_frame(TTSSpeakFrame(
                    "I am sorry, but I am not able to assist with that."
                ))
                await self.push_frame(GuardrailTriggeredFrame(
                    guardrail_name=event.data.guardrail_name,
                    is_off_topic=event.data.is_off_topic,
                    reasoning=event.data.reasoning
                ))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Handle EndFrame specially to avoid serialization issues
        if isinstance(frame, EndFrame):
            await self.push_frame(TextFrame("Session ended"))
            return

        await super().process_frame(frame, direction)

        context = None

        if isinstance(frame, OpenAILLMContextFrame):
            context = frame.context
        elif isinstance(frame, AgentChatContextFrame):
            context = frame.context
        elif isinstance(frame, LLMMessagesFrame):
            context = AgentChatContext.from_messages(frame.messages)

        if context is not None:
            await self.push_frame(LLMFullResponseStartFrame())
            await self._process_context(context)
            await self.push_frame(LLMFullResponseEndFrame())
        else:
            await self.push_frame(frame, direction)

    def create_context_aggregator(
        self,
        context: AgentChatContext,
        *,
        user_params: LLMUserAggregatorParams = LLMUserAggregatorParams(),
        assistant_params: LLMAssistantAggregatorParams = LLMAssistantAggregatorParams(),
    ) -> AgentContextAggregatorPair:
        user = AgentUserContextAggregator(context, params=user_params)
        assistant = AgentAssistantContextAggregator(user, params=assistant_params)
        return AgentContextAggregatorPair(_user=user, _assistant=assistant)

    def get_agent(self, name: str):
        return self._client.get_agent(name)

import asyncio

from loguru import logger

from typing import Any, Dict, Optional

from agents import (
    Runner,
    RunContextWrapper,
)

from openai.types.responses import ResponseTextDeltaEvent

from foundation_voice.custom_plugins.services.openai_agents.agents_sdk.agent import (
    AgentFactory,
)
from foundation_voice.custom_plugins.services.openai_agents.agents_sdk.utils.chunks import (
    create_agent_updated_chunk,
    create_error_chunk,
    create_guardrail_chunk,
    create_tool_call_chunk,
    create_tool_call_output_chunk,
)


class AgentHandler:
    def __init__(
        self,
        config,
        context: Optional[RunContextWrapper] = None,
        tools: Optional[Dict[str, Any]] = None,
    ):
        self._config = config
        self._setup(context, tools)

    def _setup(self, context, tools):
        self.agents = AgentFactory(self._config, context, tools)

    async def run_streamed(self, agent_name, messages, context=None):
        agent, guardrails = self.agents.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent {agent_name} not found")

        user_input = messages[-1].get("content")
        buffer = []
        cancel_event = asyncio.Event()

        async def stream_agent():
            try:
                async for chunk in Runner.run_streamed(
                    agent, messages, context=context
                ).stream_events():
                    if cancel_event.is_set():
                        break
                    if chunk.type == "raw_response_event" and isinstance(
                        chunk.data, ResponseTextDeltaEvent
                    ):
                        buffer.append(chunk)
                    elif chunk.type == "run_item_stream_event":
                        item = chunk.item
                        if item.type == "tool_call_item":
                            buffer.append(create_tool_call_chunk(agent.name, item))
                        elif item.type == "tool_call_output_item":
                            buffer.append(create_tool_call_output_chunk(item))
                    elif chunk.type == "agent_updated_stream_event":
                        buffer.append(create_agent_updated_chunk(agent, chunk))
            except Exception as e:
                buffer.append(create_error_chunk(e))

        agent_task = asyncio.create_task(stream_agent())

        # Guardrail evaluation only for user input
        if messages[-1].get("role") == "user" and guardrails:
            results = await asyncio.gather(
                *[
                    self._run_guardrail(gr, agent, user_input, context)
                    for gr in guardrails
                ]
            )

            for name, result in results:
                if result and result.tripwire_triggered:
                    cancel_event.set()
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    yield create_guardrail_chunk(name, result)
                    return

        # Wait for agent to finish processing
        while not agent_task.done():
            await asyncio.sleep(0.01)

        # Yield all buffered output
        for chunk in buffer:
            yield chunk

    @staticmethod
    async def _run_guardrail(guardrail, agent, user_input, context):
        try:
            result = await guardrail.guardrail_function(
                ctx=RunContextWrapper(context=context),
                agent=agent,
                input=user_input,
            )
            return (guardrail.name, result)
        except Exception as e:
            logger.error(f"Guardrail {guardrail.name} failed: {e}")
            return (guardrail.name, None)

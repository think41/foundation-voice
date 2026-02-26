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
        has_guardrails = bool(messages[-1].get("role") == "user" and guardrails)

        # Fast path: no guardrails — yield chunks immediately as they stream in
        if not has_guardrails:
            try:
                async for chunk in Runner.run_streamed(
                    agent, messages, context=context
                ).stream_events():
                    if chunk.type == "raw_response_event" and isinstance(
                        chunk.data, ResponseTextDeltaEvent
                    ):
                        yield chunk
                    elif chunk.type == "run_item_stream_event":
                        item = chunk.item
                        if item.type == "tool_call_item":
                            yield create_tool_call_chunk(agent.name, item)
                        elif item.type == "tool_call_output_item":
                            yield create_tool_call_output_chunk(item)
                    elif chunk.type == "agent_updated_stream_event":
                        yield create_agent_updated_chunk(agent, chunk)
            except Exception as e:
                yield create_error_chunk(e)
            return

        # Guardrail path: run guardrails concurrently with streaming, buffer until safe to yield
        queue = asyncio.Queue()
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
                        await queue.put(chunk)
                    elif chunk.type == "run_item_stream_event":
                        item = chunk.item
                        if item.type == "tool_call_item":
                            await queue.put(create_tool_call_chunk(agent.name, item))
                        elif item.type == "tool_call_output_item":
                            await queue.put(create_tool_call_output_chunk(item))
                    elif chunk.type == "agent_updated_stream_event":
                        await queue.put(create_agent_updated_chunk(agent, chunk))
            except Exception as e:
                await queue.put(create_error_chunk(e))
            finally:
                await queue.put(None)  # sentinel

        agent_task = asyncio.create_task(stream_agent())
        pending_guardrails = {
            asyncio.create_task(self._run_guardrail(gr, agent, user_input, context))
            for gr in guardrails
        }

        # Stream chunks immediately while guardrails run concurrently.
        # Cancel and yield guardrail chunk only if a tripwire is triggered.
        stream_done = False
        while not stream_done:
            queue_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                {queue_task} | pending_guardrails,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Check any completed guardrails for tripwires
            for gt in done & pending_guardrails:
                pending_guardrails.discard(gt)
                try:
                    name, result = gt.result()
                    if result and result.tripwire_triggered:
                        queue_task.cancel()
                        cancel_event.set()
                        agent_task.cancel()
                        try:
                            await agent_task
                        except asyncio.CancelledError:
                            pass
                        for remaining in pending_guardrails:
                            remaining.cancel()
                        yield create_guardrail_chunk(name, result)
                        return
                except Exception as e:
                    logger.error(f"Guardrail task error: {e}")

            # Yield chunk if queue_task completed
            if queue_task in done:
                chunk = queue_task.result()
                if chunk is None:
                    stream_done = True
                else:
                    yield chunk
            else:
                # Guardrail completed but queue not ready yet — cancel and re-loop
                queue_task.cancel()

        # Stream done — wait for any remaining guardrails
        if pending_guardrails:
            await asyncio.gather(*pending_guardrails, return_exceptions=True)

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

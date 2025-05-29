from loguru import logger

from typing import Any, Dict, List, Optional

from agents import (
    Runner,
    RunContextWrapper,
)

from openai.types.responses import ResponseTextDeltaEvent

from custom_plugins.services.openai_agents.agents_sdk.agent import AgentFactory

class AgentHandler:
    def __init__(
        self, 
        config, 
        context: Optional[RunContextWrapper] = None,
        tools: Optional[Dict[str, Any]] = None
    ):
        self._config = config
        self._setup(context, tools)

    def _setup(self, context, tools):
        self.agents = AgentFactory(self._config, context, tools)

    async def run_streamed(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        context: Optional[RunContextWrapper] = None,
    ):
        """
        Args:
            agent_name: Name of the agent to run
            messages: List of messages to send to the agent
            context: Optional context to pass to the agent
        
        Returns:
            Async generator 

        """

        agent = self.agents.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent {agent_name} not found")

        guardrails = agent.input_guardrails
        if messages[-1].get("role") == "user" and guardrails:
            context_wrapper = RunContextWrapper(context=context)
            for guardrail in guardrails:
                guardrail_func = guardrail.guardrail_function
                try:
                    guardrail_result = await guardrail_func(
                        ctx=context_wrapper,
                        agent=agent,
                        input=messages[-1].get("content"),
                    )

                    if guardrail_result.tripwire_triggered:
                        guardrail_triggered_chunk = self._get_guardrail_chunk(guardrail.name, guardrail_result)
                        yield guardrail_triggered_chunk
                        return

                except Exception as e:
                    logger.error(f"Guardrail {guardrail.name} failed: {e}")
                    continue
        
        try:
            chunks = Runner.run_streamed(agent, messages, context=context)
            async for chunk in chunks.stream_events():
                if chunk.type == "raw_response_event" and isinstance(chunk.data, ResponseTextDeltaEvent):
                    yield chunk
                elif chunk.type == "run_item_stream_event":
                    item = chunk.item
                    
                    if item.type == "tool_call_item":
                        tool_call_chunk = type(
                            "ToolCallChunk",
                            (),
                            {
                                "type": "tool_call_item",
                                "data": type("ToolCallData", (), {
                                    "agent": agent.name,
                                    "tool_name": item.raw_item.name,
                                    "input": item.raw_item.arguments,
                                    "call_id": item.raw_item.call_id
                                })
                            }
                        )
                        yield tool_call_chunk
                        
                    elif item.type == "tool_call_output_item":
                        tool_call_output_chunk = type(
                            "ToolCallOutputChunk",
                            (),
                            {
                                "type": "tool_call_output_item",
                                "data": type("ToolCallOutputData", (), {
                                    "call_id": item.raw_item["call_id"],
                                    "tool_result": item.output,
                                })
                            }
                        )
                        yield tool_call_output_chunk

                elif chunk.type == "agent_updated_stream_event":
                    if agent.name != chunk.new_agent.name:
                        
                        agent_updated_chunk = type(
                            "AgentUpdatedChunk",
                            (),
                            {
                                "type": "agent_updated_stream_event",
                                "data": type("AgentUpdatedData", (), {
                                    "from_agent": agent.name,
                                    "to_agent": chunk.new_agent.name,
                                })
                            }
                        )
                        yield agent_updated_chunk


        except Exception as e:
            error_msg = f"Error running agent. Exception: {e}"
            error_chunk = type(
                "ErrorChunk",
                (),
                {
                    "type": "error_event",
                    "data": type("ErrorData", (), {"text": error_msg}),
                },
            )
            yield error_chunk
    
    def _get_guardrail_chunk(self, guardrail_name, guardrail_result):
        return type(
            "GuardrailTriggeredChunk",
            (),
            {
                "type": "guardrail_triggered_event",
                "data": type("GuardrailTriggerData", (), {
                    "guardrail_name": guardrail_name,
                    "is_off_topic": guardrail_result.tripwire_triggered,
                    "reasoning": guardrail_result.output_info.reasoning,
                })
            }
        )
        
                        
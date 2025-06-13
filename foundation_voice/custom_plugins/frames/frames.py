from typing import Any, Dict
from dataclasses import dataclass

from pipecat.frames.frames import DataFrame


# Custom defined frame for start of a tool call
@dataclass
class ToolCallFrame(DataFrame):
    agent_name: str
    tool_name: str
    input: Dict[str, Any]
    call_id: str

    def __str__(self):
        return f"ToolCallFrame(agent={self.agent_name}, tool={self.tool_name}, input={self.input})"


# Custom defined frame for the result of a tool call
@dataclass
class ToolResultFrame(DataFrame):
    result: str
    call_id: str

    def __str__(self):
        return f"ToolResultFrame(result={self.result})"


# Custom defined frame for agent handoff
@dataclass
class AgentHandoffFrame(DataFrame):
    from_agent: str
    to_agent: str

    def __str__(self):
        return (
            f"AgentHandoffFrame(from_agent={self.from_agent}, to_agent={self.to_agent})"
        )


@dataclass
class GuardrailTriggeredFrame(DataFrame):
    guardrail_name: str
    is_off_topic: bool
    reasoning: str

    def __str__(self):
        return f"GuardrailTriggeredFrame(guardrail_name={self.guardrail_name}, is_off_topic={self.is_off_topic}, reasoning={self.reasoning})"

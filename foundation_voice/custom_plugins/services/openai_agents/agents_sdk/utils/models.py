from pydantic import BaseModel
from typing import Any, Literal


class ToolCallData(BaseModel):
    agent: str
    tool_name: str
    input: Any
    call_id: str


class ToolCallChunk(BaseModel):
    type: Literal["tool_call_item"]
    data: ToolCallData


class ToolCallOutputData(BaseModel):
    tool_result: Any
    call_id: str


class ToolCallOutputChunk(BaseModel):
    type: Literal["tool_call_output_item"]
    data: ToolCallOutputData


class AgentUpdatedData(BaseModel):
    from_agent: str
    to_agent: str


class AgentUpdatedChunk(BaseModel):
    type: Literal["agent_updated_stream_event"]
    data: AgentUpdatedData


class ErrorData(BaseModel):
    text: str


class ErrorChunk(BaseModel):
    type: Literal["error_event"]
    data: ErrorData


class GuardrailTriggerData(BaseModel):
    guardrail_name: str
    is_off_topic: bool
    reasoning: str


class GuardrailTriggerChunk(BaseModel):
    type: Literal["guardrail_triggered_event"]
    data: GuardrailTriggerData

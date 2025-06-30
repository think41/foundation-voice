from .models import (
    ToolCallChunk,
    ToolCallData,
    ToolCallOutputChunk,
    ToolCallOutputData,
    ErrorChunk,
    ErrorData,
    AgentUpdatedChunk,
    AgentUpdatedData,
    GuardrailTriggerChunk,
    GuardrailTriggerData,
)


def create_tool_call_chunk(agent_name: str, item):
    return ToolCallChunk(
        type="tool_call_item",
        data=ToolCallData(
            agent=agent_name,
            tool_name=item.raw_item.name,
            input=item.raw_item.arguments,
            call_id=item.raw_item.call_id,
        ),
    )


def create_tool_call_output_chunk(item):
    return ToolCallOutputChunk(
        type="tool_call_output_item",
        data=ToolCallOutputData(
            call_id=item.raw_item["call_id"],
            tool_result=item.output,
        ),
    )


def create_error_chunk(exception):
    return ErrorChunk(
        type="error_event",
        data=ErrorData(text=f"Error running agent. Exception: {exception}"),
    )


def create_agent_updated_chunk(agent, item):
    return AgentUpdatedChunk(
        type="agent_updated_stream_event",
        data=AgentUpdatedData(
            from_agent=agent.name,
            to_agent=item.new_agent.name,
        ),
    )


def create_guardrail_chunk(name, result):
    return GuardrailTriggerChunk(
        type="guardrail_triggered_event",
        data=GuardrailTriggerData(
            guardrail_name=name,
            is_off_topic=result.tripwire_triggered,
            reasoning=result.output_info.reasoning,
        ),
    )

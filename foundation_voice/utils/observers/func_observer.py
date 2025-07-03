from collections import deque

from pipecat.processors.frameworks.rtvi import (
    RTVIProcessor,
    RTVIObserver,
    RTVIServerMessageFrame,
)
from pipecat.frames.frames import FunctionCallInProgressFrame, FunctionCallResultFrame
from pipecat.observers.base_observer import FramePushed
from ...custom_plugins.frames.frames import (
    ToolCallFrame,
    ToolResultFrame,
    AgentHandoffFrame,
    GuardrailTriggeredFrame,
)


class FunctionObserver(RTVIObserver):
    def __init__(self, rtvi: RTVIProcessor):
        super().__init__(rtvi)
        self._rtvi = rtvi
        self._frame_seen = set()
        self._queue = deque()

    async def on_push_frame(self, input_data: FramePushed):
        await super().on_push_frame(input_data)
        if input_data.frame.id in self._frame_seen:
            return
        self._frame_seen.add(input_data.frame.id)

        mark_as_seen = True

        if isinstance(input_data.frame, FunctionCallInProgressFrame):
            data = {
                "function_name": input_data.frame.function_name,
                "tool_call_id": input_data.frame.tool_call_id,
                "arguments": input_data.frame.arguments,
            }
            frame = RTVIServerMessageFrame(
                data={"type": "function_call_in_progress", "payload": data}
            )
            await self._rtvi.push_frame(frame)

        elif isinstance(input_data.frame, FunctionCallResultFrame):
            data = {
                "function_name": input_data.frame.function_name,
                "tool_call_id": input_data.frame.tool_call_id,
                "arguments": input_data.frame.arguments,
                "result": input_data.frame.result,
            }

            frame = RTVIServerMessageFrame(
                data={"type": "function_call_result", "payload": data}
            )

            await self._rtvi.push_frame(frame)

        elif isinstance(input_data.frame, ToolCallFrame):
            data = {
                "function_name": input_data.frame.tool_name,
                "tool_call_id": input_data.frame.call_id,
                "arguments": input_data.frame.input,
            }
            self._queue.append(data)
            frame = RTVIServerMessageFrame(data={"type": "tool_call", "payload": data})
            await self._rtvi.push_frame(frame)

        elif isinstance(input_data.frame, ToolResultFrame):
            agent_tool_call = self._queue.popleft()

            if agent_tool_call and (
                agent_tool_call["tool_call_id"] == input_data.frame.call_id
            ):
                data = {
                    "function_name": agent_tool_call["function_name"],
                    "tool_call_id": agent_tool_call["tool_call_id"],
                    "arguments": agent_tool_call["arguments"],
                    "result": input_data.frame.result,
                }
                frame = RTVIServerMessageFrame(
                    data={"type": "llm-tool-result", "payload": data}
                )
                await self._rtvi.push_frame(frame)

        elif isinstance(input_data.frame, AgentHandoffFrame):
            data = {
                "from_agent": input_data.frame.from_agent,
                "to_agent": input_data.frame.to_agent,
            }
            frame = RTVIServerMessageFrame(
                data={"type": "agent_handoff", "payload": data}
            )
            await self._rtvi.push_frame(frame)

        elif isinstance(input_data.frame, GuardrailTriggeredFrame):
            data = {
                "guardrail_name": input_data.frame.guardrail_name,
                "is_off_topic": input_data.frame.is_off_topic,
            }
            frame = RTVIServerMessageFrame(
                data={"type": "guardrail_triggered", "payload": data}
            )
            await self._rtvi.push_frame(frame)

        if mark_as_seen:
            self._frame_seen.add(input_data.frame.id)

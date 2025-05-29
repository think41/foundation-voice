from collections import deque

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIObserver, RTVIServerMessageFrame
from pipecat.frames.frames import FunctionCallInProgressFrame, FunctionCallResultFrame, FunctionCallResultFrame
from pipecat.frames.frames import Frame

from custom_plugins.frames.frames import ToolCallFrame, ToolResultFrame


class FunctionObserver(RTVIObserver):
    def __init__(
        self, 
        llm,
        rtvi: RTVIProcessor
    ):
        super().__init__(rtvi)
        self._llm = llm
        self._rtvi = rtvi 
        self._frame_seen = set()
        self._queue = deque()

    async def on_push_frame(
        self,
        src: FrameProcessor,
        dst: FrameProcessor,
        frame: Frame,
        direction: FrameDirection,
        timestamp: int,
    ):
        await super().on_push_frame(src, dst, frame, direction, timestamp)
        if frame.id in self._frame_seen:
            return
        self._frame_seen.add(frame.id)

        mark_as_seen = True

        if isinstance(frame, FunctionCallInProgressFrame):
            data = {
                "function_name": frame.function_name,
                "tool_call_id": frame.tool_call_id,
                "arguments": frame.arguments,
            }
            frame = RTVIServerMessageFrame(
                data={
                    "type": "function_call_in_progress",
                    "payload": data
                }
            )
            await self._rtvi.push_frame(frame)
        
        elif isinstance(frame, FunctionCallResultFrame):
            data = {
                "function_name": frame.function_name,
                "tool_call_id": frame.tool_call_id,
                "arguments": frame.arguments,
                "result": frame.result,
            }

            frame = RTVIServerMessageFrame(
                data={
                    "type": "function_call_result",
                    "payload": data
                }
            )

            await self._rtvi.push_frame(frame)

        elif isinstance(frame, ToolCallFrame):
            data = {
                "function_name": frame.tool_name,
                "tool_call_id": frame.call_id,
                "arguments": frame.input,
            }
            self._queue.append(data)
            frame = RTVIServerMessageFrame(
                data={
                    "type": "tool_call",
                    "payload": data
                }
            )
            await self._rtvi.push_frame(frame)

        elif isinstance(frame, ToolResultFrame):
            agent_tool_call = self._queue.popleft()

            if agent_tool_call and (agent_tool_call["tool_call_id"] == frame.call_id):
                data = {
                    "function_name": agent_tool_call["function_name"],
                    "tool_call_id": agent_tool_call["tool_call_id"],
                    "arguments": agent_tool_call["arguments"],
                    "result": frame.result
                }
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "llm-tool-result",
                        "payload": data
                    }
                )
                await self._rtvi.push_frame(frame)

        if mark_as_seen:
            self._frame_seen.add(frame.id)
            
            
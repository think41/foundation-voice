import json
from typing_extensions import override

from pipecat.transports.services.livekit import (
    LiveKitTransport as _OGLiveKitTransport,
    LiveKitOutputTransport as _OGLiveKitOutputTransport,
    LiveKitTransportMessageFrame,
    LiveKitTransportMessageUrgentFrame,
)
from pipecat.frames.frames import TransportMessageFrame, TransportMessageUrgentFrame


class LiveKitOutputTransport(_OGLiveKitOutputTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override
    async def send_message(
        self, frame: TransportMessageFrame | TransportMessageUrgentFrame
    ):
        msg = frame.message
        if not isinstance(msg, str):
            msg = json.dumps(msg)

        # Store the JSON string in the frame
        frame.message = msg

        # Encode the string to bytes before sending
        encoded_msg = msg.encode()

        if isinstance(
            frame, (LiveKitTransportMessageFrame, LiveKitTransportMessageUrgentFrame)
        ):
            await self._client.send_data(encoded_msg, frame.participant_id)
        else:
            await self._client.send_data(encoded_msg)


class LiveKitTransport(_OGLiveKitTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override
    def output(self) -> LiveKitOutputTransport:
        if not self._output:
            self._output = LiveKitOutputTransport(
                self, self._client, self._params, name=self._output_name
            )
        return self._output

    async def cleanup(self):
        await self._client.cleanup()

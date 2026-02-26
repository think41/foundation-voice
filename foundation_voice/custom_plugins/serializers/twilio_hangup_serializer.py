"""
Custom Twilio serializer that handles the 'stop' event sent when
the remote party hangs up, converting it into a pipecat EndFrame
so the pipeline shuts down cleanly.
"""

import json

from loguru import logger

from pipecat.frames.frames import EndFrame, Frame
from pipecat.serializers.twilio import TwilioFrameSerializer


class TwilioHangupSerializer(TwilioFrameSerializer):
    """Extends TwilioFrameSerializer to handle remote hangup.

    When the caller hangs up, Twilio sends a 'stop' event over the
    WebSocket stream. The base serializer ignores this and returns None,
    leaving the pipeline running indefinitely. This subclass returns an
    EndFrame on 'stop' so the pipeline terminates immediately.
    """

    async def deserialize(self, data: str | bytes) -> Frame | None:
        message = json.loads(data)

        if message.get("event") == "stop":
            logger.info("Twilio 'stop' event received — caller hung up. Ending pipeline.")
            return EndFrame()

        return await super().deserialize(data)

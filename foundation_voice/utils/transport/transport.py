from typing import Optional, Union
from fastapi import WebSocket
import logging
from enum import Enum
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.serializers.protobuf import ProtobufFrameSerializer

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Enum defining all supported transport types"""

    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"
    DAILY = "daily"


class TransportFactory:
    @staticmethod
    def create_transport(
        transport_type: TransportType,
        connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
        room_url: str = None,
        token: str = None,
        bot_name: str = "AI Assistant",
    ):
        """
        Create a transport based on the specified type.
        Args:
            transport_type: Type of transport to create (must be TransportType enum)
            connection: Connection instance for websocket/webrtc
            room_url: URL for Daily.co room
            token: Authentication token
            bot_name: Name of the bot
        Returns:
            Transport instance
        Raises:
            ValueError: If required parameters are missing
        """
        if not isinstance(transport_type, TransportType):
            raise ValueError("transport_type must be a TransportType enum")

        if transport_type == TransportType.WEBSOCKET:
            if not isinstance(connection, WebSocket):
                raise ValueError(
                    "WebSocket connection required for websocket transport"
                )

            return FastAPIWebsocketTransport(
                websocket=connection,
                params=FastAPIWebsocketParams(
                    serializer=ProtobufFrameSerializer(),
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    add_wav_header=True,
                    vad_analyzer=SileroVADAnalyzer(),
                    session_timeout=60 * 3,  # 3 minutes
                ),
            )

        elif transport_type == TransportType.WEBRTC:
            if not isinstance(connection, SmallWebRTCConnection):
                raise ValueError("WebRTC connection required for webrtc transport")

            return SmallWebRTCTransport(
                webrtc_connection=connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    vad_analyzer=SileroVADAnalyzer(),
                ),
            )

        elif transport_type == TransportType.DAILY:
            if not room_url or not token:
                raise ValueError("room_url and token required for daily transport")
            logger.info(
                f"Creating Daily transport with room_url: {room_url} and token: {token}"
            )

            return DailyTransport(
                room_url=room_url,
                token=token,
                bot_name=bot_name,
                params=DailyParams(
                    audio_out_enabled=True,
                    transcription_enabled=True,
                    vad_enabled=True,
                    vad_analyzer=SileroVADAnalyzer(),
                ),
            )

        raise ValueError(f"Unknown transport type: {transport_type}")

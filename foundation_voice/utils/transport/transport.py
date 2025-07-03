from typing import Optional, Union
from fastapi import WebSocket
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from loguru import logger
from enum import Enum
from pipecat.transports.base_transport import TransportParams
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.serializers.twilio import TwilioFrameSerializer
from foundation_voice.utils.providers.vad_provider import create_vad_analyzer
import os


class TransportType(Enum):
    """Enum defining all supported transport types"""

    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"
    DAILY = "daily"
    SIP = "sip"


class TransportFactory:
    @staticmethod
    def create_transport(
        transport_type: TransportType,
        connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
        room_url: str = None,
        token: str = None,
        bot_name: str = "AI Assistant",
        **kwargs,
    ):
        """
        Create a transport based on the specified type.
        Args:
            transport_type: Type of transport to create (must be TransportType enum)
            connection: Connection instance for websocket/webrtc
            room_url: URL for Daily.co room
            token: Authentication token
            bot_name: Name of the bot
            **kwargs: Additional parameters for specific transports (e.g., sip_params, vad_config)
        Returns:
            Transport instance
        Raises:
            ValueError: If required parameters are missing
        """
        if not isinstance(transport_type, TransportType):
            raise ValueError("transport_type must be a TransportType enum")

        logger.debug(
            f"TransportFactory: Creating transport type: {transport_type.value}"
        )
        logger.debug(
            f"TransportFactory: Connection type: {type(connection).__name__ if connection else 'None'}"
        )
        logger.debug(f"TransportFactory: Additional kwargs: {list(kwargs.keys())}")

        vad_config = kwargs.get("vad_config", {})
        vad_analyzer = create_vad_analyzer(vad_config)

        if transport_type == TransportType.WEBSOCKET:
            try:
                from fastapi import WebSocket
                from pipecat.transports.network.fastapi_websocket import (
                    FastAPIWebsocketTransport,
                    FastAPIWebsocketParams,
                )
            except ImportError as e:
                logger.error(
                    "The 'fastapi' package, required for WebSocket transport, was not found. "
                    "To use this transport, please install the SDK with the 'fastapi' extra: "
                    "pip install foundation-voice[fastapi]"
                )
                # Re-raise with a clear message and original exception context
                raise ImportError(
                    "WebSocket transport dependencies not found. Install with: pip install foundation-voice[fastapi]"
                ) from e
            logger.debug("TransportFactory: Creating standard WebSocket transport")
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
                    add_wav_header=False,
                    vad_analyzer=vad_analyzer,
                    session_timeout=60 * 3,  # 3 minutes
                ),
            )

        elif transport_type == TransportType.WEBRTC:
            try:
                from pipecat.transports.network.webrtc_connection import (
                    SmallWebRTCConnection,
                )
                from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
            except ImportError as e:
                logger.error(
                    "The 'small_webrtc' package, required for WebRTC transport, was not found. "
                    "To use this transport, please install the SDK with the 'small_webrtc' extra: "
                    "pip install foundation-voice[small_webrtc]"
                )
                # Re-raise with a clear message and original exception context
                raise ImportError(
                    "WebRTC transport dependencies not found. Install with: pip install foundation-voice[small_webrtc]"
                ) from e
            logger.debug("TransportFactory: Creating WebRTC transport")
            if not isinstance(connection, SmallWebRTCConnection):
                raise ValueError("WebRTC connection required for webrtc transport")

            return SmallWebRTCTransport(
                webrtc_connection=connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    vad_analyzer=vad_analyzer,
                ),
            )

        elif transport_type == TransportType.DAILY:
            logger.debug("TransportFactory: Creating Daily transport")
            try:
                from pipecat.transports.services.daily import (
                    DailyTransport,
                    DailyParams,
                )
            except ImportError as e:
                logger.error(
                    "The 'daily' package, required for Daily transport, was not found. "
                    "To use this transport, please install the SDK with the 'daily' extra: "
                    "pip install foundation-voice[daily]"
                )
                # Re-raise with a clear message and original exception context
                raise ImportError(
                    "Daily transport dependencies not found. Install with: pip install foundation-voice[daily]"
                ) from e

            if not room_url or not token:
                raise ValueError("room_url and token required for daily transport")
            logger.debug(
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
                    vad_analyzer=vad_analyzer,
                ),
            )

        elif transport_type == TransportType.SIP:
            try:
                from fastapi import WebSocket
                from pipecat.transports.network.fastapi_websocket import (
                    FastAPIWebsocketTransport,
                    FastAPIWebsocketParams,
                )
            except ImportError as e:
                logger.error(
                    "The 'fastapi' package, required for WebSocket transport, was not found. "
                    "To use this transport, please install the SDK with the 'fastapi' extra: "
                    "pip install foundation-voice[fastapi]"
                )
                # Re-raise with a clear message and original exception context
                raise ImportError(
                    "WebSocket transport dependencies not found. Install with: pip install foundation-voice[fastapi]"
                ) from e
            logger.debug("TransportFactory: Creating standard WebSocket transport")

            logger.debug(
                "TransportFactory: Creating SIP transport with Twilio serializer"
            )
            if not isinstance(connection, WebSocket):
                raise ValueError("WebSocket connection required for SIP transport")

            sip_params = kwargs.get("sip_params", {})
            stream_sid = sip_params.get("stream_sid")
            call_sid = sip_params.get("call_sid")

            logger.debug(
                f"TransportFactory: SIP params - stream_sid: {stream_sid}, call_sid: {call_sid}"
            )

            if not stream_sid or not call_sid:
                raise ValueError(
                    "stream_sid and call_sid are required for SIP transport"
                )

            serializer = TwilioFrameSerializer(
                stream_sid=stream_sid,
                call_sid=call_sid,
                account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                params=TwilioFrameSerializer.InputParams(
                    auto_hang_up=kwargs.get("auto_hang_up", True),
                ),
            )

            logger.debug(
                "TransportFactory: Created Twilio serializer, building SIP transport"
            )

            # SIP transport configuration optimized for Twilio
            return FastAPIWebsocketTransport(
                websocket=connection,
                params=FastAPIWebsocketParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    add_wav_header=False,  # Twilio doesn't need WAV headers
                    vad_enabled=True,
                    vad_analyzer=vad_analyzer,
                    vad_audio_passthrough=True,  # Important for Twilio
                    serializer=serializer,
                    # No session_timeout for SIP - Twilio manages the session
                ),
            )

        raise ValueError(f"Unknown transport type: {transport_type}")

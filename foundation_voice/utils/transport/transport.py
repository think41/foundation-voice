import os

from enum import Enum
from loguru import logger
from fastapi import WebSocket
from typing import Optional, Union, Dict, Any

from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter

from foundation_voice.utils.providers.vad_provider import create_vad_analyzer


class TransportType(Enum):
    """Enum defining all supported transport types"""


    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"
    DAILY = "daily"
    SIP = "sip"
    LIVEKIT = "livekit"
    LIVEKIT_SIP = "livekit_sip"


def get_fastapi_websocket_transport(
    connection,
    serializer: ProtobufFrameSerializer | TwilioFrameSerializer,
    vad_analyzer,
    extra_params: Dict[str, Any] = None,
):
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

    if not isinstance(connection, WebSocket):
        raise ValueError("WebSocket connection required for websocket transport")

    return FastAPIWebsocketTransport(
        websocket=connection,
        params=FastAPIWebsocketParams(
            serializer=serializer,
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_filter=NoisereduceFilter(),
            add_wav_header=False,
            vad_analyzer=vad_analyzer,
            **(extra_params or {}),
        ),
    )



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
            logger.debug("TransportFactory: Creating standard WebSocket transport")

            transport = get_fastapi_websocket_transport(
                connection=connection,
                serializer=ProtobufFrameSerializer(),
                vad_analyzer=vad_analyzer,
                extra_params={"session_timeout": 60 * 3},
            )

            return transport

        elif transport_type == TransportType.WEBRTC:
            try:
                from pipecat.transports.network.webrtc_connection import (
                    SmallWebRTCConnection,
                )
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
                    audio_in_filter=NoisereduceFilter(),
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
                    audio_in_filter=NoisereduceFilter(),
                ),
            )

        elif transport_type == TransportType.SIP:
            logger.debug(
                "TransportFactory: Creating SIP transport with Twilio serializer"
            )

            sip_params = kwargs.get("sip_params", {})
            stream_sid = sip_params.get("stream_sid")
            call_sid = sip_params.get("call_sid")

            logger.debug(
                f"TransportFactory: SIP params - stream_sid: {stream_sid}, call_sid: {call_sid}"
            )
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

            transport = get_fastapi_websocket_transport(
                connection=connection,
                serializer=serializer,
                vad_analyzer=vad_analyzer,
                extra_params={
                    "vad_enabled": True,
                    "vad_audio_passthrough": True,
                },
            )

            # SIP transport configuration optimized for Twilio
            return transport

        elif transport_type == TransportType.LIVEKIT | TransportType.LIVEKIT_SIP:
            logger.debug("Creating LiveKit transport")
            try:
                from pipecat.transports.services.livekit import LiveKitParams
                from foundation_voice.utils.transport.livekit_transport import (
                    LiveKitTransport,
                )
            except ImportError as e:
                logger.error(
                    "The 'livekit' package, required for LiveKit transport, was not found. "
                    "To use this transport, please install the SDK with the 'livekit' extra: "
                    "pip install foundation-voice[livekit]"
                )
                # Re-raise with a clear message and original exception context
                raise ImportError(
                    "LiveKit transport dependencies not found. Install with: pip install foundation-voice[livekit]"
                ) from e

            room_url = room_url
            agent_token = kwargs.get("agent_token")
            room_name = kwargs.get("room_name")

            logger.info(
                f"Room_URL: {room_url}, Token: {agent_token}, Room_Name: {room_name}"
            )

            if not room_url or not agent_token or not room_name:
                raise ValueError(
                    "room_url, agent_token and room_name are required for LiveKit transport"
                )

            return LiveKitTransport(
                url=room_url,
                token=agent_token,
                room_name=room_name,
                params=LiveKitParams(
                    audio_out_enabled=True,
                    transcription_enabled=True,
                    vad_enabled=True,
                    vad_analyzer=vad_analyzer,
                ),
            )

        else:
            raise ValueError(f"Unhandled transport type: {transport_type}")

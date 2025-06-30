import uuid
import aiohttp

from loguru import logger
from fastapi import WebSocket
from typing import Any, Dict, Optional, Callable

from foundation_voice.agent.run import run_agent
from foundation_voice.utils.transport.transport import TransportType
from foundation_voice.utils.transport.sip_detection import SIPDetector
from foundation_voice.utils.transport.connection_manager import (
    WebRTCOffer,
    connection_manager,
)
from foundation_voice.utils.daily_helpers import create_room


class CaiSDK:
    def __init__(
        self, agent_func: Optional[Callable] = None, agent_config: Optional[dict] = None
    ):
        self.agent_func = agent_func or run_agent
        self.agent_config = agent_config or {}

    def _ensure_metadata_and_session_id(self, kwargs: dict) -> None:
        """Ensure metadata and session_id are present in kwargs with default values."""
        kwargs.setdefault("metadata", {})
        kwargs.setdefault("session_id", str(uuid.uuid4()))

    def create_args(
        self,
        transport_type: TransportType,
        connection: Any,
        agent: Dict[str, Any],
        **kwargs,
    ):
        args = {
            "transport_type": transport_type,
            "connection": connection,
            "config": agent.get("config"),
            "callbacks": agent.get("callbacks", None),
            "tool_dict": agent.get("tool_dict", {}),
            "contexts": agent.get("contexts", {}),
        }
        return {**args, **kwargs}

    async def _auto_detect_transport(
        self, websocket: WebSocket
    ) -> tuple[TransportType, Optional[dict]]:
        """Auto-detect transport type with simplified logic"""
        query_params = dict(websocket.query_params)

        # 1. Check for explicit transport type
        explicit_transport = query_params.get("transport_type", "").lower()
        if explicit_transport in ["websocket", "webrtc", "daily"]:
            return TransportType(explicit_transport), None

        # 2. Try SIP detection (simple pattern-based approach)
        client_ip = websocket.client.host if websocket.client else "unknown"
        headers = dict(websocket.headers) if hasattr(websocket, "headers") else {}

        if SIPDetector.detect_sip_connection(client_ip, headers, query_params):
            sip_params = await SIPDetector.handle_sip_handshake(websocket)
            if sip_params:
                return TransportType.SIP, sip_params
            logger.debug("SIP detection failed, falling back to WebSocket")

        # 3. Default to WebSocket
        return TransportType.WEBSOCKET, None

    async def websocket_endpoint_with_agent(
        self, websocket: WebSocket, agent: dict, transport_type: TransportType, **kwargs
    ):
        self._ensure_metadata_and_session_id(kwargs)
        """
        Main WebSocket endpoint that automatically detects transport type.
        Users just call this - all complexity is handled internally.
        """
        try:
            # Auto-detect transport type (internal SDK logic)
            # transport_type, sip_params = await self._auto_detect_transport(websocket)

            # # Add SIP parameters if this is a SIP call
            # if sip_params:
            #     kwargs["sip_params"] = sip_params

            logger.debug(f"Auto-detected transport: {transport_type.value}")

            args = self.create_args(
                transport_type=transport_type,
                connection=websocket,
                agent=agent,
                **kwargs,
            )

            await self.agent_func(
                **args,
            )
        except Exception as e:
            logger.error(f"Error in websocket_endpoint_with_agent: {e}")
            raise

    async def webrtc_endpoint(self, offer: WebRTCOffer, agent: dict, **kwargs):
        self._ensure_metadata_and_session_id(kwargs)

        answer, connection = await connection_manager.handle_webrtc_connection(offer)
        args = self.create_args(
            transport_type=TransportType.WEBRTC,
            connection=connection,
            agent=agent,
            **kwargs,
        )
        response = {
            "answer": answer,
            "background_task_args": {
                "func": run_agent,
                **args,
            },
        }
        return response

    async def connect_handler(self, request: dict, agent: dict, **kwargs):
        self._ensure_metadata_and_session_id(kwargs)

        try:
            transport_type_str = request.get("transportType", "").lower
            # Convert string to TransportType enum
            try:
                transport_type = TransportType(transport_type_str)
            except ValueError:
                return {"error": f"Unsupported transport type: {transport_type_str}"}

            if transport_type == TransportType.WEBSOCKET:
                return {
                    "session_id": kwargs["session_id"],
                    "websocket_url": f"/ws?session_id={kwargs['session_id']}&agent_name={request.get('agent_name')}",
                }

            elif transport_type == TransportType.WEBRTC:
                # Check if this is a WebRTC offer
                if "sdp" in request and "type" in request:
                    # Handle WebRTC offer
                    offer = WebRTCOffer(
                        sdp=request["sdp"],
                        type=request["type"],
                        session_id=request.get("session_id"),
                        restart_pc=request.get("restart_pc", False),
                        agent_name=request.get("agent_name"),
                    )

                    await self.webrtc_endpoint(offer, agent, **kwargs)
                else:
                    # Return WebRTC UI details
                    return {
                        "offer_url": "/api/connect",  # Use same endpoint for offers
                        "webrtc_ui_url": "/webrtc",
                    }

            elif transport_type == TransportType.DAILY:
                # Create a new room if not provided
                room_url = request.get("room_url")
                if not room_url:
                    room_url, _ = create_room()

                async with aiohttp.ClientSession() as session:
                    url, token = await connection_manager.handle_daily_connection(
                        session, room_url
                    )
                    kwargs.update(
                        {
                            "room_url": url,
                            "token": token,
                        }
                    )
                    args = self.create_args(
                        transport_type=transport_type,
                        connection=url,
                        agent=agent,
                        **kwargs,
                    )
                    logger.info(f"Connect handler called with kwargs: {kwargs}")
                    return {
                        "room_url": url,
                        "token": token,
                        "background_task_args": {
                            "func": run_agent,
                            **args,
                        },
                    }

            else:
                return {"error": f"Unsupported transport type: {transport_type_str}"}

        except Exception as e:
            return {"error": f"Failed to establish connection: {str(e)}"}

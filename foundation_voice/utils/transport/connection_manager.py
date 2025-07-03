from typing import Dict, Tuple, Optional
from loguru import logger
import os
import aiohttp
from pydantic import BaseModel
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from ..daily_helpers import get_token


class WebRTCOffer(BaseModel):
    sdp: str
    type: str
    session_id: Optional[str] = None
    pc_id: Optional[str] = None
    restart_pc: bool = False
    agent_name: Optional[str] = None


class ConnectionManager:
    def __init__(self):
        self.pcs_map: Dict[str, SmallWebRTCConnection] = {}

    async def handle_webrtc_connection(
        self, request: WebRTCOffer
    ) -> Tuple[dict, SmallWebRTCConnection]:
        """Handle WebRTC connection creation or renegotiation."""
        if request.pc_id and request.pc_id in self.pcs_map:
            connection = self.pcs_map[request.pc_id]
            logger.info(f"Reusing existing connection for pc_id: {request.pc_id}")
            await connection.renegotiate(
                sdp=request.sdp,
                type=request.type,
                restart_pc=request.restart_pc,
            )
        else:
            connection = SmallWebRTCConnection(
                ice_servers=["stun:stun.l.google.com:19302"]
            )
            await connection.initialize(sdp=request.sdp, type=request.type)

        answer = connection.get_answer()
        self.pcs_map[answer["pc_id"]] = connection
        return answer, connection

    async def handle_daily_connection(
        self, session: aiohttp.ClientSession, room_url: Optional[str] = None
    ) -> tuple[str, str]:
        """Handle Daily.co connection setup."""
        if not room_url:
            raise ValueError("Room URL is required for Daily.co connection")

        api_key = os.getenv("DAILY_API_KEY")
        if not api_key:
            raise ValueError(
                "No Daily API key specified. Set DAILY_API_KEY in your environment."
            )

        # Get token using our helper function
        token = get_token(room_url)
        return room_url, token


# Create global instance
connection_manager = ConnectionManager()

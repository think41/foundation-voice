from typing import Dict, Tuple, Optional
from loguru import logger
import os
import aiohttp
from pydantic import BaseModel
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper


class WebRTCOffer(BaseModel):
    sdp: str
    type: str
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
        self, session: aiohttp.ClientSession
    ) -> tuple[str, str]:
        """Handle Daily.co connection setup."""
        url = os.getenv("DAILY_SAMPLE_ROOM_URL")
        api_key = os.getenv("DAILY_API_KEY")

        if not url:
            raise ValueError(
                "No Daily room URL specified. Set DAILY_SAMPLE_ROOM_URL in your environment."
            )
        if not api_key:
            raise ValueError(
                "No Daily API key specified. Set DAILY_API_KEY in your environment."
            )

        daily_rest_helper = DailyRESTHelper(
            daily_api_key=api_key,
            daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
            aiohttp_session=session,
        )

        token = await daily_rest_helper.get_token(url, expiry_time=60 * 60)
        return url, token


# Create global instance
connection_manager = ConnectionManager()

"""
Simplified SIP detection for foundation-voice SDK.
Based on actual SIP handshake patterns rather than IP detection.
"""

import json
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket
from loguru import logger


class SIPDetector:
    """Simplified SIP detection based on handshake patterns"""

    @classmethod
    def detect_sip_connection(
        cls, client_ip: str, headers: Dict[str, str], query_params: Dict[str, str]
    ) -> bool:
        """Simple SIP detection - explicit transport type or no query params (typical SIP pattern)"""
        return (
            query_params.get("transport_type") == "sip"
            or not query_params  # SIP providers typically don't send query params
        )

    @classmethod
    async def handle_sip_handshake(
        cls, websocket: WebSocket
    ) -> Optional[Dict[str, str]]:
        """Handle SIP handshake by checking for Twilio's specific message pattern"""
        try:
            # Get first message with timeout
            first_message = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            data = json.loads(first_message)

            # Check for Twilio's "connected" event with protocol field
            if data.get("event") == "connected" and "protocol" in data:
                # Get start event with call details
                start_message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=10
                )
                start_data = json.loads(start_message)

                if start_data.get("event") == "start":
                    stream_sid = start_data.get("start", {}).get("streamSid")
                    call_sid = start_data.get("start", {}).get("callSid")
                    customParameters = start_data.get("start", {}).get(
                        "customParameters"
                    )

                    if stream_sid and call_sid:
                        logger.info(
                            f"SIP handshake completed - Stream: {stream_sid}, Call: {call_sid}"
                        )
                        return {
                            "stream_sid": stream_sid,
                            "call_sid": call_sid,
                            "customParameters": customParameters,
                        }

            return None

        except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Not a SIP connection: {e}")
            return None

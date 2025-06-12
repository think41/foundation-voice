"""
Internal SIP detection and handling for foundation-voice SDK.
Users should not need to import or use this module directly.
"""

import json
import asyncio
from typing import Dict, Any, Tuple, Optional
from fastapi import WebSocket
from loguru import logger


class SIPDetector:
    """Internal SIP detection for the foundation-voice SDK"""
    
    # Default Twilio detection patterns (internal to SDK)
    AWS_IP_PREFIXES = [
        "54.", "18.", "52.", "34.", "184.", "3.", "13.", "44.", "35.", "99.",
        "168.86.", "177.71.", "103.", "185.", "208.78.", "67.213."
    ]
    
    TWILIO_USER_AGENTS = ["twilio"]
    TWILIO_HEADERS = ["x-twilio", "twilio"]
    
    @classmethod
    def detect_sip_connection(cls, client_ip: str, headers: Dict[str, str], query_params: Dict[str, str]) -> bool:
        """
        Detect if this is a SIP connection (like Twilio).
        This is internal SDK logic - users don't need to understand this.
        """
        # Explicit SIP transport type
        if query_params.get("transport_type") == "sip":
            return True
            
        # No query params usually means it's from a SIP provider
        if not query_params:
            # Check IP patterns (Twilio uses AWS infrastructure)
            is_aws_ip = any(client_ip.startswith(prefix) for prefix in cls.AWS_IP_PREFIXES)
            
            # Check User-Agent
            user_agent = headers.get("user-agent", "").lower()
            is_twilio_ua = any(pattern in user_agent for pattern in cls.TWILIO_USER_AGENTS)
            
            # Check headers
            has_twilio_headers = any(
                key.lower().startswith(prefix) 
                for key in headers.keys() 
                for prefix in cls.TWILIO_HEADERS
            )
            
            return is_aws_ip or is_twilio_ua or has_twilio_headers
        
        return False
    
    @classmethod
    async def handle_sip_handshake(cls, websocket: WebSocket) -> Optional[Dict[str, str]]:
        """
        Handle SIP handshake (like Twilio). Returns SIP parameters if successful.
        This is internal SDK logic - users don't need to understand this.
        """
        try:
            # Get first message (should be "connected" event)
            first_message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            
            # Check if it's a Twilio connected event
            try:
                parsed_msg = json.loads(first_message)
                if not (parsed_msg.get("event") == "connected" and "protocol" in parsed_msg):
                    return None  # Not a Twilio call
            except json.JSONDecodeError:
                return None  # Not JSON, not a SIP call
            
            # Get second message (should be "start" event with call details)
            call_data_str = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            call_data = json.loads(call_data_str)
            
            if call_data.get("event") != "start":
                logger.warning(f"Expected 'start' event, got: {call_data.get('event')}")
                return None
            
            # Extract SIP parameters
            start_data = call_data.get("start", {})
            stream_sid = start_data.get("streamSid")
            call_sid = start_data.get("callSid")
            
            if not stream_sid or not call_sid:
                logger.warning("Missing streamSid or callSid in SIP start event")
                return None
            
            logger.info(f"SIP handshake completed - Stream: {stream_sid}, Call: {call_sid}")
            return {"stream_sid": stream_sid, "call_sid": call_sid}
            
        except asyncio.TimeoutError:
            logger.warning("Timeout during SIP handshake")
            return None
        except Exception as e:
            logger.warning(f"SIP handshake failed: {e}")
            return None 
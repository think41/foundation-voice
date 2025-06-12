"""
SIP utilities for Twilio integration.
Handles detection, handshake, and configuration management.
"""

import json
import asyncio
from typing import Dict, Any, Tuple, Optional
from fastapi import WebSocket
from loguru import logger


class SIPConfig:
    """SIP configuration management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("sip", {})
        self.twilio = self.config.get("twilio", {})
        self.detection = self.twilio.get("detection", {})
        self.handshake = self.twilio.get("handshake", {})
        self.logging = config.get("logging", {})
    
    @property
    def aws_ip_prefixes(self) -> list:
        return self.detection.get("aws_ip_prefixes", [])
    
    @property
    def user_agent_patterns(self) -> list:
        return self.detection.get("user_agent_patterns", ["twilio"])
    
    @property
    def header_patterns(self) -> list:
        return self.detection.get("header_patterns", ["x-twilio", "twilio"])
    
    @property
    def handshake_timeout(self) -> int:
        return self.handshake.get("timeout_seconds", 30)
    
    @property
    def expected_events(self) -> list:
        return self.handshake.get("expected_events", ["connected", "start"])
    
    @property
    def enable_detection_logs(self) -> bool:
        return self.logging.get("enable_sip_detection_logs", False)
    
    @property
    def enable_handshake_logs(self) -> bool:
        return self.logging.get("enable_handshake_logs", True)


class TwilioDetector:
    """Handles Twilio call detection logic"""
    
    def __init__(self, config: SIPConfig):
        self.config = config
    
    def detect_twilio_connection(self, client_ip: str, headers: Dict[str, str]) -> bool:
        """
        Detect if the connection is likely from Twilio based on IP and headers.
        
        Args:
            client_ip: Client IP address
            headers: Request headers
            
        Returns:
            bool: True if likely a Twilio connection
        """
        if not self.config.detection.get("enabled", True):
            return False
        
        # Check for AWS IP patterns (Twilio uses AWS infrastructure)
        is_aws_ip = any(client_ip.startswith(prefix) for prefix in self.config.aws_ip_prefixes)
        
        # Check User-Agent for Twilio indicators
        user_agent = headers.get("user-agent", "").lower()
        is_twilio_ua = any(pattern in user_agent for pattern in self.config.user_agent_patterns)
        
        # Check headers for Twilio indicators
        has_twilio_headers = any(
            key.lower().startswith(prefix) 
            for key in headers.keys() 
            for prefix in self.config.header_patterns
        )
        
        is_likely_twilio = is_aws_ip or is_twilio_ua or has_twilio_headers
        
        if self.config.enable_detection_logs and is_likely_twilio:
            logger.info(f"Twilio connection detected: IP={is_aws_ip}, UA={is_twilio_ua}, Headers={has_twilio_headers}")
        
        return is_likely_twilio
    
    async def detect_from_first_message(self, websocket: WebSocket) -> Tuple[bool, Optional[str]]:
        """
        Examine the first WebSocket message to detect Twilio signature.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Tuple of (is_twilio, first_message_data)
        """
        try:
            # Wait for first message with timeout
            first_message = await asyncio.wait_for(
                websocket.receive_text(), 
                timeout=self.config.handshake_timeout
            )
            
            # Check if it looks like Twilio's "connected" event
            try:
                parsed_msg = json.loads(first_message)
                if (parsed_msg.get("event") == "connected" and 
                    "protocol" in parsed_msg and 
                    "version" in parsed_msg):
                    
                    if self.config.enable_detection_logs:
                        logger.info("Detected Twilio 'connected' event from first message")
                    
                    return True, first_message
                    
            except json.JSONDecodeError:
                # Not JSON, likely binary WebSocket data for regular transport
                pass
                
            return False, first_message
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for first message during Twilio detection")
            return False, None
        except Exception as e:
            logger.warning(f"Error examining first message for Twilio detection: {e}")
            return False, None


class TwilioHandshakeManager:
    """Handles Twilio SIP handshake process"""
    
    def __init__(self, config: SIPConfig):
        self.config = config
    
    async def perform_handshake(self, websocket: WebSocket, first_message_data: Optional[str] = None) -> Dict[str, str]:
        """
        Perform the Twilio SIP handshake process.
        
        Args:
            websocket: WebSocket connection
            first_message_data: Optional first message if already received
            
        Returns:
            Dict containing stream_sid and call_sid
            
        Raises:
            Exception: If handshake fails
        """
        try:
            if self.config.enable_handshake_logs:
                logger.info("Starting Twilio SIP handshake")
            
            # Handle first message (connected event)
            if first_message_data is None:
                first_message_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=self.config.handshake_timeout
                )
            
            if self.config.enable_handshake_logs:
                logger.debug(f"Received first message: {first_message_data}")
            
            # Get the second message (start event with call details)
            call_data_str = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=self.config.handshake_timeout
            )
            
            if self.config.enable_handshake_logs:
                logger.debug(f"Received call data: {call_data_str}")
            
            call_data = json.loads(call_data_str)
            
            # Validate the start event
            if call_data.get("event") != "start":
                raise ValueError(f"Expected 'start' event, got: {call_data.get('event')}")
            
            # Extract required IDs
            start_data = call_data.get("start", {})
            stream_sid = start_data.get("streamSid")
            call_sid = start_data.get("callSid")
            
            if not stream_sid or not call_sid:
                raise ValueError(f"Missing streamSid or callSid in start event")
            
            if self.config.enable_handshake_logs:
                logger.info(f"Twilio handshake completed - Stream: {stream_sid}, Call: {call_sid}")
            
            return {"stream_sid": stream_sid, "call_sid": call_sid}
            
        except asyncio.TimeoutError:
            raise Exception("Timeout during Twilio handshake")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON during handshake: {e}")
        except Exception as e:
            raise Exception(f"Handshake failed: {e}") 
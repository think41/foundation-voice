from fastapi import WebSocket
from typing import Optional, Callable
from loguru import logger
from .agent.run import run_agent
from .utils.transport.connection_manager import WebRTCOffer, connection_manager
from .utils.transport.session_manager import session_manager
from .utils.transport.sip_detection import SIPDetector
import aiohttp
from .utils.transport.transport import TransportType
import uuid

class CaiSDK:
    def __init__(self, agent_func: Optional[Callable] = None, agent_config: Optional[dict] = None):        
        self.agent_func = agent_func or run_agent
        self.agent_config = agent_config or {}
    
    async def websocket_endpoint_with_agent(self, websocket: WebSocket, agent: dict, session_id: Optional[str] = None, **kwargs):
        """
        Main WebSocket endpoint that automatically detects transport type.
        Users just call this - all complexity is handled internally.
        """
        try:
            # Auto-detect transport type (internal SDK logic)
            transport_type, sip_params = await self._auto_detect_transport(websocket)
            
            # Add SIP parameters if this is a SIP call
            if sip_params:
                kwargs["sip_params"] = sip_params
            
            logger.debug(f"Auto-detected transport: {transport_type.value}")
            
            await self.agent_func(
                transport_type,
                connection=websocket,
                session_id=session_id,
                callbacks=agent.get("callbacks", None),
                tool_dict=agent.get("tool_dict", {}),
                contexts=agent.get("contexts", {}),
                config=agent.get("config", {}),
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Error in websocket_endpoint_with_agent: {e}")
            raise

    async def _auto_detect_transport(self, websocket: WebSocket) -> tuple[TransportType, Optional[dict]]:
        """Auto-detect transport type with simplified logic"""
        query_params = dict(websocket.query_params)
        
        # 1. Check for explicit transport type
        explicit_transport = query_params.get("transport_type", "").lower()
        if explicit_transport in ["websocket", "webrtc", "daily"]:
            return TransportType(explicit_transport), None
        
        # 2. Try SIP detection (simple pattern-based approach)
        client_ip = websocket.client.host if websocket.client else "unknown"
        headers = dict(websocket.headers) if hasattr(websocket, 'headers') else {}
        
        if SIPDetector.detect_sip_connection(client_ip, headers, query_params):
            sip_params = await SIPDetector.handle_sip_handshake(websocket)
            if sip_params:
                return TransportType.SIP, sip_params
            logger.debug("SIP detection failed, falling back to WebSocket")
        
        # 3. Default to WebSocket
        return TransportType.WEBSOCKET, None
    
    async def webrtc_endpoint(self, offer: WebRTCOffer, agent: dict, metadata: Optional = None):
        if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
            answer, connection = await connection_manager.handle_webrtc_connection(offer)
            response = {
                "answer": answer,
                "background_task_args": {
                    "func": run_agent,
                    "transport_type": TransportType.WEBRTC,
                    "session_id": answer["pc_id"],
                    "connection": connection,
                    "config": agent["config"],
                    "contexts": agent.get("contexts", {}),
                    "tool_dict": agent.get("tool_dict", {}),
                    "callbacks": agent.get("callbacks", None),
                    "metadata": metadata
                }
            }
            return response
            
        answer, connection = await connection_manager.handle_webrtc_connection(offer)
        response = {
            "answer": answer,
            "background_task_args": {
                "func": run_agent,
                "transport_type": TransportType.WEBRTC,
                "session_id": answer["pc_id"],
                "connection": connection,
                "config": agent["config"],
                "contexts": agent.get("contexts", {}),
                "tool_dict": agent.get("tool_dict", {}),
                "callbacks": agent.get("callbacks", None),
                "metadata": metadata
            }
        }
        return response
    
    async def connect_handler(self, request: dict, agent: dict):
        try:
            transport_type_str = request.get("transportType", "").lower()
            agent_config = request.get("agentConfig", {})
            
            # Convert string to TransportType enum
            try:
                transport_type = TransportType(transport_type_str)
            except ValueError:
                return {"error": f"Unsupported transport type: {transport_type_str}"}
            
            if transport_type == TransportType.WEBSOCKET:
                session_id = str(uuid.uuid4())

                return {
                    'session_id': session_id,
                    'websocket_url': f"/ws?session_id={session_id}&agent_name={request.get('agent_name')}"
                }

                
            elif transport_type == TransportType.WEBRTC:
                # Check if this is a WebRTC offer
                if "sdp" in request and "type" in request:
                    # Handle WebRTC offer
                    offer = WebRTCOffer(
                        sdp=request["sdp"],
                        type=request["type"],
                        pc_id=request.get("pc_id"),
                        restart_pc=request.get("restart_pc", False),
                        agent_name=request.get("agent_name")
                    )
                    
                    if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
                        answer, connection = await connection_manager.handle_webrtc_connection(offer)
                        return { 
                            "answer": answer,
                            "background_task_args": {
                                "func": run_agent,
                                "transport_type": transport_type,
                                "session_id": answer["pc_id"],
                                "config": agent["config"],
                                "connection": connection,
                                "contexts": agent.get("contexts", {}),
                                "tool_dict": agent.get("tool_dict", {}),
                                "callbacks": agent.get("callbacks", None),
                            }
                        }
                    
                    answer, connection = await connection_manager.handle_webrtc_connection(offer)
                    return {
                        "answer": answer,
                        "background_task_args": {
                            "func": run_agent,
                            "transport_type": transport_type,
                            "connection": connection,
                            "config": agent["config"],
                            "contexts": agent.get("contexts", {}),
                            "tool_dict": agent.get("tool_dict", {}),
                            "callbacks": agent.get("callbacks", None),
                        }
                    }
                else:
                    # Return WebRTC UI details
                    return {
                        "offer_url": "/api/connect",  # Use same endpoint for offers
                        "webrtc_ui_url": "/webrtc",
                    }
                    
            elif transport_type == TransportType.DAILY:
                async with aiohttp.ClientSession() as session:
                    url, token = await connection_manager.handle_daily_connection(session)

                    session_id = str(uuid.uuid4())
                    return { 
                        "room_url": url,
                        "token": token,
                        "background_task_args": {
                            "func": run_agent,
                            "transport_type": transport_type,
                            "session_id": session_id,
                            "room_url": url,
                            "token": token,
                            "config": agent["config"],
                            "contexts": agent.get("contexts", {}),
                            "tool_dict": agent.get("tool_dict", {}),
                            "callbacks": agent.get("callbacks", None),
                        }
                    }
                
            else:
                return {"error": f"Unsupported transport type: {transport_type_str}"}
                
        except Exception as e:
            return {"error": f"Failed to establish connection: {str(e)}"}

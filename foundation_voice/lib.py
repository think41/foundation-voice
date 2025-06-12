from fastapi import WebSocket
from typing import Optional, Callable
from .agent.run import run_agent
from .utils.transport.connection_manager import WebRTCOffer, connection_manager
from .utils.transport.session_manager import session_manager
import aiohttp
from .utils.transport.transport import TransportType
import uuid

class CaiSDK:
    def __init__(self, agent_func: Optional[Callable] = None, agent_config: Optional[dict] = None):        
        self.agent_func = agent_func or run_agent
        self.agent_config = agent_config or {}
    
    async def websocket_endpoint_with_agent(self, websocket: WebSocket, agent: dict, session_id: Optional[str] = None):
        await websocket.accept()
        try:
            await self.agent_func(
                TransportType.WEBSOCKET,
                connection=websocket,
                session_id=session_id,
                callbacks=agent.get("callbacks", None),
                tool_dict=agent.get("tool_dict", {}),
                contexts=agent.get("contexts", {}),
                config=agent.get("config", {}),
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            await websocket.close()

    
    async def webrtc_endpoint(self, offer: WebRTCOffer, agent: dict, metadata: Optional[dict] = None):
        if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
            answer, connection = await connection_manager.handle_webrtc_connection(offer)
            response = {
                "answer": answer,
                "background_task_args": {
                    "func": run_agent,
                    "transport_type": TransportType.WEBRTC,
                    "session_id": offer.session_id,
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
                "session_id": offer.session_id,
                "connection": connection,
                "config": agent["config"],
                "contexts": agent.get("contexts", {}),
                "tool_dict": agent.get("tool_dict", {}),
                "callbacks": agent.get("callbacks", None),
                "metadata": metadata
            }
        }
        return response
    
    async def connect_handler(self, request: dict, agent: dict, session_id: Optional[str] = None):
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
                        session_id=request.get("session_id"),
                        restart_pc=request.get("restart_pc", False),
                        agent_name=request.get("agent_name")
                    )
                    
                    if offer.session_id and session_manager.get_webrtc_session(offer.session_id):
                        answer, connection = await connection_manager.handle_webrtc_connection(offer)
                        return { 
                            "answer": answer,
                            "background_task_args": {
                                "func": run_agent,
                                "transport_type": transport_type,
                                "session_id": offer.session_id,
                                "connection": connection,
                                "config": agent["config"],
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

                    session_id = session_id or str(uuid.uuid4())
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

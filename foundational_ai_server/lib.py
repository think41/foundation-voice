from fastapi import WebSocket, BackgroundTasks
from typing import Optional, Callable, Dict
from .agent.run import run_agent
from .utils.transport.connection_manager import WebRTCOffer, connection_manager
from .utils.transport.session_manager import session_manager
import aiohttp
import time
from .agent_configure.utils.callbacks import custom_callbacks
from .utils.transport.transport import TransportType
from .agent.agent import AgentCallbacks

class CaiSDK:
    def __init__(self, agent_func: Optional[Callable] = None, agent_config: Optional[dict] = None):        
        self.agent_func = agent_func or run_agent
        self.agent_config = agent_config or {}
    
    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        try:
            await self.agent_func(TransportType.WEBSOCKET, connection=websocket, **self.agent_config)
        except Exception:
            await websocket.close()
    
    async def webrtc_endpoint(self, offer: WebRTCOffer, background_tasks: BackgroundTasks, tool_dict: dict, agent_callbacks: AgentCallbacks):
        if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
            answer, connection = await connection_manager.handle_webrtc_connection(offer)
            return answer
            
        answer, connection = await connection_manager.handle_webrtc_connection(offer)
        background_tasks.add_task(
            run_agent, 
            TransportType.WEBRTC, 
            connection=connection, 
            session_id=answer["pc_id"],
            callbacks=agent_callbacks,
            tool_dict=tool_dict,
            **self.agent_config
        )
        return answer
    
    async def connect_handler(self, background_tasks: BackgroundTasks, request: dict, tool_dict: dict, agent_callbacks: AgentCallbacks):
        try:
            transport_type_str = request.get("transportType", "").lower()
            agent_config = request.get("agentConfig", {})
            
            # Convert string to TransportType enum
            try:
                transport_type = TransportType(transport_type_str)
            except ValueError:
                return {"error": f"Unsupported transport type: {transport_type_str}"}
            
            if transport_type == TransportType.WEBSOCKET:
                return {"websocket_url": "/ws"}
                
            elif transport_type == TransportType.WEBRTC:
                # Check if this is a WebRTC offer
                if "sdp" in request and "type" in request:
                    # Handle WebRTC offer
                    offer = WebRTCOffer(
                        sdp=request["sdp"],
                        type=request["type"],
                        pc_id=request.get("pc_id"),
                        restart_pc=request.get("restart_pc", False)
                    )
                    
                    if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
                        answer, _ = await connection_manager.handle_webrtc_connection(offer)
                        return answer
                    
                    answer, connection = await connection_manager.handle_webrtc_connection(offer)
                    background_tasks.add_task(
                        run_agent,
                        transport_type,
                        connection=connection,
                        session_id=answer["pc_id"],
                        callbacks=agent_callbacks,
                        tool_dict=tool_dict,
                        **self.agent_config
                    )
                    return answer
                else:
                    # Return WebRTC UI details
                    return {
                        "offer_url": "/api/connect",  # Use same endpoint for offers
                        "webrtc_ui_url": "/webrtc",
                    }
                    
            elif transport_type == TransportType.DAILY:
                async with aiohttp.ClientSession() as session:
                    url, token = await connection_manager.handle_daily_connection(session)
                    if not session_manager.get_daily_room_session(url):
                        background_tasks.add_task(
                            run_agent,
                            transport_type,
                            room_url=url,
                            token=token,
                            bot_name="AI Assistant",                            
                            callbacks=agent_callbacks,
                            tool_dict=tool_dict,
                            **self.agent_config
                        )   
                return {"room_url": url, "token": token}
            
            else:
                return {"error": f"Unsupported transport type: {transport_type_str}"}
                
        except Exception as e:
            return {"error": f"Failed to establish connection: {str(e)}"}

    # async def create_daily_room(
    #     self,
    #     background_tasks: BackgroundTasks,
    #     room_config: Optional[Dict] = None,
    #     bot_name: Optional[str] = None,
    #     **kwargs
    # ) -> Dict[str, str]:
    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             # Merge room_config with defaults
    #             final_room_config = {
    #                 "privacy": "public",  # default
    #                 "exp": round(time.time()) + 86400,  # 1 day expiry
    #                 **(room_config or {})
    #             }
                
    #             url, token = await connection_manager.handle_daily_connection(
    #                 session,
    #                 room_config=final_room_config
    #             )
                
    #             if not session_manager.get_daily_room_session(url):
    #                 agent_config = {
    #                     **self.agent_config,
    #                     "bot_name": bot_name or self.agent_config.get("bot_name", "AI Assistant"),
    #                     **kwargs
    #                 }
                    
    #                 background_tasks.add_task(
    #                     self.agent_func,
    #                     "daily",
    #                     room_url=url,
    #                     token=token,
    #                     callbacks=custom_callbacks,
    #                     **agent_config
    #                 )
                
    #             return {
    #                 "room_url": url,
    #                 "token": token,
    #                 "room_config": final_room_config
    #             }
                
    #     except Exception as e:
    #         return {
    #             "error": f"Failed to create Daily.co room: {str(e)}",
    #             "details": str(e)
    #         }
    
    # async def end_daily_room(self, room_url: str) -> Dict[str, str]:
    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             await connection_manager.end_daily_connection(session, room_url)
    #             session_manager.remove_daily_session(room_url)
    #             return {"status": "success", "message": f"Room {room_url} ended"}
    #     except Exception as e:
    #         return {"status": "error", "message": str(e)}
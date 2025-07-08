from typing import Optional, Union
from fastapi import WebSocket
from loguru import logger
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.pipeline.task import PipelineTask
from ..utils.transport.session_manager import session_manager


async def cleanup(
    transport_type: str,
    connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
    room_url: str = None,
    session_id: str = None,
    task: PipelineTask = None,
):
    try:
        # Cancel the pipeline task if it exists and is running
        if task:
            await task.cancel()
            logger.info(f"Cancelled pipeline task for session: {session_id}")

        # Clean up transport-specific resources
        if transport_type == "webrtc" and hasattr(connection, "pc"):
            pc_id = id(connection.pc)
            await session_manager.remove_session(session_id)
            if pc_id in session_manager.webrtc_sessions:
                del session_manager.webrtc_sessions[pc_id]
                logger.info(f"Cleaned up WebRTC session: {pc_id}")
        elif transport_type == "daily" and room_url:
            await session_manager.remove_session(session_id)
            if room_url in session_manager.daily_room_sessions:
                del session_manager.daily_room_sessions[room_url]
            logger.info(f"Cleaned up Daily session for room: {room_url}")
        elif transport_type == "websocket":
            await session_manager.remove_session(session_id)
            logger.info(f"Cleaned up WebSocket session: {session_id}")

        # Remove from active sessions if still present
        if session_id in session_manager.active_sessions:
            del session_manager.active_sessions[session_id]

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        # Re-raise the exception to ensure it's not silently ignored
        raise

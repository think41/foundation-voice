import uuid
from typing import Optional, Union, Dict, Any
from fastapi import WebSocket
from loguru import logger
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.pipeline.runner import PipelineRunner
from ..utils.transport.session_manager import session_manager
from ..utils.transport.transport import TransportType
from .agent import create_agent_pipeline
from .cleanup import cleanup
from .agent import AgentCallbacks

async def run_agent(
    transport_type: TransportType,
    config: Dict[str, Any],
    connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
    room_url: str = None,
    token: str = None,
    bot_name: str = "AI Assistant",
    session_id: str = None,
    callbacks: Optional[AgentCallbacks] = None,
    tool_dict: Dict[str, Any] = None,
    contexts: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    if not session_id:
        session_id = str(uuid.uuid4())

    if transport_type == TransportType.DAILY and room_url:
        existing_session = session_manager.get_daily_room_session(room_url)
        if existing_session:
            logger.info(f"Bot already exists in Daily room: {room_url}")
            return

    if transport_type == TransportType.WEBRTC and isinstance(connection, SmallWebRTCConnection):
        existing_session = session_manager.get_webrtc_session(connection.pc_id)
        if existing_session:
            logger.info(f"Bot already exists for WebRTC connection: {connection.pc_id}")
            return

    task, transport = await create_agent_pipeline(
        transport_type=transport_type,
        connection=connection,
        room_url=room_url,
        token=token,
        bot_name=bot_name,
        session_id=session_id,
        callbacks=callbacks,
        tool_dict=tool_dict,
        contexts=contexts,
        config=config,
        metadata=metadata
    )

    try:
        if transport_type == TransportType.DAILY:
            await session_manager.add_session(session_id, task, daily_room_url=room_url)
        elif transport_type == TransportType.WEBRTC and isinstance(connection, SmallWebRTCConnection):
            await session_manager.add_webrtc_session(connection.pc_id, task)
        else:
            await session_manager.add_session(session_id, task)

        runner = PipelineRunner()
        await runner.run(task)
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise
    finally:
        try:
            await cleanup(transport_type, connection, room_url, session_id, task)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
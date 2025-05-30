import os
from pydoc import text
import sys
from typing import Optional, Union
from fastapi import WebSocket
from loguru import logger
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.frames.frames import BotInterruptionFrame, TextFrame
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIProcessor, RTVIObserver, RTVIAction, RTVIActionArgument
from ..utils.providers.stt_provider import create_stt_service
from ..utils.providers.tts_provider import create_tts_service
from ..utils.providers.llm_provider import create_llm_service, create_llm_context
from ..utils.config_loader import ConfigLoader
from pipecat.processors.transcript_processor import TranscriptProcessor
from ..utils.transport.transport import TransportFactory
from ..utils.transport import session_manager
from ..utils.observers.func_observer import FunctionObserver
from ..agent_configure.utils.context import contexts
from ..agent_configure.utils.tool import tool_config
from ..utils.transcripts.transcript_handler import TranscriptHandler

from ..utils.observers.user_bot_latency_log_observer import UserBotLatencyLogObserver
from ..utils.observers.call_summary_metrics_observer import CallSummaryMetricsObserver
import uuid
import json

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")



async def create_agent_pipeline(
    transport_type: str,
    connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
    room_url: str = None,
    token: str = None,
    bot_name: str = "AI Assistant",
    session_id: uuid.UUID = None,
):
    """
    Creates and returns the agent pipeline with the specified transport.
    """

    # Set up RTVI processor for transcript and event emission
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))


    config_path = os.getenv("CONFIG_PATH")
    if not config_path:
        logger.error("CONFIG_PATH environment variable not set")
        raise ValueError("CONFIG_PATH environment variable must be set")

    try:
        config = ConfigLoader.load_config(config_path)
        agent_config = config.get("agent", {})
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Create transport using factory
    transport = TransportFactory.create_transport(
        transport_type=transport_type,
        connection=connection,
        room_url=room_url,
        token=token,
        bot_name=bot_name,
    )

    try:
        logger.debug("Creating LLM service from configuration")
        args = {
            "rtvi": rtvi,
            "context": contexts.get(agent_config.get("context")),
            "tools": tool_config,
        }
        llm = create_llm_service(
            agent_config.get("llm", {}),
            data=args,
        )
    except Exception as e:
        logger.error(f"Failed to create LLM service: {e}")
        raise

    try:
        logger.debug("Creating STT service from configuration")
        stt = create_stt_service(agent_config.get("stt", {}))
    except Exception as e:
        logger.error(f"Failed to create STT service: {e}")
        raise

    try:
        logger.debug("Creating TTS service from configuration")
        tts = create_tts_service(agent_config.get("tts", {}))
    except Exception as e:
        logger.error(f"Failed to create TTS service: {e}")
        raise

    context = None
    try:
        logger.debug("Creating context")
        context = create_llm_context(agent_config)
    except Exception as e:
        logger.error(f"Failed to create context: {e}")
        raise

    context_aggregator = llm.create_context_aggregator(context)

    transcript = TranscriptProcessor()

    transcript_handler = TranscriptHandler(
        transport=transport,
        session_id=session_id,
        log_message=True,
        transport_type=transport_type,
        connection=connection,
    )
    # Create pipeline with RTVI processor included
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript.user(),
            context_aggregator.user(),
            llm,
            tts,
            rtvi,
            transcript.assistant(),
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    # Create pipeline task with observers
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[
            
            # RTVIObserver(rtvi),
            UserBotLatencyLogObserver(),
            CallSummaryMetricsObserver()
        ,
            FunctionObserver(llm=llm, rtvi=rtvi),
        ],
    )

    async def append_to_messages_func(processor, service, arguments):
        messages = arguments.get("messages")
        run_immediately = arguments.get("run_immediately")
        # await task.queue_frames(
        #     [context_aggregator.user().add_messages(
        #         messages[0]
        #     )]
        # )
        context_aggregator.user().add_messages(messages)
        await task.queue_frames([context_aggregator.user().get_context_frame()])
        # await context_aggregator.user().add_messages(messages[0])
        print(f"{messages}")
        
        return True

    append_to_messages = RTVIAction(
        service="llm",
        action="append_to_messages",
        arguments=[
            RTVIActionArgument(
                name="messages",
                type="array"
            ),
            RTVIActionArgument(
                name="run_immediately",
                type="bool"
            )
        ],
        result="bool",
        handler=append_to_messages_func
    )
    rtvi.register_action(append_to_messages)

    @transcript.event_handler("on_transcript_update")
    async def handle_transcript_update(processor, frame):
        await transcript_handler.on_transcript_update(transcript, frame)

    @rtvi.event_handler("on_client_ready")
    async def on_client_connected(rtvi):
        logger.info("Client ready")
        await rtvi.set_bot_ready()
        await task.queue_frames([context_aggregator.user().get_context_frame()])
    


    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    if transport_type == "daily":

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            print(f"Participant joined: {participant}")
            await transport.capture_participant_transcription(participant["id"])

        # Create and store observers
        call_metrics_observer = CallSummaryMetricsObserver()
        task_observers = [
            RTVIObserver(rtvi),
            UserBotLatencyLogObserver(),
            call_metrics_observer
        ]
        
        # Create pipeline task with observers
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=task_observers,
        )
        
        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            print(f"Participant left: {participant}")
            logger.info("Generating call metrics summary...")
            
            try:
                # Directly call the metrics observer we stored
                if call_metrics_observer:
                    await call_metrics_observer._log_summary()
            except Exception as e:
                logger.error(f"Error generating metrics summary: {e}")
            finally:
                # Always ensure the task is cancelled
                await task.cancel()

    if transport_type == "websocket":

        @transport.event_handler("on_session_timeout")
        async def on_session_timeout(transport, client):
            logger.info("WebSocket session timeout")
            try:
                # Send a text frame indicating session end before closing
                await task.queue_frames(
                    [
                        TextFrame("Session timeout - closing connection"),
                        BotInterruptionFrame(),
                    ]
                )
            except Exception as e:
                logger.error(f"Error during session timeout handling: {e}")
            finally:
                # Ensure cleanup happens
                if transport_type == "websocket" and connection:
                    await connection.close()

            # Queue the frame for processing

    return task


async def run_agent(
    transport_type: str,
    connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
    room_url: str = None,
    token: str = None,
    bot_name: str = "AI Assistant",
    session_id: str = None,
):
    """
    Runs the agent with the specified transport configuration.
    """
    # Generate unique session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    # For Daily transport, check if a bot already exists in the room
    if transport_type == "daily" and room_url:
        existing_session = session_manager.get_daily_room_session(room_url)
        if existing_session:
            logger.info(f"Bot already exists in Daily room: {room_url}")
            return

    # For WebRTC transport, check if a session already exists
    if transport_type == "webrtc" and isinstance(connection, SmallWebRTCConnection):
        existing_session = session_manager.get_webrtc_session(connection.pc_id)
        if existing_session:
            logger.info(f"Bot already exists for WebRTC connection: {connection.pc_id}")
            return

    task = await create_agent_pipeline(
        transport_type=transport_type,
        connection=connection,
        room_url=room_url,
        token=token,
        bot_name=bot_name,
        session_id=session_id,
    )

    # Register the session
    if transport_type == "daily":
        await session_manager.add_session(session_id, task, daily_room_url=room_url)
    elif transport_type == "webrtc" and isinstance(connection, SmallWebRTCConnection):
        await session_manager.add_webrtc_session(connection.pc_id, task)
    else:
        await session_manager.add_session(session_id, task)

    try:
        runner = PipelineRunner()
        await runner.run(task)
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise
    finally:
        # Comprehensive cleanup for all transport types
        try:
            if transport_type == "webrtc" and isinstance(
                connection, SmallWebRTCConnection
            ):
                pc_id = connection.pc_id
                await session_manager.remove_webrtc_session(pc_id)
                logger.info(f"Cleaned up WebRTC session: {pc_id}")

            elif transport_type == "daily" and room_url:
                await session_manager.remove_session(session_id)
                # Ensure Daily room session is also cleaned up
                if room_url in session_manager.daily_room_sessions:
                    del session_manager.daily_room_sessions[room_url]
                logger.info(f"Cleaned up Daily session for room: {room_url}")

            elif transport_type == "websocket":
                await session_manager.remove_session(session_id)
                logger.info(f"Cleaned up WebSocket session: {session_id}")

            # Additional cleanup for any remaining references
            if session_id in session_manager.active_sessions:
                del session_manager.active_sessions[session_id]

            logger.info(f"Session cleanup completed for {transport_type} transport")

        except Exception as cleanup_error:
            logger.error(f"Error during session cleanup: {cleanup_error}")
            # Don't re-raise the cleanup error to ensure the original error (if any) is propagated

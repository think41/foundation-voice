import sys
import uuid

from loguru import logger
from fastapi import WebSocket
from typing import Optional, Union, Dict, Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.utils.tracing.setup import setup_tracing
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.transports.network.webrtc_connection import SmallWebRTCConnection
from pipecat.processors.frameworks.rtvi import (
    RTVIConfig,
    RTVIProcessor,
    RTVIAction,
    RTVIActionArgument,
)
from pipecat.observers.loggers.user_bot_latency_log_observer import (
    UserBotLatencyLogObserver,
)

from foundation_voice.custom_plugins.agent_callbacks import AgentCallbacks, AgentEvent
from foundation_voice.utils.function_adapter import FunctionFactory
from foundation_voice.utils.transport.transport import TransportFactory, TransportType
from foundation_voice.utils.idle_processor.user_idle_processor import UserIdleProcessor
from foundation_voice.utils.transcripts.transcript_handler import TranscriptHandler
from foundation_voice.utils.providers.stt_provider import create_stt_service
from foundation_voice.utils.providers.tts_provider import create_tts_service
from foundation_voice.utils.providers.llm_provider import (
    create_llm_service,
    create_llm_context,
)
from foundation_voice.utils.observers.func_observer import FunctionObserver
from foundation_voice.utils.observers.call_summary_metrics_observer import (
    CallSummaryMetricsObserver,
)

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def create_agent_pipeline(
    transport_type: TransportType,
    config: Dict[str, Any],
    connection: Optional[Union[WebSocket, SmallWebRTCConnection]] = None,
    room_url: str = None,
    token: str = None,
    bot_name: str = "AI Assistant",
    session_id: uuid.UUID = None,
    callbacks: Optional[AgentCallbacks] = None,
    tool_dict: Dict[str, Any] = None,
    contexts: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
):
    """
    Creates and returns the agent pipeline with the specified transport.
    Args:
        transport_type: Type of transport to use (must be TransportType enum)
        connection: Connection instance for websocket/webrtc
        room_url: URL for Daily.co room
        token: Authentication token
        bot_name: Name of the bot
        session_id: Optional session ID
        callbacks: Optional instance of AgentCallbacks for custom event handling
    """
    # Use default callbacks if none provided
    if callbacks is None:
        callbacks = AgentCallbacks()

    if config.get("pipeline", {}).get("enable_tracing"):
        exporter = OTLPSpanExporter(
            endpoint="http://localhost:4317",  # Jaeger or other collector endpoint
            insecure=True,
        )

        setup_tracing(
            service_name="my-voice-app",
            exporter=exporter,
            console_export=False,  # Set to True for debug output
        )

    # Set up RTVI processor for transcript and event emission
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    try:
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
        vad_config=agent_config.get("vad", {}),
        **kwargs,
    )

    tools = FunctionFactory(
        provider=agent_config.get("llm", {}).get("provider", "openai"),
        functions=tool_dict,
    ).built_tools

    try:
        logger.debug("Creating LLM service from configuration")
        args = {
            "rtvi": rtvi,
            "contexts": contexts,
            "tools": tools,
        }
        llm = create_llm_service(
            agent_config,
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
        context = create_llm_context(
            agent_config,
            contexts.get(
                agent_config.get("llm", {}).get("agent_config", {}).get("context"), {}
            ),
            tools,
        )

        context_aggregator = llm.create_context_aggregator(context)

        if kwargs.get("sip_params"):
            if kwargs.get("sip_params").get("call_sid"):
                call_sid = kwargs.get("sip_params").get("call_sid")
                logger.debug(f"call_sid: {call_sid}")
                context_aggregator.assistant().add_messages(
                    [
                        {
                            "role": "assistant",
                            "content": f'The call sid is "{call_sid}", use it only when needed.',
                        },
                        {
                            "role": "assistant",
                            "content": f'The session_id is "{session_id}", use it only when needed.',
                        },
                    ]
                )
        else:
            call_sid = None

        # Handle session resume data if available
        if metadata and "transcript" in metadata:
            logger.info("Restoring previous transcript from session resume data")
            previous_messages = metadata["transcript"]
            if isinstance(previous_messages, list):
                # Add previous messages to the context
                for message in previous_messages:
                    if (
                        isinstance(message, dict)
                        and "role" in message
                        and "content" in message
                    ):
                        context_aggregator.user().add_message(message)
                logger.info(
                    f"Restored {len(previous_messages)} messages from previous session"
                )
    except Exception as e:
        logger.error(f"Failed to create context: {e}")
        raise

    transcript = TranscriptProcessor()

    idle_processor = UserIdleProcessor(tries=2, timeout=10)

    transcript_handler = TranscriptHandler(
        transport=transport,
        session_id=session_id,
        transport_type=transport_type.value,  # Use enum value for backward compatibility
        connection=connection,
    )

    # Create pipeline with RTVI processor included
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            idle_processor,
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

    # Register event handlers for all transport types

    async def append_to_messages_func(processor, service, arguments):
        messages = arguments.get("messages")
        _run_immediately = arguments.get("run_immediately")
        context_aggregator.user().add_messages(messages)
        await task.queue_frames([context_aggregator.user().get_context_frame()])
        return True

    append_to_messages = RTVIAction(
        service="llm",
        action="append_to_messages",
        arguments=[
            RTVIActionArgument(name="messages", type="array"),
            RTVIActionArgument(name="_run_immediately", type="bool"),
        ],
        result="bool",
        handler=append_to_messages_func,
    )
    rtvi.register_action(append_to_messages)

    # Create observers
    call_metrics_observer = CallSummaryMetricsObserver()
    task_observers = [
        UserBotLatencyLogObserver(),
        call_metrics_observer,
        FunctionObserver(rtvi=rtvi),
    ]

    # Configure sample rates based on transport type
    # Twilio SIP requires 8kHz, other transports can use higher rates
    # if transport_type == TransportType.SIP:
    #     audio_in_sample_rate = 8000   # Twilio requires 8kHz
    #     audio_out_sample_rate = 8000  # Twilio requires 8kHz
    #     logger.debug("Using Twilio SIP sample rates: 8kHz in/out")
    # else:
    #     audio_in_sample_rate = 16000   # Higher quality for WebRTC/WebSocket
    #     audio_out_sample_rate = 24000  # Higher quality for WebRTC/WebSocket
    #     logger.debug(f"Using standard sample rates: {audio_in_sample_rate}Hz in, {audio_out_sample_rate}Hz out")

    # Create pipeline task with transport-appropriate sample rates
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=config.get("pipeline", {}).get(
                "sample_rate_in", 16000
            ),
            audio_out_sample_rate=config.get("pipeline", {}).get(
                "sample_rate_out", 24000
            ),
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            enable_tracing=config.get("pipeline", {}).get(
                "enable_tracing", False
            ),  # Enable tracing for this task
            enable_turn_tracking=True,  # Enable turn tracking for this task
            conversation_id="customer-123",
        ),
        observers=task_observers,
    )

    metadata_without_transcript = {}
    if metadata:
        metadata_without_transcript = metadata.copy()
        metadata_without_transcript.pop("transcript", None)

    @transcript.event_handler(AgentEvent.TRANSCRIPT_UPDATE.value)
    async def handle_transcript_update(processor, frame):
        callback = callbacks.get_callback(AgentEvent.TRANSCRIPT_UPDATE)

        data = {
            "frame": frame,
            "metadata": metadata_without_transcript,
            "session_id": session_id,
        }
        await callback(data)
        await transcript_handler.on_transcript_update(frame)

    if transport_type == TransportType.DAILY:

        @rtvi.event_handler("on_client_ready")
        async def on_client_connected(rtvi):
            logger.info("Daily client ready")
            await rtvi.set_bot_ready()
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @transport.event_handler(AgentEvent.PARTICIPANT_LEFT.value)
        async def on_participant_left(transport, participant, reason):
            logger.info("Participant left Daily room")
            callback = callbacks.get_callback(AgentEvent.CLIENT_DISCONNECTED)
            end_transcript = transcript_handler.get_all_messages()
            # Get metrics from the observer
            metrics = (
                call_metrics_observer.get_metrics_summary()
                if call_metrics_observer
                else None
            )
            data = {
                "participant": participant,
                "reason": reason,
                "metadata": metadata,
                "transcript": end_transcript,
                "metrics": metrics,
                "session_id": session_id,
            }

            await callback(data)

            try:
                # Only try to log metrics if the observer exists
                if call_metrics_observer:
                    await call_metrics_observer._log_summary()
            except Exception as e:
                logger.error(f"Error generating metrics summary: {e}")
            finally:
                from .cleanup import cleanup

                await cleanup(transport_type, connection, room_url, session_id, task)

        @transport.event_handler(AgentEvent.FIRST_PARTICIPANT_JOINED.value)
        async def on_first_participant_joined(transport, participant):
            callback = callbacks.get_callback(AgentEvent.FIRST_PARTICIPANT_JOINED)
            data = {
                "participant": participant,
                "metadata": metadata,
                "session_id": session_id,
            }
            await callback(data)
            await transport.capture_participant_transcription(participant["id"])

    if transport_type != TransportType.DAILY:

        @transport.event_handler(AgentEvent.CLIENT_DISCONNECTED.value)
        async def on_client_disconnected(transport, client):
            logger.info("WebSocket client disconnected")
            callback = callbacks.get_callback(AgentEvent.CLIENT_DISCONNECTED)
            end_transcript = transcript_handler.get_all_messages()
            # Get metrics from the observer
            metrics = (
                call_metrics_observer.get_metrics_summary()
                if call_metrics_observer
                else None
            )

            data = {
                "transcript": end_transcript,
                "metrics": metrics,
                "metadata": metadata,
                "session_id": session_id,
            }

            await callback(data)

            try:
                # Only try to log metrics if the observer exists
                if call_metrics_observer:
                    await call_metrics_observer._log_summary()
            except Exception as e:
                logger.error(f"Error generating metrics summary: {e}")
            finally:
                # Always ensure the task is cancelled
                from .cleanup import cleanup

                await cleanup(transport_type, connection, room_url, session_id, task)

        @transport.event_handler(AgentEvent.CLIENT_CONNECTED.value)
        async def on_client_connected(transport, client):
            callback = callbacks.get_callback(AgentEvent.CLIENT_CONNECTED)
            data = {"client": client, "metadata": metadata, "session_id": session_id}
            await callback(data)
            await task.queue_frames([context_aggregator.user().get_context_frame()])

    if transport_type == TransportType.WEBRTC:

        @transport.event_handler("on_client_closed")
        async def on_client_closed(transport, client):
            logger.info("Client clicked on disconnect. Ending Pipeline task")
            await task.cancel()

    return task, transport

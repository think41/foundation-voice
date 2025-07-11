import json
import uuid
from enum import Enum
from loguru import logger
from fastapi import WebSocket
from typing import Dict, Any, Optional, Callable, AsyncGenerator

from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.frames.frames import Frame, AudioRawFrame, InputAudioRawFrame
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.audio.utils import create_default_resampler


class ExotelTransport(BaseTransport):
    """
    Transport for Exotel Media Streams using PipeCat's ExotelFrameSerializer.
    """

    def __init__(self, websocket: WebSocket, stream_sid: str, params: Optional[TransportParams] = None):
        """
        Initialize the Exotel transport with a WebSocket connection and stream SID.
        
        Args:
            websocket: FastAPI WebSocket connection
            stream_sid: Exotel Media Stream SID
            params: Optional transport parameters
        """
        super().__init__(params or TransportParams())
        self.websocket = websocket
        self.stream_sid = stream_sid
        self._serializer = ExotelFrameSerializer(
            stream_sid=stream_sid,
            params=ExotelFrameSerializer.InputParams(
                sample_rate=self._params.audio_out_sample_rate
            )
        )
        self._event_handlers: Dict[str, Callable] = {}
        self._running = True
        self._resampler = create_default_resampler()

    def register_event_handler(self, event_name: str, handler: Callable) -> None:
        """
        Register an event handler for transport events.
        
        Args:
            event_name: Name of the event to handle
            handler: Callable to be invoked when the event occurs
        """
        self._event_handlers[event_name] = handler
        logger.debug(f"Registered event handler for {event_name}")

    async def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """
        Emit an event to registered handlers.
        
        Args:
            event_name: Name of the event to emit
            *args: Positional arguments to pass to the handler
            **kwargs: Keyword arguments to pass to the handler
        """
        handler = self._event_handlers.get(event_name)
        if handler:
            try:
                await handler(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event handler for {event_name}: {e}")

    async def input(self) -> AsyncGenerator[Frame, None]:
        """
        Process incoming audio data from the WebSocket and convert to frames.
        
        Yields:
            InputAudioRawFrame objects containing the received audio data
        """
        try:
            while self._running:
                message_str = await self.websocket.receive_text()
                message = json.loads(message_str)
                
                # Process based on event type
                if message.get('event') == 'media':
                    frame = await self._serializer.deserialize(message_str)
                    if frame:
                        yield frame
                elif message.get('event') == 'stop':
                    logger.info(f"Stream {self.stream_sid} stopped.")
                    await self.emit_event("CLIENT_DISCONNECTED", {"reason": "stop_event"})
                    self._running = False
                    break
                elif message.get('event') == 'dtmf':
                    # DTMF events are handled by the serializer and returned as frames
                    frame = await self._serializer.deserialize(message_str)
                    if frame:
                        yield frame
                elif message.get('event') == 'start':
                    # This is the initial connection event
                    # We already have the stream_sid from initialization
                    await self.emit_event("CLIENT_CONNECTED", {"stream_sid": self.stream_sid})
        except Exception as e:
            logger.error(f"Error in Exotel transport input: {e}")
            await self.emit_event("CLIENT_DISCONNECTED", {"reason": str(e)})
            self._running = False

    async def output(self, frame: Frame) -> None:
        """
        Process output frames and send them to the WebSocket.
        
        Args:
            frame: Frame to send to the client
        """
        if not self._running:
            return
            
        try:
            serialized_data = await self._serializer.serialize(frame)
            if serialized_data:
                await self.websocket.send_text(serialized_data)
        except Exception as e:
            logger.error(f"Error in Exotel transport output: {e}")
            self._running = False

    async def close(self) -> None:
        """
        Close the WebSocket connection.
        """
        self._running = False
        logger.info(f"Closing WebSocket connection for Exotel stream {self.stream_sid}")
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing Exotel WebSocket: {e}")

    def event_handler(self, event_name: str):
        """
        Decorator for registering event handlers.
        
        Args:
            event_name: Name of the event to handle
        """
        def decorator(func):
            self.register_event_handler(event_name, func)
            return func
        return decorator

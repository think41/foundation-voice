from typing import Dict, Any, Optional, Callable, Awaitable
from abc import ABC, abstractmethod
from enum import Enum, auto

class AgentEvent(Enum):
    """Enum defining all possible agent events"""
    CLIENT_CONNECTED = "on_client_connected"
    CLIENT_DISCONNECTED = "on_client_disconnected"
    FIRST_PARTICIPANT_JOINED = "on_first_participant_joined"
    PARTICIPANT_LEFT = "on_participant_left"
    SESSION_TIMEOUT = "on_session_timeout"
    TRANSCRIPT_UPDATE = "on_transcript_update"

class AgentCallbacks:
    """
    Class for managing agent callbacks.
    Users must explicitly register callbacks for each event they want to handle.
    """
    
    def __init__(self):
        self._callbacks: Dict[AgentEvent, Callable] = {}
        self._register_default_callbacks()

    def _register_default_callbacks(self):
        """Register default callback implementations"""
        self.register_callback(
            AgentEvent.CLIENT_CONNECTED,
            self._default_client_connected
        )
        self.register_callback(
            AgentEvent.CLIENT_DISCONNECTED,
            self._default_client_disconnected
        )
        self.register_callback(
            AgentEvent.FIRST_PARTICIPANT_JOINED,
            self._default_first_participant_joined
        )
        self.register_callback(
            AgentEvent.PARTICIPANT_LEFT,
            self._default_participant_left
        )
        self.register_callback(
            AgentEvent.TRANSCRIPT_UPDATE,
            self._default_transcript_update
        )

    def register_callback(self, event: AgentEvent, callback: Callable):
        """
        Register a callback function for a specific event.
        Args:
            event: The event to register the callback for
            callback: The callback function to register
        """
        self._callbacks[event] = callback

    def get_callback(self, event: AgentEvent) -> Callable:
        """
        Get the registered callback for an event.
        Args:
            event: The event to get the callback for
        Returns:
            The registered callback function
        Raises:
            KeyError: If no callback is registered for the event
        """
        return self._callbacks[event]

    async def _default_client_connected(self, data: Dict[str, Any]):
        """Default implementation for client connected event"""
        client = data.get("client")
        session_id = data.get("session_id")
        print(f"Client connected with session ID: {session_id}")

    async def _default_client_disconnected(self, data: Dict[str, Any]):
        """Default implementation for client disconnected event"""
        session_id = data.get("session_id")
        print(f"Client disconnected with session ID: {session_id}")
        print(f"Transcript: {data.get('transcript', [])}")
        if data.get('metrics'):
            print(f"Call metrics: {data['metrics']}")

    async def _default_first_participant_joined(self, data: Dict[str, Any]):
        """Default implementation for first participant joined event"""
        participant = data.get('participant')
        session_id = data.get("session_id")
        print(f"Participant joined with session ID {session_id}: {participant}")

    async def _default_participant_left(self, data: Dict[str, Any]):
        """Default implementation for participant left event"""
        participant = data.get('participant')
        session_id = data.get("session_id")
        print(f"Participant left with session ID {session_id}: {participant}")

    async def _default_transcript_update(self, data):
        """Default implementation for transcript update event"""
        frame = data.get("frame")
        session_id = data.get("session_id")
        # metadata = data.get("metadata")

        for message in frame.messages:
            print(f"TRANSCRIPT [{session_id}] [{message.timestamp}] {message.role}: {message.content}")

    def has_callback(self, event: AgentEvent) -> bool:
        """
        Check if a callback is registered for an event.
        Args:
            event: The event to check
        Returns:
            True if a callback is registered, False otherwise
        """
        return event in self._callbacks 
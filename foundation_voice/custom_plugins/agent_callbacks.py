from typing import Dict, Any, Callable
from enum import Enum


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
            AgentEvent.CLIENT_CONNECTED, self._default_client_connected
        )
        self.register_callback(
            AgentEvent.CLIENT_DISCONNECTED, self._default_client_disconnected
        )
        self.register_callback(
            AgentEvent.FIRST_PARTICIPANT_JOINED, self._default_first_participant_joined
        )
        self.register_callback(
            AgentEvent.PARTICIPANT_LEFT, self._default_participant_left
        )
        self.register_callback(
            AgentEvent.TRANSCRIPT_UPDATE, self._default_transcript_update
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

    async def _default_client_connected(self, client: Dict[str, Any]):
        """Default implementation for client connected event"""
        pass

    async def _default_client_disconnected(self, data: Dict[str, Any]):
        """Default implementation for client disconnected event"""
        # Also contains metadata. metadata = data["metadata"]
        print(f"Client disconnected. Transcript: {data.get('transcript', [])}")
        if data.get("metrics"):
            print(f"Call metrics: {data['metrics']}")

    async def _default_first_participant_joined(self, data: Dict[str, Any]):
        """Default implementation for first participant joined event"""
        print(f"Participant joined: {data.get('participant')}")

    async def _default_participant_left(self, data: Dict[str, Any]):
        # reason = data.get("reason")
        # metadata = data.get("metadata")

        """Default implementation for participant left event"""
        print(f"Participant left: {data.get('participant')}")

    async def _default_transcript_update(self, data):
        """Default implementation for transcript update event"""
        frame = data.get("frame")
        # metadata = data.get("metadata")

        for message in frame.messages:
            print(
                f"TRANSCRIPT: [{message.timestamp}] {message.role}: {message.content}"
            )

    def has_callback(self, event: AgentEvent) -> bool:
        """
        Check if a callback is registered for an event.
        Args:
            event: The event to check
        Returns:
            True if a callback is registered, False otherwise
        """
        return event in self._callbacks

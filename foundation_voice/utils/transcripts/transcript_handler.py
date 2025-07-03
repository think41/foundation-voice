import uuid
from typing import Dict, List, Optional
from loguru import logger
from pipecat.frames.frames import TranscriptionMessage, TranscriptionUpdateFrame


class TranscriptHandler:
    def __init__(
        self,
        transport,
        session_id: uuid.UUID,
        transport_type: Optional[str] = "smallwebrtc",
        connection: Optional = None,
    ):
        self._session_id = session_id
        self._transport = transport
        self._transport_type = transport_type
        self._connection = connection
        self.messages: List[TranscriptionMessage] = []
        self._saved_messages: List[Dict] = []  # Store saved messages in memory

    def get_all_messages(self) -> List[Dict]:
        """
        Get all saved messages in chronological order.
        Returns:
            List of dictionaries containing message data with keys:
            - type: "transcript_update"
            - role: message role (e.g., "user", "assistant")
            - content: message content
            - timestamp: message timestamp
        """
        return self._saved_messages

    async def on_transcript_update(self, frame: TranscriptionUpdateFrame):
        """
        Handle transcript updates and store messages.
        Args:
            frame: TranscriptionUpdateFrame containing new messages
        """
        for msg in frame.messages:
            if msg.role == "user":
                logger.info(f"User: {msg.content}")
            self.messages.append(msg)
            # Store message in saved_messages with required format
            self._saved_messages.append(
                {
                    "type": "transcript_update",
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                }
            )

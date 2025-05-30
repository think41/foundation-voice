import uuid
import json

from typing import Dict, List, Optional, Callable
from loguru import logger
from pathlib import Path

from pipecat.frames.frames import TranscriptionMessage, TranscriptionUpdateFrame
from pipecat.processors.transcript_processor import TranscriptProcessor


class TranscriptHandler:
    def __init__(
        self, 
        transport,
        session_id: uuid.UUID,
        transport_type: Optional[str] = "smallwebrtc",
        connection: Optional = None,
        log_message: Optional[bool] = False,
    ):
        self._session_id = session_id
        self._transport = transport
        self._transport_type = transport_type
        self._connection = connection
        self._log_message = log_message

        self.messages: List[TranscriptionMessage] = []

        # Set folder to save files in 'transcripts/bucket/'
        current_file_dir = Path(__file__).parent  # 'transcripts'
        bucket_dir = current_file_dir / "bucket"
        bucket_dir.mkdir(parents=True, exist_ok=True)  # create folder if it doesn't exist

        self._file_path = bucket_dir / f"transcript_{self._session_id}.txt"


        if self._log_message:
            self._write_line: Callable[[str], None] = self._log_and_write
        else: 
            self._write_line: Callable[[str], None] = self._write_to_file

        # logger.debug(f"Transcript handler initialized with " + logging and" if log_message else "file write"))

    def create_output_file(self):
        open(self._file_path, "a", encoding="utf-8").close()
            

    async def save_message(
        self,
        message: TranscriptionMessage
    ):
        timestamp = f"[{message.timestamp}] " if message.timestamp else ""
        line = f"{timestamp}{message.role}: {message.content}"
        data = {
            "type": "transcript_update",
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp,
        }
        self._write_line(line)
        await self._send_to_server(data)

    async def _send_to_server(
        self, 
        data: Dict
    ):
        json_payload = json.dumps(data)
        try:
            # Send the transcript data through the transport's websocket
            if self._transport_type == "websocket" and self._connection:
                await self._connection.send_text(json_payload)
                logger.debug(f"Sent transcript update to client: {json_payload}")
            elif hasattr(self._transport, "connection") and self._transport.connection:
                await self._transport.connection.send_text(json_payload)
                logger.debug(f"Sent transcript update to client: {json_payload}")
        except Exception as e:
            logger.error(f"Error sending transcript update to client: {e}")


    def _write_to_file(self, line: str):
        try:
            with open(self._file_path, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except Exception as e:
            logger.error(f"Failed to write to file: {e}")

    
    def _log_and_write(self, line: str):
        logger.info(line)
        self._write_to_file(line)


    async def on_transcript_update(
        self,
        processor: TranscriptProcessor,
        frame: TranscriptionUpdateFrame
    ):
        for msg in frame.messages:
            self.messages.append(msg)
            await self.save_message(msg)

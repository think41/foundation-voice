from typing import Dict, Optional
import logging
from pipecat.pipeline.task import PipelineTask

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, "PipelineTask"] = {}
        self.daily_room_sessions: Dict[str, "PipelineTask"] = {}
        self.webrtc_sessions: Dict[str, "PipelineTask"] = {}

    async def add_session(
        self, session_id: str, task: "PipelineTask", daily_room_url: str = None
    ):
        self.active_sessions[session_id] = task
        if daily_room_url:
            self.daily_room_sessions[daily_room_url] = task

    async def remove_session(self, session_id: str):
        """Remove session and clean up all related references."""
        try:
            if session_id in self.active_sessions:
                task = self.active_sessions[session_id]
                # Clean up daily room sessions if this task is associated with any
                for room_url, room_task in list(self.daily_room_sessions.items()):
                    if room_task == task:
                        del self.daily_room_sessions[room_url]
                        logger.info(f"Removed Daily room session: {room_url}")

                # Clean up from active sessions
                del self.active_sessions[session_id]
                logger.info(f"Removed active session: {session_id}")

        except Exception as e:
            logger.error(f"Error removing session {session_id}: {e}")

    def get_session(self, session_id: str) -> Optional["PipelineTask"]:
        return self.active_sessions.get(session_id)

    def get_daily_room_session(self, room_url: str) -> Optional["PipelineTask"]:
        return self.daily_room_sessions.get(room_url)

    def get_webrtc_session(self, pc_id: str) -> Optional["PipelineTask"]:
        return self.webrtc_sessions.get(pc_id)

    async def add_webrtc_session(self, pc_id: str, task: "PipelineTask"):
        self.webrtc_sessions[pc_id] = task
        self.active_sessions[pc_id] = task

    async def remove_webrtc_session(self, pc_id: str):
        """Remove WebRTC session and clean up all related references."""
        try:
            if pc_id in self.webrtc_sessions:
                del self.webrtc_sessions[pc_id]
                logger.info(f"Removed WebRTC session: {pc_id}")

                if pc_id in self.active_sessions:
                    del self.active_sessions[pc_id]
                    logger.info(f"Removed active session for WebRTC: {pc_id}")

        except Exception as e:
            logger.error(f"Error removing WebRTC session {pc_id}: {e}")


# Create a global session manager instance
session_manager = SessionManager()

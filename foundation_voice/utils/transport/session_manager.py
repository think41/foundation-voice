from typing import Dict, Optional
import logging
from pipecat.pipeline.task import PipelineTask
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SessionResumeData(BaseModel):
    """Data model for session resume information"""
    resume: bool
    data: Dict = {}  # Additional session data


class SessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, "PipelineTask"] = {}
        self.daily_room_sessions: Dict[str, "PipelineTask"] = {}
        self.webrtc_sessions: Dict[str, "PipelineTask"] = {}
        self._contexts: Dict = {}  # Store session contexts

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
                # Clean up contexts if they exist
                self._contexts.pop(session_id, None)
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
                    # Clean up contexts if they exist
                    self._contexts.pop(pc_id, None)
                    logger.info(f"Removed active session for WebRTC: {pc_id}")

        except Exception as e:
            logger.error(f"Error removing WebRTC session {pc_id}: {e}")

    def update_session_resume_data(self, contexts: Dict, session_id: str, session_resume: Optional[Dict] = None) -> Dict:
        try:
            if not session_resume:
                return contexts
            resume_data = SessionResumeData(
                resume=session_resume.get("resume", False),
                data=session_resume
            )
            if resume_data.resume:
                existing_data = contexts.get("session_resume_data", {"resume": True})
                existing_data.update(resume_data.data)
                contexts["session_resume_data"] = existing_data
                
            # Store the updated contexts
            self._contexts[session_id] = contexts
            return contexts
            
        except Exception as e:
            logger.error(f"Error updating session resume data: {e}")
            return contexts
            
    def get_session_contexts(self, session_id: str) -> Dict:
        """Returns the contexts for a specific session"""
        return self._contexts.get(session_id, {})


# Create a global session manager instance
session_manager = SessionManager()

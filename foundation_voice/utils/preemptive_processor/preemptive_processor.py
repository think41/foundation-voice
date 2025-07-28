import asyncio
import time
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMMessagesFrame,
    TTSSpeakFrame,
    BotInterruptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SimplePreemptiveState(Enum):
    IDLE = "idle"
    WAITING = "waiting"
    PLAYING = "playing"


@dataclass
class SimplePreemptiveSession:
    state: SimplePreemptiveState = SimplePreemptiveState.IDLE
    start_time: float = 0.0
    task: Optional[asyncio.Task] = None
    cancel_event: asyncio.Event = None
    
    def __post_init__(self):
        if self.cancel_event is None:
            self.cancel_event = asyncio.Event()


class SimplePreemptiveProcessor(FrameProcessor):
    """
    Simplified preemptive processor that injects filler phrases
    when LLM responses take too long.
    
    Position: After LLM, before TTS
    """
    
    def __init__(
        self,
        latency_threshold_ms: int = 300,
        phrases: list = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.latency_threshold_ms = latency_threshold_ms
        self.phrases = phrases or [
            "Let me think about that...",
            "Just a moment...",
            "I'm processing that...",
            "Give me a second...",
        ]
        
        self.current_session: Optional[SimplePreemptiveSession] = None
        self.user_speaking = False
        self.metrics = {"triggered": 0, "cancelled": 0}
        
        logger.info(f"🔧 Simple Preemptive Processor initialized (threshold: {latency_threshold_ms}ms)")
    
    async def _trigger_preemptive_after_delay(self, session: SimplePreemptiveSession):
        """Wait for threshold, then send preemptive phrase"""
        try:
            # Wait for the configured delay
            await asyncio.sleep(self.latency_threshold_ms / 1000.0)
            
            # Check if we should still proceed
            if session.cancel_event.is_set() or session.state != SimplePreemptiveState.WAITING:
                logger.info("❌ PREEMPTIVE: Cancelled before trigger")
                return
            
            # Select phrase and update state
            import random
            phrase = random.choice(self.phrases)
            session.state = SimplePreemptiveState.PLAYING
            
            logger.info(f"🎯 PREEMPTIVE: Triggering phrase: '{phrase}'")
            
            # Create and send TTS frame
            tts_frame = TTSSpeakFrame(text=phrase)
            await self.push_frame(tts_frame, FrameDirection.DOWNSTREAM)
            
            self.metrics["triggered"] += 1
            
            # Wait for cancellation (when real response arrives)
            await session.cancel_event.wait()
            
        except asyncio.CancelledError:
            logger.info("❌ PREEMPTIVE: Task cancelled")
        except Exception as e:
            logger.error(f"💥 PREEMPTIVE: Error: {e}")
    
    async def _start_session(self, reason: str = "unknown"):
        """Start a new preemptive session"""
        if self.user_speaking or self.current_session:
            return
        
        # Create new session
        self.current_session = SimplePreemptiveSession(
            state=SimplePreemptiveState.WAITING,
            start_time=time.time()
        )
        
        # Start the delay task
        self.current_session.task = asyncio.create_task(
            self._trigger_preemptive_after_delay(self.current_session)
        )
        
        logger.info(f"🚀 PREEMPTIVE: Started session (reason: {reason})")
    
    async def _cancel_session(self, reason: str = "unknown"):
        """Cancel current preemptive session"""
        if not self.current_session:
            return
        
        logger.info(f"🛑 PREEMPTIVE: Cancelling session (reason: {reason})")
        
        # Signal cancellation
        self.current_session.cancel_event.set()
        
        # Cancel task
        if self.current_session.task and not self.current_session.task.done():
            self.current_session.task.cancel()
            try:
                await self.current_session.task
            except asyncio.CancelledError:
                pass
        
        # Send interruption if we're currently playing
        if self.current_session.state == SimplePreemptiveState.PLAYING:
            await self.push_frame(BotInterruptionFrame(), FrameDirection.DOWNSTREAM)
            logger.info("🔇 PREEMPTIVE: Sent interruption frame")
        
        self.metrics["cancelled"] += 1
        self.current_session = None
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and manage preemptive responses"""
        frame_type = type(frame).__name__
        
        # Log key frames
        if frame_type in ["LLMMessagesFrame", "LLMFullResponseStartFrame", "LLMFullResponseEndFrame", 
                         "UserStartedSpeakingFrame", "UserStoppedSpeakingFrame", "TTSSpeakFrame"]:
            logger.info(f"🔍 PREEMPTIVE: {frame_type} ({direction.name})")
        
        # Handle user speech
        if isinstance(frame, UserStartedSpeakingFrame):
            self.user_speaking = True
            await self._cancel_session("user_speaking")
        
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self.user_speaking = False
        
        # Handle LLM processing start
        elif isinstance(frame, LLMMessagesFrame) and direction == FrameDirection.DOWNSTREAM:
            logger.info("🧠 PREEMPTIVE: LLM processing started")
            await self._start_session("llm_messages")
        
        # Handle LLM response start (cancel preemptive)
        elif isinstance(frame, LLMFullResponseStartFrame):
            logger.info("✨ PREEMPTIVE: LLM response ready, cancelling preemptive")
            await self._cancel_session("llm_response_ready")
        
        # Handle LLM response end (cleanup)
        elif isinstance(frame, LLMFullResponseEndFrame):
            logger.info("🏁 PREEMPTIVE: LLM response finished")
            await self._cancel_session("llm_response_end")
        
        # Pass frame through
        await super().process_frame(frame, direction)
    
    def get_metrics(self):
        """Get processor metrics"""
        return self.metrics.copy()
    
    async def cleanup(self):
        """Cleanup resources"""
        await self._cancel_session("cleanup")
        logger.info("🧹 PREEMPTIVE: Cleaned up")
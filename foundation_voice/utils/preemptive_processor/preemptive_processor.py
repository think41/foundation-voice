"""
Enhanced Preemptive Speech Processor compatible with ParallelPipeline

This version works within ParallelPipeline by using frames that ARE available
to the preemptive processor branch, rather than relying on LLM frames.
"""

import asyncio
import random
import time
import threading
from typing import Dict, List, Optional

from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    TranscriptionUpdateFrame,
    UserStoppedSpeakingFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from loguru import logger


class PreemptiveSpeechProcessor(FrameProcessor):
    def __init__(self, tts, threshold_ms=300, filler_config=None):
        super().__init__()
        self.tts = tts
        self.threshold = threshold_ms / 1000.0  # Convert to seconds
        self.filler_config = filler_config or {
            "default": [
                "Let me think about that...",
                "Just a moment...", 
                "Give me a second...",
                "I'm working on that...",
            ],
            "question": [
                "That's a great question, let me look that up...",
                "Interesting question, let me think...",
                "Let me find that information for you...",
            ],
            "calculation": [
                "Let me calculate that for you...",
                "Give me a moment to work this out...",
                "Let me crunch those numbers...",
            ]
        }
        
        # State tracking with thread safety
        self._lock = threading.Lock()
        self._preemptive_task: Optional[asyncio.Task] = None
        self._bot_speaking = False
        self._last_user_text = ""
        self._user_stopped_time: Optional[float] = None
        self._preemptive_triggered = False
        self._preemptive_playing = False
        self._task_id = 0  # Counter to track task generations
        self._last_preemptive_time: Optional[float] = None  # Track when last preemptive was triggered
        self._preemptive_cooldown = 3.0  # 3 second cooldown after preemptive response
        self._last_bot_speaking_time: Optional[float] = None  # Track bot speaking patterns
        
        logger.info(f"ParallelCompatiblePreemptiveProcessor initialized with {threshold_ms}ms threshold")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        user_text_captured = False
        # Try TranscriptionUpdateFrame first (most common)
        if isinstance(frame, TranscriptionUpdateFrame):
            for msg in frame.messages:
                if msg.role == "user":
                    user_input = msg.content
                    self._last_user_text = user_input
                    user_text_captured = True
                    logger.info(f"Transcription captured: '{self._last_user_text}' (direction: {direction})")

        # Also try TextFrame in case transcription comes as TextFrame
        elif isinstance(frame, TextFrame) and direction == FrameDirection.UPSTREAM:
            # Only capture if it doesn't look like a bot response
            if (frame.text and frame.text.strip() and 
                not getattr(frame, 'metadata', {}).get('preemptive', False)):
                self._last_user_text = frame.text.strip()
                user_text_captured = True
                logger.info(f"User text captured from TextFrame: '{self._last_user_text}'")

        # Track user input
        if isinstance(frame, UserStoppedSpeakingFrame):
            await self._handle_user_stopped_speaking()
            
        elif isinstance(frame, TranscriptionFrame) and direction == FrameDirection.UPSTREAM:
            self._last_user_text = frame.text
            logger.debug(f"Captured user text: '{self._last_user_text}'")
        
        # NOTE: LLMFullResponseStartFrame/EndFrame won't reach us in ParallelPipeline
        # So we use BotStartedSpeakingFrame as our LLM detection mechanism
        
        # Track bot speaking state and use it to detect LLM responses
        elif isinstance(frame, BotStartedSpeakingFrame):
            current_time = time.time()
            self._bot_speaking = True
            self._last_bot_speaking_time = current_time
            
            logger.info("Bot started speaking")
            
            # CRITICAL: Detect if this is likely an LLM response vs preemptive response
            time_since_user_stopped = (current_time - self._user_stopped_time 
                                     if self._user_stopped_time else float('inf'))
            
            # If bot starts speaking relatively soon after user stopped, it's likely LLM
            # Use a percentage of threshold to determine "soon"
            llm_detection_window = self.threshold * 0.9  # 90% of threshold
            
            if (self._preemptive_task and not self._preemptive_task.done() and 
                not self._preemptive_triggered and 
                time_since_user_stopped < llm_detection_window):
                
                logger.info(f"Early bot speaking detected ({time_since_user_stopped:.2f}s) - cancelling preemptive timer (LLM response)")
                await self._cancel_preemptive_task("Bot started speaking early (LLM response detected)")
                await self._log_preemptive_event("llm_detected_via_early_bot_speaking", {
                    "message": "LLM response detected via early bot speaking - cancelled preemptive",
                    "task_id": self._task_id,
                    "time_since_user_stopped": time_since_user_stopped,
                    "threshold_seconds": self.threshold,
                    "detection_window": llm_detection_window
                })
            
            await self._log_preemptive_event("bot_started_speaking", {
                "message": "Bot started speaking",
                "preemptive_triggered": self._preemptive_triggered,
                "preemptive_playing": self._preemptive_playing,
                "time_since_user_stopped": time_since_user_stopped,
                "likely_llm_response": time_since_user_stopped < llm_detection_window
            })
            
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            logger.info("Bot stopped speaking")
            
            await self._log_preemptive_event("bot_stopped_speaking", {
                "message": "Bot stopped speaking",
                "preemptive_triggered": self._preemptive_triggered,
                "preemptive_playing": self._preemptive_playing,
                "will_reset_state": not self._bot_speaking
            })
            
            # Add delay before resetting state to prevent immediate new timers
            await asyncio.sleep(0.2)  # 200ms buffer
            await self._reset_state()
            
        # Track TTS state to detect preemptive audio
        elif isinstance(frame, TTSStartedFrame):
            if self._preemptive_triggered:
                self._preemptive_playing = True
                logger.info("Preemptive TTS started")
                await self._log_preemptive_event("tts_started", {
                    "message": "Preemptive response TTS started",
                    "is_preemptive": True
                })
            else:
                logger.info("Regular TTS started")
                await self._log_preemptive_event("tts_started", {
                    "message": "Regular TTS started", 
                    "is_preemptive": False,
                    "preemptive_triggered": self._preemptive_triggered
                })
                
        elif isinstance(frame, TTSStoppedFrame):
            if self._preemptive_playing:
                self._preemptive_playing = False
                logger.info("Preemptive TTS stopped")
                await self._log_preemptive_event("tts_stopped", {
                    "message": "Preemptive response TTS completed",
                    "is_preemptive": True
                })
            else:
                logger.info("Regular TTS stopped")
                await self._log_preemptive_event("tts_stopped", {
                    "message": "Regular TTS stopped",
                    "is_preemptive": False
                })
            
        # Pass frame through
        await self.push_frame(frame, direction)

    async def _handle_user_stopped_speaking(self):
        """Handle when user stops speaking - start preemptive timer"""
        current_time = time.time()
        
        # Thread-safe state update
        with self._lock:
            # Ignore if we recently processed a UserStoppedSpeakingFrame
            if (self._user_stopped_time and 
                current_time - self._user_stopped_time < 0.1):  # 100ms debounce
                logger.debug("Ignoring duplicate UserStoppedSpeakingFrame within 100ms")
                return
            
            # Don't start new timer if we're already in preemptive mode
            if self._preemptive_triggered or self._preemptive_playing:
                logger.debug("Ignoring UserStoppedSpeakingFrame - already in preemptive mode")
                await self._log_preemptive_event("timer_blocked", {
                    "message": "New timer blocked - already in preemptive mode",
                    "preemptive_triggered": self._preemptive_triggered,
                    "preemptive_playing": self._preemptive_playing
                })
                return
            
            # Cooldown period after preemptive responses
            if (self._last_preemptive_time and 
                current_time - self._last_preemptive_time < self._preemptive_cooldown):
                remaining_cooldown = self._preemptive_cooldown - (current_time - self._last_preemptive_time)
                logger.debug(f"Ignoring UserStoppedSpeakingFrame - still in cooldown ({remaining_cooldown:.1f}s remaining)")
                await self._log_preemptive_event("timer_blocked", {
                    "message": f"New timer blocked - cooldown active ({remaining_cooldown:.1f}s remaining)",
                    "cooldown_remaining_seconds": remaining_cooldown,
                    "last_preemptive_time": self._last_preemptive_time
                })
                return
            
            # Also ignore if bot is currently speaking
            if self._bot_speaking:
                logger.debug("Ignoring UserStoppedSpeakingFrame - bot is speaking")
                await self._log_preemptive_event("timer_blocked", {
                    "message": "New timer blocked - bot is speaking",
                    "bot_speaking": self._bot_speaking
                })
                return
                
            self._user_stopped_time = current_time
        
        await self._reset_state()
        
        # Cancel any existing preemptive task with proper cleanup
        await self._cancel_preemptive_task("New user speech detected")
        
        # Start new preemptive timer with unique ID
        self._task_id += 1
        current_task_id = self._task_id
        self._preemptive_task = asyncio.create_task(
            self._preemptive_timer(current_task_id)
        )
        
        logger.debug(f"User stopped speaking, starting preemptive timer (ID: {current_task_id})")
        
        # Log to frontend
        await self._log_preemptive_event("timer_started", {
            "message": f"Preemptive timer started ({self.threshold * 1000:.0f}ms)",
            "threshold_ms": self.threshold * 1000,
            "user_text": self._last_user_text,
            "task_id": current_task_id
        })

    async def _reset_state(self):
        """Reset preemptive state for new interaction"""
        with self._lock:
            # Only reset if bot has actually stopped speaking
            if not self._bot_speaking:
                old_triggered = self._preemptive_triggered
                old_playing = self._preemptive_playing
                
                self._preemptive_triggered = False
                self._preemptive_playing = False
                
                logger.info(f"Preemptive state reset - ready for new interaction "
                          f"(was: triggered={old_triggered}, playing={old_playing})")
                
                await self._log_preemptive_event("state_reset", {
                    "message": "Preemptive state reset - ready for new interaction",
                    "previous_triggered": old_triggered,
                    "previous_playing": old_playing,
                    "bot_speaking": self._bot_speaking
                })
            else:
                logger.debug("State reset skipped - bot still speaking")

    async def _preemptive_timer(self, task_id: int):
        """Timer that triggers preemptive response after threshold"""
        try:
            logger.debug(f"Preemptive timer {task_id} sleeping for {self.threshold}s")
            await asyncio.sleep(self.threshold)
            
            # Check if this task is still the current one
            if self._preemptive_task is None or task_id != self._task_id:
                logger.debug(f"Timer {task_id} obsolete, not triggering")
                return
            
            # CRITICAL: Double-check all conditions before triggering
            if self._bot_speaking:
                logger.debug(f"Timer {task_id} completed but bot is speaking - not triggering")
                await self._log_preemptive_event("timer_completed_no_trigger", {
                    "message": "Timer completed but bot is speaking", 
                    "task_id": task_id,
                    "reason": "bot_speaking"
                })
                return
                
            if self._preemptive_triggered:
                logger.debug(f"Timer {task_id} completed but preemptive already triggered - not triggering")
                await self._log_preemptive_event("timer_completed_no_trigger", {
                    "message": "Timer completed but preemptive already triggered",
                    "task_id": task_id,
                    "reason": "already_triggered"
                })
                return
            
            # Additional check: If bot spoke recently (within 1 second), don't trigger
            # This catches cases where LLM response finished just before our timer
            if (self._last_bot_speaking_time and 
                time.time() - self._last_bot_speaking_time < 1.0):
                logger.debug(f"Timer {task_id} completed but bot spoke recently - not triggering")
                await self._log_preemptive_event("timer_completed_no_trigger", {
                    "message": "Timer completed but bot spoke recently",
                    "task_id": task_id,
                    "reason": "recent_bot_speaking",
                    "seconds_since_bot_spoke": time.time() - self._last_bot_speaking_time
                })
                return
            
            # All conditions met - trigger preemptive response
            await self._trigger_preemptive(task_id)
                
        except asyncio.CancelledError:
            logger.debug(f"Preemptive timer {task_id} cancelled")
            await self._log_preemptive_event("timer_cancelled", {
                "message": f"Preemptive timer {task_id} cancelled",
                "task_id": task_id,
                "reason": "task_cancelled"
            })
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            logger.error(f"Error in preemptive timer {task_id}: {e}")
            await self._log_preemptive_event("timer_error", {
                "message": f"Error in preemptive timer {task_id}: {str(e)}",
                "task_id": task_id,
                "error": str(e)
            })

    async def _trigger_preemptive(self, task_id: int):
        """Trigger the preemptive response"""
        with self._lock:
            if self._preemptive_triggered:
                logger.debug(f"Preemptive already triggered, ignoring task {task_id}")
                return
            self._preemptive_triggered = True
            self._last_preemptive_time = time.time()  # Record when preemptive was triggered
        
        # Select appropriate phrase
        intent = self._infer_intent(self._last_user_text)
        phrases = self.filler_config.get(intent, self.filler_config["default"])
        phrase = random.choice(phrases)
        
        logger.info(f"Triggering preemptive response (task {task_id}): '{phrase}' (intent: {intent})")
        
        # Calculate actual delay
        actual_delay = (time.time() - self._user_stopped_time) * 1000 if self._user_stopped_time else 0
        
        # Log preemptive trigger to frontend
        await self._log_preemptive_event("triggered", {
            "message": "Preemptive response triggered",
            "phrase": phrase,
            "intent": intent,  
            "user_text": self._last_user_text,
            "task_id": task_id,
            "expected_delay_ms": self.threshold * 1000,
            "actual_delay_ms": actual_delay
        })
        
        try:
            # Create frame with metadata
            text_frame = TextFrame(text=phrase)
            text_frame.metadata = {"preemptive": True, "task_id": task_id}

            # Send downstream to TTS (for speaking)
            await self.push_frame(text_frame, FrameDirection.DOWNSTREAM)

            logger.info(f"Preemptive response generated (task {task_id}): {text_frame.text}")
            
            # Log successful generation
            await self._log_preemptive_event("generated", {
                "message": "Preemptive response sent to TTS",
                "text": phrase,
                "task_id": task_id,
                "metadata": text_frame.metadata
            })
            
        except Exception as e:
            logger.error(f"Error triggering preemptive response (task {task_id}): {e}")
            await self._log_preemptive_event("error", {
                "message": f"Failed to generate preemptive response: {str(e)}",
                "task_id": task_id,
                "error": str(e),
                "phrase": phrase
            })

    async def _cancel_preemptive_task(self, reason: str = "Unknown"):
        """Cancel any active preemptive task with proper cleanup"""
        if self._preemptive_task and not self._preemptive_task.done():
            task_to_cancel = self._preemptive_task
            self._preemptive_task = None  # Clear reference immediately
            
            try:
                task_to_cancel.cancel()
                # Wait a moment for the task to actually cancel
                await asyncio.sleep(0.01)
                logger.debug(f"Preemptive task cancelled: {reason}")
            except Exception as e:
                logger.error(f"Error cancelling preemptive task: {e}")

    
    def _infer_intent(self, text: str) -> str:
        """Simple intent detection based on keywords"""
        if not text:
            return "default"
            
        text_lower = text.lower()
        
        # Question detection - check first since questions might also contain calc words
        question_indicators = ["what", "how", "why", "when", "where", "who", "which", "can you", "could you", "would you"]
        if any(indicator in text_lower for indicator in question_indicators) or text_lower.endswith("?"):
            # But if it's a calculation question, prioritize calculation
            calc_question_indicators = ["what is", "how much", "calculate", "compute", "add", "subtract", "multiply", "divide", "equals", "+", "-", "*", "/", "×", "÷"]
            if any(indicator in text_lower for indicator in calc_question_indicators):
                return "calculation"
            return "question"
        
        # Calculation detection - more comprehensive patterns
        calc_indicators = [
            "calculate", "compute", "add", "subtract", "multiply", "divide", 
            "sum", "total", "equals", "plus", "minus", "times", "divided by",
            "+", "-", "*", "/", "×", "÷", "=",
            # Number patterns
            "percent", "%", "percentage", "square", "cube", "power",
            # Math operations
            "average", "mean", "median", "mode", "standard deviation"
        ]
        
        # Check for calculation indicators
        if any(indicator in text_lower for indicator in calc_indicators):
            return "calculation"
        
        # Check for number patterns (sequences of digits)
        import re
        if re.search(r'\d+', text_lower):
            # If text contains numbers and math-related words, it's likely calculation
            math_context_words = ["and", "plus", "minus", "times", "divided", "equals", "is", "of", "percent"]
            if any(word in text_lower for word in math_context_words):
                return "calculation"
        
        return "default"

    async def _log_preemptive_event(self, event_type: str, data: Dict):
        """Send preemptive logging events to the frontend via RTVI server messages"""
        log_data = {
            "type": "preemptive_log",
            "event": event_type,
            "timestamp": time.time(),
            "data": data
        }
        
        # Create RTVI server message frame to send to frontend
        server_message_frame = RTVIServerMessageFrame(data=log_data)
        await self.push_frame(server_message_frame, FrameDirection.DOWNSTREAM)
        
        # Also log locally for server-side debugging
        logger.info(f"Preemptive event [{event_type}]: {data.get('message', '')}")

    def get_debug_info(self) -> Dict:
        """Get current state for debugging"""
        with self._lock:
            return {
                "threshold_ms": self.threshold * 1000,
                "bot_speaking": self._bot_speaking,
                "last_user_text": self._last_user_text,
                "preemptive_triggered": self._preemptive_triggered,
                "preemptive_playing": self._preemptive_playing,
                "has_active_task": self._preemptive_task is not None and not self._preemptive_task.done(),
                "user_stopped_time": self._user_stopped_time,
                "current_task_id": self._task_id,
                "task_reference_exists": self._preemptive_task is not None,
                "last_preemptive_time": self._last_preemptive_time,
                "cooldown_remaining": (self._preemptive_cooldown - (time.time() - self._last_preemptive_time)) if self._last_preemptive_time else 0,
                "last_bot_speaking_time": self._last_bot_speaking_time,
            }
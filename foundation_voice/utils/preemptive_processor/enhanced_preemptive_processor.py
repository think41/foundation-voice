# import asyncio
# import time
# import random
# from typing import Dict, List, Optional, Any, Callable
# from dataclasses import dataclass, field
# from enum import Enum

# from loguru import logger
# from pipecat.frames.frames import (
#     Frame,
#     TextFrame,
#     TranscriptionFrame,
#     UserStartedSpeakingFrame,
#     UserStoppedSpeakingFrame,
#     LLMFullResponseStartFrame,
#     LLMFullResponseEndFrame,
#     LLMMessagesFrame,
#     BotStartedSpeakingFrame,
#     BotStoppedSpeakingFrame,
#     TTSStartedFrame,
#     TTSStoppedFrame,
#     TTSSpeakFrame,
#     BotInterruptionFrame,
#     CancelFrame,
#     StartInterruptionFrame,
#     StopInterruptionFrame,
#     EndFrame,
# )
# from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


# class PreemptiveState(Enum):
#     IDLE = "idle"
#     WAITING = "waiting"
#     PLAYING = "playing"
#     CANCELLED = "cancelled"


# @dataclass
# class PreemptiveConfig:
#     """Configuration for preemptive responses"""
#     # Global settings
#     enabled: bool = True
#     latency_threshold_ms: int = 300
#     max_preemptive_duration_ms: int = 3000
    
#     # Global preemptive phrases
#     global_phrases: List[str] = field(default_factory=lambda: [
#         "Let me check that for you...",
#         "Just a moment...",
#         "I'm thinking about that...",
#         "Give me a second...",
#         "Let me process that...",
#     ])
    
#     # Intent-specific phrases (context-aware)
#     intent_phrases: Dict[str, List[str]] = field(default_factory=lambda: {
#         "question": [
#             "Let me think about that...",
#             "That's a good question...",
#             "I need to consider that...",
#         ],
#         "request": [
#             "I'll help you with that...",
#             "Let me take care of that...",
#             "Working on that for you...",
#         ],
#         "search": [
#             "Let me search for that...",
#             "Looking that up...",
#             "Searching for information...",
#         ],
#         "calculation": [
#             "Let me calculate that...",
#             "Running the numbers...",
#             "Computing that for you...",
#         ],
#         "default": [
#             "Just a moment...",
#             "Processing...",
#             "One second...",
#         ]
#     })
    
#     # Fallback behavior
#     skip_if_quick_response: bool = True
#     quick_response_threshold_ms: int = 150
    
#     # TTS settings for preemptive responses
#     preemptive_tts_voice: Optional[str] = None
#     preemptive_tts_speed: float = 1.1  # Slightly faster for fillers
#     preemptive_tts_volume: float = 0.9  # Slightly quieter


# @dataclass
# class PreemptiveSession:
#     """Tracks the state of a preemptive response session"""
#     state: PreemptiveState = PreemptiveState.IDLE
#     start_time: float = 0.0
#     phrase_used: Optional[str] = None
#     intent: Optional[str] = None
#     preemptive_task: Optional[asyncio.Task] = None
#     actual_response_started: bool = False
#     cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


# class EnhancedPreemptiveProcessor(FrameProcessor):
#     """
#     Enhanced preemptive processor that provides configurable filler phrases
#     to reduce perceived latency in voice interactions.
#     """
    
#     def __init__(
#         self,
#         config: Optional[PreemptiveConfig] = None,
#         tts_processor: Optional[Any] = None,
#         intent_classifier: Optional[Callable[[str], str]] = None,
#         **kwargs
#     ):
#         super().__init__(**kwargs)
#         self.config = config or PreemptiveConfig()
#         self.tts_processor = tts_processor
#         self.intent_classifier = intent_classifier or self._default_intent_classifier
        
#         # Session tracking
#         self.current_session: Optional[PreemptiveSession] = None
#         self.last_user_input: Optional[str] = None
#         self.user_speaking = False
#         self.bot_speaking = False
#         self.waiting_for_llm = False  # Track if we're waiting for LLM response
        
#         # Track preemptive phrases to identify them later
#         self.active_preemptive_phrases: set = set()
#         self.preemptive_playing = False
        
#         # Metrics
#         self.metrics = {
#             "preemptive_triggered": 0,
#             "preemptive_cancelled": 0,
#             "preemptive_completed": 0,
#             "avg_trigger_latency": 0.0,
#             "latency_samples": []
#         }
        
#         logger.info(f"🔧 Enhanced Preemptive Processor initialized with threshold: {self.config.latency_threshold_ms}ms")
    
#     def _is_preemptive_tts(self, frame) -> bool:
#         """Check if a TTS frame is preemptive by examining its text content"""
#         if not hasattr(frame, 'text') or not frame.text:
#             return False
        
#         # Check if the text matches any of our active preemptive phrases
#         frame_text = frame.text.strip()
#         return frame_text in self.active_preemptive_phrases
    
#     def _default_intent_classifier(self, text: str) -> str:
#         """Simple intent classification based on keywords"""
#         text_lower = text.lower()
        
#         # Question patterns
#         if any(word in text_lower for word in ["what", "how", "why", "when", "where", "who", "?"]):
#             return "question"
        
#         # Request patterns
#         if any(word in text_lower for word in ["please", "can you", "could you", "help", "do"]):
#             return "request"
        
#         # Search patterns
#         if any(word in text_lower for word in ["find", "search", "look up", "tell me about"]):
#             return "search"
        
#         # Calculation patterns
#         if any(word in text_lower for word in ["calculate", "compute", "add", "subtract", "multiply", "divide", "math"]):
#             return "calculation"
        
#         return "default"
    
#     def _select_preemptive_phrase(self, intent: str) -> str:
#         """Select an appropriate preemptive phrase based on intent"""
#         # Try intent-specific phrases first
#         if intent in self.config.intent_phrases:
#             phrases = self.config.intent_phrases[intent]
#         else:
#             # Fallback to default intent phrases, then global phrases
#             phrases = (self.config.intent_phrases.get("default", []) + 
#                       self.config.global_phrases)
        
#         if not phrases:
#             phrases = ["Just a moment..."]
        
#         return random.choice(phrases)
    
#     async def _trigger_preemptive_response(self, session: PreemptiveSession):
#         """Trigger a preemptive response after the configured delay"""
#         try:
#             logger.debug(f"⏱️ Waiting {self.config.latency_threshold_ms}ms before triggering preemptive response...")
            
#             # Wait for the latency threshold
#             await asyncio.sleep(self.config.latency_threshold_ms / 1000.0)
            
#             # Check if we should still proceed
#             if (session.cancel_event.is_set() or 
#                 session.actual_response_started or 
#                 session.state != PreemptiveState.WAITING):
#                 logger.debug("❌ Preemptive response cancelled before trigger")
#                 session.state = PreemptiveState.CANCELLED
#                 self.metrics["preemptive_cancelled"] += 1
#                 return
            
#             # Select and trigger preemptive phrase
#             phrase = self._select_preemptive_phrase(session.intent or "default")
#             session.phrase_used = phrase
#             session.state = PreemptiveState.PLAYING
            
#             # Track this phrase as preemptive
#             self.active_preemptive_phrases.add(phrase)
#             self.preemptive_playing = True
            
#             logger.info(f"🎯 Triggering preemptive response: '{phrase}' (intent: {session.intent})")
            
#             await self.push_frame( TextFrame(role="assistant", content=phrase), FrameDirection.DOWNSTREAM )
            
#             # Update metrics
#             self.metrics["preemptive_triggered"] += 1
#             trigger_latency = (time.time() - session.start_time) * 1000
#             self.metrics["latency_samples"].append(trigger_latency)
            
#             # Update average latency
#             if self.metrics["latency_samples"]:
#                 self.metrics["avg_trigger_latency"] = sum(self.metrics["latency_samples"]) / len(self.metrics["latency_samples"])
            
#             logger.info(f"📊 Preemptive triggered! Latency: {trigger_latency:.1f}ms, Total triggered: {self.metrics['preemptive_triggered']}")
            
#             # Wait for maximum duration or cancellation
#             try:
#                 await asyncio.wait_for(
#                     session.cancel_event.wait(),
#                     timeout=self.config.max_preemptive_duration_ms / 1000.0
#                 )
#             except asyncio.TimeoutError:
#                 logger.warning("⚠️ Preemptive response reached maximum duration")
#                 # Clean up the phrase tracking
#                 self.active_preemptive_phrases.discard(phrase)
#                 self.preemptive_playing = False
            
#         except asyncio.CancelledError:
#             logger.debug("❌ Preemptive response task was cancelled")
#             session.state = PreemptiveState.CANCELLED
#             self.metrics["preemptive_cancelled"] += 1
#             # Clean up tracking
#             if session.phrase_used:
#                 self.active_preemptive_phrases.discard(session.phrase_used)
#             self.preemptive_playing = False
#         except Exception as e:
#             logger.error(f"💥 Error in preemptive response: {e}")
#             session.state = PreemptiveState.CANCELLED
#             # Clean up tracking
#             if session.phrase_used:
#                 self.active_preemptive_phrases.discard(session.phrase_used)
#             self.preemptive_playing = False
    
#     async def _start_preemptive_session(self, user_input: str = ""):
#         """Start a new preemptive response session"""
#         if not self.config.enabled or self.bot_speaking:
#             logger.debug(f"🚫 Preemptive session not started - enabled: {self.config.enabled}, bot_speaking: {self.bot_speaking}")
#             return
        
#         # Cancel any existing session
#         await self._cancel_current_session("new_session")
        
#         # Classify intent
#         intent = self.intent_classifier(user_input) if user_input else "default"
        
#         # Create new session
#         self.current_session = PreemptiveSession(
#             state=PreemptiveState.WAITING,
#             start_time=time.time(),
#             intent=intent
#         )
        
#         # Mark that we're waiting for LLM
#         self.waiting_for_llm = True
        
#         # Start preemptive task
#         self.current_session.preemptive_task = asyncio.create_task(
#             self._trigger_preemptive_response(self.current_session)
#         )
        
#         logger.info(f"🚀 Started preemptive session with intent: {intent}, input: '{user_input[:50]}...'")
    
#     async def _cancel_current_session(self, reason: str = "new_session"):
#         """Cancel the current preemptive session"""
#         if not self.current_session:
#             return
        
#         logger.debug(f"🛑 Cancelling preemptive session: {reason}")
        
#         # Set cancel event
#         self.current_session.cancel_event.set()
        
#         # Cancel task
#         if self.current_session.preemptive_task and not self.current_session.preemptive_task.done():
#             self.current_session.preemptive_task.cancel()
#             try:
#                 await self.current_session.preemptive_task
#             except asyncio.CancelledError:
#                 pass
        
#         # Send interruption if currently playing
#         if self.current_session.state == PreemptiveState.PLAYING:
#             await self.push_frame(BotInterruptionFrame(), FrameDirection.DOWNSTREAM)
#             logger.debug("🔇 Sent bot interruption frame to stop preemptive TTS")
        
#         # Clean up phrase tracking
#         if self.current_session.phrase_used:
#             self.active_preemptive_phrases.discard(self.current_session.phrase_used)
#         self.preemptive_playing = False
        
#         # Update metrics
#         if self.current_session.state == PreemptiveState.PLAYING:
#             self.metrics["preemptive_completed"] += 1
        
#         self.current_session = None
#         self.waiting_for_llm = False
    
#     async def _handle_quick_response(self) -> bool:
#         """Check if response is quick enough to skip preemptive"""
#         if not self.config.skip_if_quick_response or not self.current_session:
#             return False
        
#         elapsed_ms = (time.time() - self.current_session.start_time) * 1000
        
#         if elapsed_ms < self.config.quick_response_threshold_ms:
#             logger.debug(f"⚡ Quick response detected ({elapsed_ms:.1f}ms), skipping preemptive")
#             await self._cancel_current_session("quick_response")
#             return True
        
#         return False
    
#     # Frame Processing Methods
    
#     async def process_frame(self, frame: Frame, direction: FrameDirection):
#         """Main frame processing logic"""
#         # Log frame types for debugging
#         # Intercept user‐input frames before they go downstream
#         if direction == FrameDirection.UPSTREAM and isinstance(frame, (TextFrame, TranscriptionFrame)):
#             text = getattr(frame, "text", None) or getattr(frame, "transcript", "")
#             self.last_user_input = text
#             logger.info(f"📝 User input received: '{text}' → starting preemptive")
#             if not self.user_speaking and not self.bot_speaking:
#                 await self._start_preemptive_session(text)

#         # 2) Let the base class link this frame downstream/upstream
#         frame_type = type(frame).__name__
#         await super().process_frame(frame, direction)

        
#         # Handle LLM Messages frame (when LLM is about to process)
#         if isinstance(frame, LLMMessagesFrame) and direction == FrameDirection.DOWNSTREAM:
#             logger.info("🧠 LLM Messages frame detected - LLM is processing")
#             if not self.waiting_for_llm and not self.current_session:
#                 # If no preemptive session started yet, start one now
#                 await self._start_preemptive_session(self.last_user_input or "")
        
#         # Handle LLM response frames
#         elif isinstance(frame, LLMFullResponseStartFrame):
#             logger.info("✨ LLM response started - cancelling preemptive")
#             if self.current_session:
#                 self.current_session.actual_response_started = True
                
#                 # Check for quick response
#                 if await self._handle_quick_response():
#                     pass  # Preemptive was cancelled
#                 else:
#                     # Cancel preemptive as actual response is ready
#                     await self._cancel_current_session("actual_response_ready")
        
#         # Handle LLM response end - reset state
#         elif isinstance(frame, LLMFullResponseEndFrame):
#             logger.debug("🏁 LLM response ended")
#             if self.current_session:
#                 await self._cancel_current_session("llm_response_ended")
        
#         # Handle Bot/TTS events
#         elif isinstance(frame, (BotStartedSpeakingFrame, TTSStartedFrame)):
#             # Check if this might be our preemptive TTS by checking if we're in preemptive mode
#             # and if there are active preemptive phrases
#             if self.preemptive_playing and self.active_preemptive_phrases:
#                 logger.info("🎤 Preemptive TTS started playing")
#             else:
#                 logger.info("🎤 Bot started speaking (non-preemptive)")
#                 self.bot_speaking = True
#                 await self._cancel_current_session("bot_started_speaking")
        
#         elif isinstance(frame, (BotStoppedSpeakingFrame, TTSStoppedFrame)):
#             # Check if this was our preemptive TTS ending
#             if self.preemptive_playing and self.active_preemptive_phrases:
#                 logger.info("🎤 Preemptive TTS finished playing")
#                 self.preemptive_playing = False
#                 # Clear the active phrases
#                 self.active_preemptive_phrases.clear()
#                 if self.current_session:
#                     self.current_session.state = PreemptiveState.IDLE
#             else:
#                 logger.info("🎤 Bot stopped speaking (non-preemptive)")
#                 self.bot_speaking = False
        
#         # Handle interruption frames
#         elif isinstance(frame, (BotInterruptionFrame, StartInterruptionFrame, StopInterruptionFrame)):
#             logger.debug("🚫 Interruption frame received")
#             await self._cancel_current_session("interruption")
        
#         # Handle cancel and end frames
#         elif isinstance(frame, (CancelFrame, EndFrame)):
#             logger.debug("🛑 Cancel/End frame received")
#             await self._cancel_current_session("cancel_or_end_frame")
        
#         # Pass frame downstream/upstream
#         await self.push_frame(frame, direction)
    
#     # Utility Methods
    
#     def get_metrics(self) -> Dict[str, Any]:
#         """Get processor metrics"""
#         return self.metrics.copy()
    
#     def reset_metrics(self):
#         """Reset processor metrics"""
#         self.metrics = {
#             "preemptive_triggered": 0,
#             "preemptive_cancelled": 0,
#             "preemptive_completed": 0,
#             "avg_trigger_latency": 0.0,
#             "latency_samples": []
#         }
    
#     def update_config(self, new_config: PreemptiveConfig):
#         """Update processor configuration"""
#         self.config = new_config
#         logger.info(f"⚙️ Updated preemptive processor config, threshold: {self.config.latency_threshold_ms}ms")
    
#     async def cleanup(self):
#         """Cleanup resources"""
#         await self._cancel_current_session("cleanup")
#         logger.info("🧹 Enhanced Preemptive Processor cleaned up")




# """
# Conservative Preemptive Speech Processor

# This version uses only the most basic frame types that should be available
# in all Pipecat versions, and relies on timing instead of LLM frame detection.
# """

# """
# Fixed Preemptive Speech Processor

# Key fixes:
# 1. Proper frame handling and flow control
# 2. Better state management
# 3. Improved timing logic
# 4. More robust error handling
# 5. Direct TTS integration
# """

# import asyncio
# import random
# import time
# from typing import Dict, List, Optional

# from pipecat.frames.frames import (
#     Frame,
#     TextFrame,
#     TranscriptionFrame,
#     UserStoppedSpeakingFrame,
#     LLMFullResponseStartFrame,
#     LLMFullResponseEndFrame,
#     BotStartedSpeakingFrame,
#     BotStoppedSpeakingFrame,
#     TTSStartedFrame,
#     TTSStoppedFrame,
#     EndFrame,
# )
# from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
# from loguru import logger


# class PreemptiveSpeechProcessor(FrameProcessor):
#     def __init__(self, tts, threshold_ms=500, filler_config=None):
#         super().__init__()
#         self.tts = tts
#         self.threshold = threshold_ms / 1000.0  # Convert to seconds
#         self.filler_config = filler_config or {
#             "default": [
#                 "Let me think about that...",
#                 "Just a moment...", 
#                 "Give me a second...",
#                 "I'm working on that...",
#             ],
#             "question": [
#                 "That's a great question, let me look that up...",
#                 "Interesting question, let me think...",
#                 "Let me find that information for you...",
#             ],
#             "calculation": [
#                 "Let me calculate that for you...",
#                 "Give me a moment to work this out...",
#                 "Let me crunch those numbers...",
#             ]
#         }
        
#         # State tracking
#         self._preemptive_task: Optional[asyncio.Task] = None
#         self._bot_speaking = False
#         self._llm_responding = False
#         self._last_user_text = ""
#         self._user_stopped_time: Optional[float] = None
#         self._preemptive_triggered = False
#         self._preemptive_playing = False
#         self._waiting_for_llm = False
        
#         logger.info(f"🎯 PreemptiveSpeechProcessor initialized with {threshold_ms}ms threshold")

#     async def process_frame(self, frame: Frame, direction: FrameDirection):
#         # Handle the frame first
#         frame_handled = False
        
#         try:
#             # Track user input and transcription
#             if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.UPSTREAM:
#                 self._last_user_text = frame.text
#                 logger.debug(f"📝 Captured user text: '{self._last_user_text}'")
                
#             elif isinstance(frame, UserStoppedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
#                 await self._handle_user_stopped_speaking()
                
#             # Track LLM response lifecycle
#             elif isinstance(frame, LLMFullResponseStartFrame):
#                 logger.debug("🧠 LLM response started")
#                 self._llm_responding = True
#                 self._waiting_for_llm = False
#                 await self._cancel_preemptive_if_active()
                
#             elif isinstance(frame, LLMFullResponseEndFrame):
#                 logger.debug("🧠 LLM response ended")
#                 self._llm_responding = False
            
#             # Track bot speaking state
#             elif isinstance(frame, BotStartedSpeakingFrame):
#                 logger.debug("🗣️ Bot started speaking")
#                 self._bot_speaking = True
                
#             elif isinstance(frame, BotStoppedSpeakingFrame):
#                 logger.debug("🗣️ Bot stopped speaking")
#                 self._bot_speaking = False
#                 await self._reset_state()
                
#             # Track TTS state
#             elif isinstance(frame, TTSStartedFrame):
#                 if self._preemptive_triggered and not self._llm_responding:
#                     self._preemptive_playing = True
#                     logger.debug("🎵 Preemptive TTS started")
                    
#             elif isinstance(frame, TTSStoppedFrame):
#                 if self._preemptive_playing:
#                     self._preemptive_playing = False
#                     logger.debug("🎵 Preemptive TTS stopped")
            
#             # Always call super().process_frame() first
#             await super().process_frame(frame, direction)
            
#             # Then push the frame downstream
#             await self.push_frame(frame, direction)
#             frame_handled = True
            
#         except Exception as e:
#             logger.error(f"❌ Error processing frame {type(frame).__name__}: {e}")
#             if not frame_handled:
#                 # Still try to pass the frame through
#                 await super().process_frame(frame, direction)
#                 await self.push_frame(frame, direction)

#     async def _handle_user_stopped_speaking(self):
#         """Handle when user stops speaking - start preemptive timer"""
#         current_time = time.time()
#         self._user_stopped_time = current_time
        
#         # Reset state for new interaction
#         await self._reset_state()
#         self._waiting_for_llm = True
        
#         # Cancel any existing preemptive task
#         await self._cancel_preemptive_if_active()
        
#         # Start new preemptive timer
#         self._preemptive_task = asyncio.create_task(self._preemptive_timer())
#         logger.debug(f"⏱️ User stopped speaking, starting preemptive timer (threshold: {self.threshold}s)")

#     async def _reset_state(self):
#         """Reset preemptive state for new interaction"""
#         self._preemptive_triggered = False
#         self._preemptive_playing = False
#         self._waiting_for_llm = False
#         logger.debug("🔄 Reset preemptive state")

#     async def _preemptive_timer(self):
#         """Timer that triggers preemptive response after threshold"""
#         try:
#             logger.debug(f"⏳ Preemptive timer started, waiting {self.threshold}s...")
#             await asyncio.sleep(self.threshold)
            
#             # Check if we should still trigger preemptive response
#             should_trigger = (
#                 self._waiting_for_llm and
#                 not self._llm_responding and 
#                 not self._bot_speaking and 
#                 not self._preemptive_triggered
#             )
            
#             if should_trigger:
#                 logger.info("🚀 Triggering preemptive response - LLM taking too long")
#                 await self._trigger_preemptive()
#             else:
#                 logger.debug(f"⏹️ Not triggering preemptive: waiting={self._waiting_for_llm}, llm_responding={self._llm_responding}, bot_speaking={self._bot_speaking}, already_triggered={self._preemptive_triggered}")
                
#         except asyncio.CancelledError:
#             logger.debug("⏹️ Preemptive timer cancelled")
#         except Exception as e:
#             logger.error(f"❌ Error in preemptive timer: {e}")

#     async def _trigger_preemptive(self):
#         """Trigger the preemptive response"""
#         if self._preemptive_triggered:
#             logger.debug("⚠️ Preemptive already triggered, skipping")
#             return
            
#         self._preemptive_triggered = True
        
#         # Select appropriate phrase
#         intent = self._infer_intent(self._last_user_text)
#         phrases = self.filler_config.get(intent, self.filler_config["default"])
#         phrase = random.choice(phrases)
        
#         logger.info(f"✨ Triggering preemptive response: '{phrase}' (intent: {intent})")
        
#         try:
#             # Create and push TextFrame downstream to TTS
#             text_frame = TextFrame(text=phrase)
            
#             # Push frame downstream toward TTS
#             await self.push_frame(text_frame, FrameDirection.DOWNSTREAM)
            
#             logger.info(f"🎯 Preemptive response sent to TTS: '{phrase}'")

#         except Exception as e:
#             logger.error(f"❌ Error triggering preemptive response: {e}")
#             self._preemptive_triggered = False  # Reset on error

#     async def _cancel_preemptive_if_active(self):
#         """Cancel any active preemptive task"""
#         if self._preemptive_task and not self._preemptive_task.done():
#             self._preemptive_task.cancel()
#             logger.debug("🛑 Preemptive task cancelled")
            
#         # If preemptive is currently playing, we might want to interrupt it
#         if self._preemptive_playing:
#             logger.debug("🛑 Preemptive was playing, marking as interrupted")
#             self._preemptive_playing = False

#     def _infer_intent(self, text: str) -> str:
#         """Simple intent detection based on keywords"""
#         if not text:
#             return "default"
            
#         text_lower = text.lower().strip()
        
#         # Question detection
#         question_indicators = ["what", "how", "why", "when", "where", "who", "which", "can you", "could you", "would you", "do you"]
#         if text_lower.endswith("?") or any(text_lower.startswith(indicator) for indicator in question_indicators):
#             return "question"
            
#         # Calculation detection  
#         calc_indicators = ["calculate", "compute", "math", "number", "sum", "total", "add", "subtract", "multiply", "divide"]
#         if any(indicator in text_lower for indicator in calc_indicators):
#             return "calculation"
            
#         return "default"

#     def get_debug_info(self) -> Dict:
#         """Get current state for debugging"""
#         return {
#             "threshold_ms": self.threshold * 1000,
#             "bot_speaking": self._bot_speaking,
#             "llm_responding": self._llm_responding,
#             "waiting_for_llm": self._waiting_for_llm,
#             "last_user_text": self._last_user_text,
#             "preemptive_triggered": self._preemptive_triggered,
#             "preemptive_playing": self._preemptive_playing,
#             "has_active_task": self._preemptive_task is not None and not self._preemptive_task.done(),
#             "user_stopped_time": self._user_stopped_time,
#         }

#     async def cleanup(self):
#         """Clean up resources"""
#         await self._cancel_preemptive_if_active()
#         await self._reset_state()




# import asyncio
# from loguru import logger
# from pipecat.frames.frames import (
#     LLMMessagesFrame, 
#     TextFrame, 
#     TranscriptionFrame, 
#     StartFrame, 
#     EndFrame,
#     AudioRawFrame,
#     Frame
# )
# from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
# import random
# import time

# class PreemptiveResponseProcessor(FrameProcessor):
#     def __init__(self, 
#                  tts_service,
#                  *,
#                  delay_threshold_ms: int = 500,  # Trigger after 500ms of no LLM response
#                  preemptive_phrases: list = None,
#                  **kwargs):
#         """
#         Processor that generates immediate preemptive responses when user stops speaking,
#         before the actual LLM response is ready.
        
#         Args:
#             tts_service: TTS service to generate preemptive audio
#             delay_threshold_ms: Time to wait before triggering preemptive response
#             preemptive_phrases: List of phrases to use for preemptive responses
#         """
#         super().__init__(**kwargs)
#         self.tts_service = tts_service
#         self.delay_threshold_ms = delay_threshold_ms
#         self.preemptive_phrases = preemptive_phrases or [
#             "Let me check that for you...",
#             "Just a moment please...",
#             "I'm thinking about that...",
#             "Processing your request...",
#             "Working on that...",
#         ]
        
#         self._user_finished_speaking_time = None
#         self._llm_response_started = False
#         self._preemptive_task = None
#         self._preemptive_sent = False
        
#         logger.info(f"🎯 PreemptiveResponseProcessor initialized with {delay_threshold_ms}ms threshold")

#     async def process_frame(self, frame, direction):
#         # Handle StartFrame to properly initialize the processor
#         if isinstance(frame, StartFrame):
#             logger.debug("🚀 PreemptiveResponseProcessor started")
#             await self.push_frame(frame, direction)
#             return
        
#         # Handle EndFrame to cleanup
#         if isinstance(frame, EndFrame):
#             logger.debug("🛑 PreemptiveResponseProcessor ending")
#             if self._preemptive_task and not self._preemptive_task.done():
#                 self._preemptive_task.cancel()
#             await self.push_frame(frame, direction)
#             return
        
#         # Pass through audio frames without processing
#         if isinstance(frame, AudioRawFrame):
#             await self.push_frame(frame, direction)
#             return
        
#         # Detect when user finishes speaking (STT produces final transcription)
#         if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
#             if frame.text.strip():  # Non-empty transcription
#                 logger.debug(f"🗣️ User transcription: '{frame.text}'")
#                 self._user_finished_speaking_time = time.time() * 1000  # Convert to ms
#                 self._llm_response_started = False
#                 self._preemptive_sent = False
                
#                 # Cancel any existing preemptive task
#                 if self._preemptive_task and not self._preemptive_task.done():
#                     self._preemptive_task.cancel()
                
#                 # Start watching for delayed LLM response
#                 logger.debug(f"⏰ Starting preemptive watch (threshold: {self.delay_threshold_ms}ms)")
#                 self._preemptive_task = asyncio.create_task(self._watch_for_delayed_llm())

#         # Detect when LLM starts responding
#         elif isinstance(frame, LLMMessagesFrame) and direction == FrameDirection.DOWNSTREAM:
#             logger.debug("🧠 LLM response started")
#             self._llm_response_started = True
            
#             # Cancel preemptive task since LLM is now responding
#             if self._preemptive_task and not self._preemptive_task.done():
#                 logger.debug("❌ Cancelling preemptive task - LLM responded")
#                 self._preemptive_task.cancel()

#         # Detect actual text responses from LLM
#         elif isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
#             if not self._llm_response_started:
#                 logger.debug("📝 LLM text response detected")
#                 self._llm_response_started = True
                
#                 # Cancel preemptive task
#                 if self._preemptive_task and not self._preemptive_task.done():
#                     logger.debug("❌ Cancelling preemptive task - LLM text response")
#                     self._preemptive_task.cancel()

#         # Always forward the frame (except Start/End/Audio which are handled above)
#         await self.push_frame(frame, direction)

#     async def _watch_for_delayed_llm(self):
#         """Watch for delayed LLM response and trigger preemptive response if needed"""
#         try:
#             # Wait for the threshold period
#             await asyncio.sleep(self.delay_threshold_ms / 1000.0)
            
#             # Check if LLM has started responding
#             if not self._llm_response_started and not self._preemptive_sent:
#                 logger.info(f"🚀 Triggering preemptive response after {self.delay_threshold_ms}ms delay")
#                 await self._send_preemptive_response()
                
#         except asyncio.CancelledError:
#             logger.debug("❌ Preemptive watch cancelled")

#     async def _send_preemptive_response(self):
#         """Send a preemptive response to fill the silence"""
#         phrase = random.choice(self.preemptive_phrases)
#         logger.info(f"🎤 Sending preemptive response: '{phrase}'")
        
#         # Create a text frame with the preemptive phrase
#         preemptive_frame = TextFrame(phrase)
        
#         # Send it downstream to TTS
#         await self.push_frame(preemptive_frame, FrameDirection.DOWNSTREAM)
        
#         self._preemptive_sent = True


"""
Conservative Preemptive Speech Processor

This version uses only the most basic frame types that should be available
in all Pipecat versions, and relies on timing instead of LLM frame detection.
"""

import asyncio
import random
import time
from typing import Dict, List, Optional

from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    UserStoppedSpeakingFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
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
        
        # State tracking
        self._preemptive_task: Optional[asyncio.Task] = None
        self._bot_speaking = False
        self._llm_responding = False
        self._last_user_text = ""
        self._user_stopped_time: Optional[float] = None
        self._preemptive_triggered = False
        self._preemptive_playing = False
        
        logger.info(f"PreemptiveSpeechProcessor initialized with {threshold_ms}ms threshold")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        # Track user input
        if isinstance(frame, UserStoppedSpeakingFrame):
            await self._handle_user_stopped_speaking()
            
        elif isinstance(frame, TranscriptionFrame) and direction == FrameDirection.UPSTREAM:
            self._last_user_text = frame.text
            logger.debug(f"Captured user text: '{self._last_user_text}'")
        
        # Track LLM response lifecycle
        elif isinstance(frame, LLMFullResponseStartFrame):
            self._llm_responding = True
            if not self._preemptive_triggered:
                await self._cancel_preemptive()
                logger.debug("LLM response started, canceling preemptive")
                
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._llm_responding = False
        
        # Track bot speaking state
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            await self._reset_state()
            
        # Track TTS state to detect preemptive audio
        elif isinstance(frame, TTSStartedFrame):
            if self._preemptive_triggered and not self._llm_responding:
                self._preemptive_playing = True
                logger.debug("Preemptive TTS started")
                
        elif isinstance(frame, TTSStoppedFrame):
            if self._preemptive_playing:
                self._preemptive_playing = False
                logger.debug("Preemptive TTS stopped")
            
        # Pass frame through
        await self.push_frame(frame, direction)

    async def _handle_user_stopped_speaking(self):
        """Handle when user stops speaking - start preemptive timer"""
        self._user_stopped_time = time.time()
        await self._reset_state()
        
        # Cancel any existing preemptive task
        if self._preemptive_task and not self._preemptive_task.done():
            self._preemptive_task.cancel()
            
        # Start new preemptive timer
        self._preemptive_task = asyncio.create_task(self._preemptive_timer())
        logger.debug("User stopped speaking, starting preemptive timer")

    async def _reset_state(self):
        """Reset preemptive state for new interaction"""
        self._preemptive_triggered = False
        self._preemptive_playing = False

    async def _preemptive_timer(self):
        """Timer that triggers preemptive response after threshold"""
        try:
            await asyncio.sleep(self.threshold)
            
            # Only trigger if LLM hasn't started and bot isn't speaking
            if not self._llm_responding and not self._bot_speaking and not self._preemptive_triggered:
                await self._trigger_preemptive()
                
        except asyncio.CancelledError:
            logger.debug("Preemptive timer cancelled")
        except Exception as e:
            logger.error(f"Error in preemptive timer: {e}")

    async def _trigger_preemptive(self):
        """Trigger the preemptive response"""
        self._preemptive_triggered = True
        
        # Select appropriate phrase
        intent = self._infer_intent(self._last_user_text)
        phrases = self.filler_config.get(intent, self.filler_config["default"])
        phrase = random.choice(phrases)
        
        logger.info(f"Triggering preemptive response: '{phrase}' (intent: {intent})")
        
        try:
            # Push TextFrame downstream to TTS
            text_frame = TextFrame(text=phrase)
            await self.push_frame(text_frame, FrameDirection.DOWNSTREAM)
            logger.info(f"Preemptive response generated: {text_frame.text}") 
            
        except Exception as e:
            logger.error(f"Error triggering preemptive response: {e}")

    async def _cancel_preemptive(self):
        """Cancel any active preemptive task"""
        if self._preemptive_task and not self._preemptive_task.done():
            self._preemptive_task.cancel()
            logger.debug("Preemptive task cancelled")

    def _infer_intent(self, text: str) -> str:
        """Simple intent detection based on keywords"""
        if not text:
            return "default"
            
        text_lower = text.lower()
        
        # Question detection
        question_indicators = ["what", "how", "why", "when", "where", "who", "?"]
        if any(indicator in text_lower for indicator in question_indicators):
            return "question"
            
        # Calculation detection  
        calc_indicators = ["calculate", "math", "number", "sum", "total", "+", "-", "*", "/"]
        if any(indicator in text_lower for indicator in calc_indicators):
            return "calculation"
            
        return "default"

    def get_debug_info(self) -> Dict:
        """Get current state for debugging"""
        return {
            "threshold_ms": self.threshold * 1000,
            "bot_speaking": self._bot_speaking,
            "llm_responding": self._llm_responding,
            "last_user_text": self._last_user_text,
            "preemptive_triggered": self._preemptive_triggered,
            "preemptive_playing": self._preemptive_playing,
            "has_active_task": self._preemptive_task is not None and not self._preemptive_task.done(),
            "user_stopped_time": self._user_stopped_time,
        }
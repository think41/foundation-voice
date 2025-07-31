"""
Enhanced Preemptive Speech Processor

A comprehensive processor that provides configurable preemptive responses
to reduce perceived latency in voice interactions.

Features:
- Configurable global and intent-specific phrases
- Adjustable latency threshold
- Fallback behavior for quick responses
- Context-aware intent detection
- Robust state management
- Streaming/non-streaming response support
- Interrupt/cancel mechanisms
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    UserStoppedSpeakingFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMMessagesFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    BotInterruptionFrame,
    CancelFrame,
    EndFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class PreemptiveState(Enum):
    """States for preemptive response lifecycle"""
    IDLE = "idle"
    WAITING = "waiting"
    PLAYING = "playing"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class PreemptiveConfig:
    """Configuration for preemptive responses"""
    # Core settings
    enabled: bool = True
    latency_threshold_ms: int = 300
    max_preemptive_duration_ms: int = 4000
    
    # Global preemptive phrases (fallback)
    global_phrases: List[str] = field(default_factory=lambda: [
        "Let me check that for you...",
        "Just a moment...",
        "I'm thinking about that...",
        "Give me a second...",
        "Processing your request...",
    ])
    
    # Intent-specific phrases (context-aware)
    intent_phrases: Dict[str, List[str]] = field(default_factory=lambda: {
        "question": [
            "That's a great question, let me think...",
            "Let me look that up for you...",
            "I need to consider that carefully...",
            "Interesting question, give me a moment...",
        ],
        "request": [
            "I'll help you with that right away...",
            "Let me take care of that for you...",
            "Working on that request now...",
            "I'm on it, just a moment...",
        ],
        "search": [
            "Let me search for that information...",
            "Looking that up now...",
            "Searching our database...",
            "Finding that information for you...",
        ],
        "calculation": [
            "Let me calculate that for you...",
            "Running those numbers now...",
            "Computing that result...",
            "Working out the math on that...",
        ],
        "greeting": [
            "Hello! Let me just get ready...",
            "Hi there! Give me just a moment...",
            "Nice to meet you! Just getting set up...",
        ],
        "complex": [
            "That's quite involved, let me work through it...",
            "This will take some careful thought...",
            "Let me analyze this thoroughly...",
        ],
        "default": [
            "Just a moment please...",
            "One second...",
            "Let me process that...",
        ]
    })
    
    # Fallback behavior
    skip_if_quick_response: bool = True
    quick_response_threshold_ms: int = 150
    
    # TTS customization for preemptive responses
    preemptive_tts_voice: Optional[str] = None
    preemptive_tts_speed: float = 1.05  # Slightly faster
    preemptive_tts_volume: float = 0.9   # Slightly quieter
    
    # Advanced features
    use_intent_detection: bool = True
    max_phrase_length: int = 50  # Characters
    avoid_repetition: bool = True
    repetition_window: int = 3   # Last N phrases to avoid repeating


@dataclass
class PreemptiveSession:
    """Tracks state of a preemptive response session"""
    state: PreemptiveState = PreemptiveState.IDLE
    start_time: float = 0.0
    user_input: str = ""
    detected_intent: str = "default"
    selected_phrase: Optional[str] = None
    preemptive_task: Optional[asyncio.Task] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    actual_response_started: bool = False
    quick_response_detected: bool = False


class EnhancedPreemptiveProcessor(FrameProcessor):
    """
    Enhanced preemptive processor with comprehensive features for
    reducing perceived latency in voice interactions.
    """
    
    def __init__(
        self,
        config: Optional[PreemptiveConfig] = None,
        tts_processor: Optional[Any] = None,
        intent_classifier: Optional[Callable[[str], str]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.config = config or PreemptiveConfig()
        self.tts_processor = tts_processor
        self.intent_classifier = intent_classifier or self._default_intent_classifier
        
        # Session management
        self.current_session: Optional[PreemptiveSession] = None
        self.recent_phrases: List[str] = []  # For avoiding repetition
        
        # State tracking
        self.user_speaking = False
        self.bot_speaking = False
        self.llm_processing = False
        self.preemptive_active = False
        
        # Metrics and monitoring
        self.metrics = {
            "sessions_started": 0,
            "preemptive_triggered": 0,
            "preemptive_cancelled": 0,
            "preemptive_completed": 0,
            "quick_responses_detected": 0,
            "avg_trigger_latency": 0.0,
            "latency_samples": [],
            "intent_distribution": {},
            "phrase_usage": {},
        }
        
        logger.info(f"🚀 Enhanced Preemptive Processor initialized")
        logger.info(f"   Threshold: {self.config.latency_threshold_ms}ms")
        logger.info(f"   Max duration: {self.config.max_preemptive_duration_ms}ms")
        logger.info(f"   Intent detection: {self.config.use_intent_detection}")
    
    def _default_intent_classifier(self, text: str) -> str:
        """Enhanced intent classification with more sophisticated patterns"""
        if not text:
            return "default"
        
        text_lower = text.lower().strip()
        
        # Greeting patterns
        greeting_patterns = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        if any(pattern in text_lower for pattern in greeting_patterns):
            return "greeting"
        
        # Question patterns (enhanced)
        question_indicators = [
            "what", "how", "why", "when", "where", "who", "which", "whom",
            "can you", "could you", "would you", "will you", "do you", "did you",
            "is there", "are there", "does", "doesn't", "should", "shouldn't"
        ]
        if (text_lower.endswith("?") or 
            any(text_lower.startswith(indicator) for indicator in question_indicators) or
            any(f" {indicator} " in f" {text_lower} " for indicator in question_indicators)):
            return "question"
        
        # Request patterns (enhanced)
        request_indicators = [
            "please", "help me", "can you help", "i need", "i want", "i would like",
            "could you please", "would you mind", "assist me", "support me"
        ]
        if any(indicator in text_lower for indicator in request_indicators):
            return "request"
        
        # Search patterns
        search_indicators = [
            "find", "search", "look up", "tell me about", "information about",
            "details on", "show me", "get me", "retrieve"
        ]
        if any(indicator in text_lower for indicator in search_indicators):
            return "search"
        
        # Calculation patterns
        calc_indicators = [
            "calculate", "compute", "math", "add", "subtract", "multiply", "divide",
            "sum", "total", "average", "percentage", "convert", "how much", "how many"
        ]
        if any(indicator in text_lower for indicator in calc_indicators):
            return "calculation"
        
        # Complex task patterns
        complex_indicators = [
            "analyze", "compare", "evaluate", "explain in detail", "breakdown",
            "comprehensive", "thorough", "detailed analysis", "step by step"
        ]
        if (any(indicator in text_lower for indicator in complex_indicators) or
            len(text.split()) > 20):  # Long requests are likely complex
            return "complex"
        
        return "default"
    
    def _select_preemptive_phrase(self, intent: str, user_input: str = "") -> str:
        """Select appropriate preemptive phrase with repetition avoidance"""
        # Get phrases for the detected intent
        if intent in self.config.intent_phrases:
            candidate_phrases = self.config.intent_phrases[intent].copy()
        else:
            # Fallback to default intent, then global phrases
            candidate_phrases = (
                self.config.intent_phrases.get("default", []) + 
                self.config.global_phrases
            ).copy()
        
        if not candidate_phrases:
            candidate_phrases = ["Just a moment..."]
        
        # Filter out phrases that are too long
        candidate_phrases = [
            phrase for phrase in candidate_phrases 
            if len(phrase) <= self.config.max_phrase_length
        ]
        
        # Avoid repetition if enabled
        if self.config.avoid_repetition and self.recent_phrases:
            available_phrases = [
                phrase for phrase in candidate_phrases 
                if phrase not in self.recent_phrases[-self.config.repetition_window:]
            ]
            if available_phrases:
                candidate_phrases = available_phrases
        
        # Select phrase
        selected_phrase = random.choice(candidate_phrases)
        
        # Update recent phrases for repetition avoidance
        if self.config.avoid_repetition:
            self.recent_phrases.append(selected_phrase)
            if len(self.recent_phrases) > self.config.repetition_window * 2:
                self.recent_phrases = self.recent_phrases[-self.config.repetition_window:]
        
        # Update metrics
        self.metrics["phrase_usage"][selected_phrase] = (
            self.metrics["phrase_usage"].get(selected_phrase, 0) + 1
        )
        
        return selected_phrase
    
    async def _start_preemptive_session(self, user_input: str = ""):
        """Start a new preemptive response session"""
        if not self.config.enabled:
            logger.debug("🚫 Preemptive responses disabled")
            return
        
        if self.bot_speaking:
            logger.debug("🚫 Bot currently speaking, skipping preemptive session")
            return
        
        # Cancel any existing session
        await self._cancel_current_session("new_session")
        
        # Detect intent
        intent = "default"
        if self.config.use_intent_detection and user_input:
            intent = self.intent_classifier(user_input)
        
        # Create new session
        self.current_session = PreemptiveSession(
            state=PreemptiveState.WAITING,
            start_time=time.time(),
            user_input=user_input,
            detected_intent=intent
        )
        
        # Update metrics
        self.metrics["sessions_started"] += 1
        self.metrics["intent_distribution"][intent] = (
            self.metrics["intent_distribution"].get(intent, 0) + 1
        )
        
        # Start preemptive task
        self.current_session.preemptive_task = asyncio.create_task(
            self._preemptive_timer()
        )
        
        logger.info(f"🚀 Started preemptive session")
        logger.debug(f"   Intent: {intent}")
        logger.debug(f"   Input: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
    
    async def _preemptive_timer(self):
        """Timer that triggers preemptive response after threshold"""
        session = self.current_session
        if not session:
            return
        
        try:
            logger.debug(f"⏱️ Preemptive timer started ({self.config.latency_threshold_ms}ms)")
            
            # Wait for the configured threshold
            await asyncio.sleep(self.config.latency_threshold_ms / 1000.0)
            
            # Check if we should still proceed
            if (session.cancel_event.is_set() or 
                session.actual_response_started or 
                session.state != PreemptiveState.WAITING):
                logger.debug("❌ Preemptive cancelled before trigger")
                session.state = PreemptiveState.CANCELLED
                self.metrics["preemptive_cancelled"] += 1
                return
            
            # Trigger preemptive response
            await self._trigger_preemptive_response(session)
            
        except asyncio.CancelledError:
            logger.debug("⏹️ Preemptive timer cancelled")
            session.state = PreemptiveState.CANCELLED
            self.metrics["preemptive_cancelled"] += 1
        except Exception as e:
            logger.error(f"💥 Error in preemptive timer: {e}")
            session.state = PreemptiveState.CANCELLED
    
    async def _trigger_preemptive_response(self, session: PreemptiveSession):
        """Trigger the actual preemptive response"""
        if not session or session.state != PreemptiveState.WAITING:
            return
        
        # Select phrase
        phrase = self._select_preemptive_phrase(
            session.detected_intent, 
            session.user_input
        )
        session.selected_phrase = phrase
        session.state = PreemptiveState.PLAYING
        
        # Calculate and record latency
        trigger_latency = (time.time() - session.start_time) * 1000
        self.metrics["latency_samples"].append(trigger_latency)
        if self.metrics["latency_samples"]:
            self.metrics["avg_trigger_latency"] = (
                sum(self.metrics["latency_samples"]) / len(self.metrics["latency_samples"])
            )
        
        logger.info(f"🎯 Triggering preemptive response: '{phrase}'")
        logger.debug(f"   Intent: {session.detected_intent}")
        logger.debug(f"   Latency: {trigger_latency:.1f}ms")
        
        try:
            # Create TextFrame for TTS
            text_frame = TextFrame(text=phrase)
            
            # Mark as preemptive active
            self.preemptive_active = True
            self.metrics["preemptive_triggered"] += 1
            
            # Send to TTS
            await self.push_frame(text_frame, FrameDirection.DOWNSTREAM)
            
            # Wait for completion or cancellation
            try:
                await asyncio.wait_for(
                    session.cancel_event.wait(),
                    timeout=self.config.max_preemptive_duration_ms / 1000.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Preemptive response reached maximum duration")
                await self._complete_preemptive_session("timeout")
            
        except Exception as e:
            logger.error(f"💥 Error triggering preemptive response: {e}")
            session.state = PreemptiveState.CANCELLED
    
    async def _cancel_current_session(self, reason: str = "unknown"):
        """Cancel the current preemptive session"""
        if not self.current_session:
            return
        
        session = self.current_session
        logger.debug(f"🛑 Cancelling preemptive session: {reason}")
        
        # Set cancel event
        session.cancel_event.set()
        
        # Cancel task
        if session.preemptive_task and not session.preemptive_task.done():
            session.preemptive_task.cancel()
            try:
                await session.preemptive_task
            except asyncio.CancelledError:
                pass
        
        # Send interruption if currently playing
        if session.state == PreemptiveState.PLAYING and self.preemptive_active:
            await self.push_frame(BotInterruptionFrame(), FrameDirection.DOWNSTREAM)
            logger.debug("🔇 Sent interruption to stop preemptive TTS")
        
        # Update state
        if session.state == PreemptiveState.PLAYING:
            session.state = PreemptiveState.CANCELLED
        
        self.preemptive_active = False
        self.current_session = None
    
    async def _complete_preemptive_session(self, reason: str = "completed"):
        """Complete the current preemptive session successfully"""
        if not self.current_session:
            return
        
        session = self.current_session
        logger.debug(f"✅ Completing preemptive session: {reason}")
        
        session.state = PreemptiveState.COMPLETED
        session.cancel_event.set()
        
        self.metrics["preemptive_completed"] += 1
        self.preemptive_active = False
        self.current_session = None
    
    async def _handle_quick_response(self) -> bool:
        """Check if response is quick enough to skip preemptive"""
        if not self.config.skip_if_quick_response or not self.current_session:
            return False
        
        elapsed_ms = (time.time() - self.current_session.start_time) * 1000
        
        if elapsed_ms < self.config.quick_response_threshold_ms:
            logger.debug(f"⚡ Quick response detected ({elapsed_ms:.1f}ms)")
            self.current_session.quick_response_detected = True
            self.metrics["quick_responses_detected"] += 1
            await self._cancel_current_session("quick_response")
            return True
        
        return False
    
    # Frame Processing Methods
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Main frame processing logic"""
        
        # Handle user input frames
        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.UPSTREAM:
            if frame.text and frame.text.strip():
                logger.debug(f"📝 User transcription: '{frame.text}'")
                # Start preemptive session for user input
                if not self.user_speaking and not self.bot_speaking:
                    await self._start_preemptive_session(frame.text)
        
        elif isinstance(frame, UserStoppedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
            logger.debug("🗣️ User stopped speaking")
            self.user_speaking = False
            # If no session started yet from transcription, start one now
            if not self.current_session:
                await self._start_preemptive_session()
        
        # Handle LLM processing frames
        elif isinstance(frame, LLMMessagesFrame) and direction == FrameDirection.DOWNSTREAM:
            logger.debug("🧠 LLM messages frame - processing started")
            self.llm_processing = True
            # If no preemptive session yet, start one
            if not self.current_session:
                await self._start_preemptive_session()
        
        elif isinstance(frame, LLMFullResponseStartFrame):
            logger.info("✨ LLM response started")
            self.llm_processing = True
            
            if self.current_session:
                self.current_session.actual_response_started = True
                
                # Check for quick response
                if not await self._handle_quick_response():
                    # Cancel preemptive as actual response is ready
                    await self._cancel_current_session("llm_response_ready")
        
        elif isinstance(frame, LLMFullResponseEndFrame):
            logger.debug("🏁 LLM response ended")
            self.llm_processing = False
            if self.current_session:
                await self._complete_preemptive_session("llm_response_ended")
        
        # Handle bot speaking state
        elif isinstance(frame, BotStartedSpeakingFrame):
            if self.preemptive_active:
                logger.info("🎤 Preemptive TTS started")
            else:
                logger.info("🎤 Bot started speaking (actual response)")
                self.bot_speaking = True
                await self._cancel_current_session("bot_started_speaking")
        
        elif isinstance(frame, BotStoppedSpeakingFrame):
            if self.preemptive_active:
                logger.info("🎤 Preemptive TTS finished")
                await self._complete_preemptive_session("preemptive_tts_finished")
            else:
                logger.info("🎤 Bot stopped speaking")
                self.bot_speaking = False
        
        # Handle TTS frames for finer control
        elif isinstance(frame, TTSStartedFrame):
            if self.preemptive_active:
                logger.debug("🎵 Preemptive TTS audio started")
        
        elif isinstance(frame, TTSStoppedFrame):
            if self.preemptive_active:
                logger.debug("🎵 Preemptive TTS audio stopped")
        
        # Handle interruption and cancellation frames
        elif isinstance(frame, (BotInterruptionFrame, CancelFrame)):
            logger.debug("🚫 Interruption/cancel frame received")
            await self._cancel_current_session("interruption")
        
        elif isinstance(frame, EndFrame):
            logger.debug("🛑 End frame received")
            await self._cancel_current_session("end_frame")
        
        # Always process and forward the frame
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
    
    # Utility and Management Methods
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive processor metrics"""
        return {
            **self.metrics,
            "current_session_active": self.current_session is not None,
            "current_state": self.current_session.state.value if self.current_session else "idle",
            "preemptive_active": self.preemptive_active,
            "bot_speaking": self.bot_speaking,
            "llm_processing": self.llm_processing,
            "config": {
                "enabled": self.config.enabled,
                "threshold_ms": self.config.latency_threshold_ms,
                "max_duration_ms": self.config.max_preemptive_duration_ms,
                "use_intent_detection": self.config.use_intent_detection,
                "avoid_repetition": self.config.avoid_repetition,
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            "sessions_started": 0,
            "preemptive_triggered": 0,
            "preemptive_cancelled": 0,
            "preemptive_completed": 0,
            "quick_responses_detected": 0,
            "avg_trigger_latency": 0.0,
            "latency_samples": [],
            "intent_distribution": {},
            "phrase_usage": {},
        }
        self.recent_phrases = []
        logger.info("📊 Metrics reset")
    
    def update_config(self, new_config: PreemptiveConfig):
        """Update processor configuration"""
        self.config = new_config
        logger.info("⚙️ Configuration updated")
        logger.info(f"   New threshold: {self.config.latency_threshold_ms}ms")
    
    def add_phrases(self, intent: str, phrases: List[str]):
        """Add new phrases for a specific intent"""
        if intent not in self.config.intent_phrases:
            self.config.intent_phrases[intent] = []
        
        self.config.intent_phrases[intent].extend(phrases)
        logger.info(f"📝 Added {len(phrases)} phrases for intent '{intent}'")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get detailed debug information"""
        session_info = {}
        if self.current_session:
            session_info = {
                "state": self.current_session.state.value,
                "start_time": self.current_session.start_time,
                "user_input": self.current_session.user_input[:100],
                "detected_intent": self.current_session.detected_intent,
                "selected_phrase": self.current_session.selected_phrase,
                "actual_response_started": self.current_session.actual_response_started,
                "quick_response_detected": self.current_session.quick_response_detected,
            }
        
        return {
            "processor_state": {
                "user_speaking": self.user_speaking,
                "bot_speaking": self.bot_speaking,
                "llm_processing": self.llm_processing,
                "preemptive_active": self.preemptive_active,
            },
            "current_session": session_info,
            "recent_phrases": self.recent_phrases[-5:],  # Last 5 phrases
            "metrics_summary": {
                "total_sessions": self.metrics["sessions_started"],
                "success_rate": (
                    self.metrics["preemptive_completed"] / 
                    max(1, self.metrics["preemptive_triggered"])
                ) * 100,
                "avg_latency": self.metrics["avg_trigger_latency"],
                "top_intents": dict(
                    sorted(self.metrics["intent_distribution"].items(), 
                           key=lambda x: x[1], reverse=True)[:5]
                ),
            }
        }
    
    async def cleanup(self):
        """Clean up resources"""
        await self._cancel_current_session("cleanup")
        logger.info("🧹 Enhanced Preemptive Processor cleaned up")
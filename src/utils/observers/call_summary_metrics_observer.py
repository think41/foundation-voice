import asyncio
import time
from collections import defaultdict
from typing import Dict, List, Any

from loguru import logger

from pipecat.frames.frames import Frame, MetricsFrame, BotStartedSpeakingFrame, UserStoppedSpeakingFrame
from pipecat.metrics.metrics import (
    MetricsData,
    TTFBMetricsData,
    ProcessingMetricsData,
    LLMTokenUsage,
    LLMUsageMetricsData,
    TTSUsageMetricsData,
)
from pipecat.observers.base_observer import BaseObserver
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class CallSummaryMetricsObserver(BaseObserver):
    """
    An observer that tracks and logs various metrics during a call, including:
    - Time To First Byte (TTFB)
    - Processing times
    - LLM token usage
    - TTS character usage
    
    The summary is logged when an EndFrame is received.
    """
    def __init__(self):
        super().__init__()
        # Store all individual values to calculate overall averages at the end
        self._ttfb_values: List[float] = []
        self._processing_times: List[float] = []
        # Store aggregate token and character counts
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tts_characters: int = 0
        self._summary_logged: bool = False
        self._call_start_time: float = 0.0
        # Userbot latency tracking
        self._user_stopped_time: Optional[float] = None
        self._userbot_latencies: List[float] = []

    async def on_push_frame(
        self,
        src: FrameProcessor,
        dst: FrameProcessor,
        frame: Frame,
        direction: FrameDirection,
        timestamp: int,
    ):
        """
        Process incoming frames to collect metrics.
        
        Args:
            src: The source frame processor
            dst: The destination frame processor
            frame: The frame being processed
            direction: The direction of the frame (UPSTREAM or DOWNSTREAM)
            timestamp: The timestamp when the frame was processed
        """
        if isinstance(frame, MetricsFrame):
            for data in frame.data:
                if isinstance(data, TTFBMetricsData):
                    # Only log TTFB if it's a valid, non-zero value
                    if data.value > 0:
                        logger.trace(f"Observer received TTFB from {data.processor}: {data.value:.4f}s")
                        self._ttfb_values.append(data.value)
                elif isinstance(data, ProcessingMetricsData):
                    if data.value > 0:
                        logger.trace(f"Observer received ProcessingTime from {data.processor}: {data.value:.4f}s")
                        self._processing_times.append(data.value)
                elif isinstance(data, LLMUsageMetricsData):
                    logger.trace(f"Observer received LLMUsage from {data.processor}: {data.value.prompt_tokens}p, {data.value.completion_tokens}c")
                    self._total_prompt_tokens += data.value.prompt_tokens
                    self._total_completion_tokens += data.value.completion_tokens
                elif isinstance(data, TTSUsageMetricsData):
                    logger.trace(f"Observer received TTSUsage from {data.processor}: {data.value} chars")
                    self._total_tts_characters += data.value
        
        # Track userbot latency (time between user stops speaking and bot starts speaking)
        if direction != FrameDirection.DOWNSTREAM:
            return
            
        if isinstance(frame, UserStoppedSpeakingFrame):
            self._user_stopped_time = time.time()
        elif (isinstance(frame, BotStartedSpeakingFrame) and 
              self._user_stopped_time is not None):
            latency = time.time() - self._user_stopped_time
            self._userbot_latencies.append(latency)
            logger.trace(f"Userbot latency: {latency:.3f}s")
            self._user_stopped_time = None

        # The summary will be triggered by the agent when a participant leaves

    async def _log_summary(self):
        """Log a summary of all collected metrics."""
        logger.info("\n" + "=" * 50)
        logger.info("CALL METRICS SUMMARY")
        logger.info("=" * 50)

        if self._ttfb_values:
            avg_ttfb = sum(self._ttfb_values) / len(self._ttfb_values)
            logger.info(f"• Average TTFB: {avg_ttfb:.4f} seconds ({len(self._ttfb_values)} samples)")
        else:
            logger.info("• Average TTFB: No data")

        if self._processing_times:
            avg_processing_time = sum(self._processing_times) / len(self._processing_times)
            logger.info(f"• Average Processing Time: {avg_processing_time:.4f} seconds ({len(self._processing_times)} samples)")
        else:
            logger.info("• Average Processing Time: No data")

        logger.info(f"• Total Prompt Tokens: {self._total_prompt_tokens}")
        logger.info(f"• Total Completion Tokens: {self._total_completion_tokens}")
        total_llm_tokens = self._total_prompt_tokens + self._total_completion_tokens
        logger.info(f"• Total LLM Tokens: {total_llm_tokens} (${total_llm_tokens * 0.00002:.4f} estimated cost)")

        logger.info(f"• Total TTS Characters: {self._total_tts_characters}")
        
        # Calculate and log call duration if we have timing data
        if hasattr(self, '_call_start_time'):
            import time
            call_duration = time.time() - self._call_start_time
            logger.info(f"• Call Duration: {call_duration:.2f} seconds")
        
        # Log userbot latency metrics if available
        if hasattr(self, '_userbot_latencies') and self._userbot_latencies:
            avg_latency = sum(self._userbot_latencies) / len(self._userbot_latencies)
            logger.info(f"• Average Userbot Latency: {avg_latency:.3f} seconds ({len(self._userbot_latencies)} samples)")
        else:
            logger.info("• Average Userbot Latency: No data")
            
        logger.info("=" * 50 + "\n")

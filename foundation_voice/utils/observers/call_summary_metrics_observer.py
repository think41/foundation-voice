import time
from typing import Dict, List, Any, Optional

from loguru import logger

from pipecat.frames.frames import (
    MetricsFrame,
    BotStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import (
    TTFBMetricsData,
    ProcessingMetricsData,
    LLMUsageMetricsData,
    TTSUsageMetricsData,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.processors.frame_processor import FrameDirection


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
        self._call_start_time: float = time.time()
        # Userbot latency tracking
        self._user_stopped_time: Optional[float] = None
        self._userbot_latencies: List[float] = []

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all collected metrics as a JSON-compatible dictionary.

        Returns:
            Dictionary containing:
            - avg_ttfb: Average Time To First Byte in seconds
            - ttfb_samples: Number of TTFB samples
            - avg_processing_time: Average processing time in seconds
            - processing_samples: Number of processing time samples
            - total_prompt_tokens: Total number of prompt tokens used
            - total_completion_tokens: Total number of completion tokens used
            - total_llm_tokens: Total number of LLM tokens used
            - estimated_cost: Estimated cost in USD
            - total_tts_characters: Total number of TTS characters used
            - call_duration: Total call duration in seconds
            - avg_userbot_latency: Average latency between user stop and bot start in seconds
            - userbot_latency_samples: Number of userbot latency samples
        """
        metrics = {
            "avg_ttfb": None,
            "ttfb_samples": len(self._ttfb_values),
            "avg_processing_time": None,
            "processing_samples": len(self._processing_times),
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_llm_tokens": self._total_prompt_tokens
            + self._total_completion_tokens,
            "estimated_cost": (
                self._total_prompt_tokens + self._total_completion_tokens
            )
            * 0.00002,
            "total_tts_characters": self._total_tts_characters,
            "call_duration": time.time() - self._call_start_time,
            "avg_userbot_latency": None,
            "userbot_latency_samples": len(self._userbot_latencies),
        }

        # Calculate averages if we have data
        if self._ttfb_values:
            metrics["avg_ttfb"] = sum(self._ttfb_values) / len(self._ttfb_values)

        if self._processing_times:
            metrics["avg_processing_time"] = sum(self._processing_times) / len(
                self._processing_times
            )

        if self._userbot_latencies:
            metrics["avg_userbot_latency"] = sum(self._userbot_latencies) / len(
                self._userbot_latencies
            )

        return metrics

    async def on_push_frame(self, metric_data: FramePushed):
        """
        Process incoming frames to collect metrics.

        Args:
            src: The source frame processor
            dst: The destination frame processor
            frame: The frame being processed
            direction: The direction of the frame (UPSTREAM or DOWNSTREAM)
            timestamp: The timestamp when the frame was processed
        """
        if isinstance(metric_data.frame, MetricsFrame):
            for data in metric_data.frame.data:
                if isinstance(data, TTFBMetricsData):
                    # Only log TTFB if it's a valid, non-zero value
                    if data.value > 0:
                        logger.trace(
                            f"Observer received TTFB from {data.processor}: {data.value:.4f}s"
                        )
                        self._ttfb_values.append(data.value)
                elif isinstance(data, ProcessingMetricsData):
                    if data.value > 0:
                        logger.trace(
                            f"Observer received ProcessingTime from {data.processor}: {data.value:.4f}s"
                        )
                        self._processing_times.append(data.value)
                elif isinstance(data, LLMUsageMetricsData):
                    logger.trace(
                        f"Observer received LLMUsage from {data.processor}: {data.value.prompt_tokens}p, {data.value.completion_tokens}c"
                    )
                    self._total_prompt_tokens += data.value.prompt_tokens
                    self._total_completion_tokens += data.value.completion_tokens
                elif isinstance(data, TTSUsageMetricsData):
                    logger.trace(
                        f"Observer received TTSUsage from {data.processor}: {data.value} chars"
                    )
                    self._total_tts_characters += data.value

        # Track userbot latency (time between user stops speaking and bot starts speaking)
        if metric_data.direction != FrameDirection.DOWNSTREAM:
            return

        if isinstance(metric_data.frame, UserStoppedSpeakingFrame):
            self._user_stopped_time = time.time()
        elif (
            isinstance(metric_data.frame, BotStartedSpeakingFrame)
            and self._user_stopped_time is not None
        ):
            latency = time.time() - self._user_stopped_time
            self._userbot_latencies.append(latency)
            logger.trace(f"Userbot latency: {latency:.3f}s")
            self._user_stopped_time = None

    async def _log_summary(self):
        """Log a summary of all collected metrics."""
        metrics = self.get_metrics_summary()

        logger.info("\n" + "=" * 50)
        logger.info("CALL METRICS SUMMARY")
        logger.info("=" * 50)

        if metrics["avg_ttfb"] is not None:
            logger.info(
                f"• Average TTFB: {metrics['avg_ttfb']:.4f} seconds ({metrics['ttfb_samples']} samples)"
            )
        else:
            logger.info("• Average TTFB: No data")

        if metrics["avg_processing_time"] is not None:
            logger.info(
                f"• Average Processing Time: {metrics['avg_processing_time']:.4f} seconds ({metrics['processing_samples']} samples)"
            )
        else:
            logger.info("• Average Processing Time: No data")

        logger.info(f"• Total Prompt Tokens: {metrics['total_prompt_tokens']}")
        logger.info(f"• Total Completion Tokens: {metrics['total_completion_tokens']}")
        logger.info(
            f"• Total LLM Tokens: {metrics['total_llm_tokens']} (${metrics['estimated_cost']:.4f} estimated cost)"
        )

        logger.info(f"• Total TTS Characters: {metrics['total_tts_characters']}")
        logger.info(f"• Call Duration: {metrics['call_duration']:.2f} seconds")

        if metrics["avg_userbot_latency"] is not None:
            logger.info(
                f"• Average Userbot Latency: {metrics['avg_userbot_latency']:.3f} seconds ({metrics['userbot_latency_samples']} samples)"
            )
        else:
            logger.info("• Average Userbot Latency: No data")

        logger.info("=" * 50 + "\n")

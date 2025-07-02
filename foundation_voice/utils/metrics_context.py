# This module holds the shared context for tracking token usage across different parts of the application.
# It is used to pass data from the OpenTelemetry exporter to the metrics observers.

from typing import Dict

from loguru import logger
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


class TokenUsageExporter(SpanExporter):
    """
    Custom OpenTelemetry SpanExporter that extracts and tracks token usage from LLM spans.
    """

    def __init__(self, usage_dict: Dict[str, int]):
        self.usage_dict = usage_dict

    def export(self, spans: tuple[ReadableSpan, ...]) -> SpanExportResult:
        """
        Process spans and extract token usage metrics.

        Args:
            spans: A tuple of ReadableSpan objects containing span data

        Returns:
            SpanExportResult: SUCCESS if processing completed successfully
        """
        logger.debug(f"[TokenUsageExporter] Received {len(spans)} spans to process.")
        usage = self.usage_dict
        for span in spans:
            attributes = dict(span.attributes)
            # Log all span attributes for debugging purposes
            logger.debug(
                f"[TokenUsageExporter] Processing span: {span.name}, Attributes: {attributes}"
            )
            if "gen_ai.usage.input_tokens" in attributes:
                input_tokens = attributes.get("gen_ai.usage.input_tokens", 0)
                logger.debug(f"[TokenUsageExporter] Found input tokens: {input_tokens}")
                usage["total_input_tokens"] += input_tokens
            if "gen_ai.usage.output_tokens" in attributes:
                output_tokens = attributes.get("gen_ai.usage.output_tokens", 0)
                logger.debug(
                    f"[TokenUsageExporter] Found output tokens: {output_tokens}"
                )
                usage["total_output_tokens"] += output_tokens
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass


def create_token_usage_processor(usage_dict: Dict[str, int]) -> SimpleSpanProcessor:
    """
    Create and return a SimpleSpanProcessor with a TokenUsageExporter.

    Returns:
        SimpleSpanProcessor: Configured processor for token usage tracking
    """
    return SimpleSpanProcessor(TokenUsageExporter(usage_dict))

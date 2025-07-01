# This module holds the shared context for tracking token usage across different parts of the application.
# It is used to pass data from the OpenTelemetry exporter to the metrics observers.

token_usage_context = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
}

def reset_token_usage():
    """Resets the token usage context."""
    global token_usage_context
    token_usage_context["total_input_tokens"] = 0
    token_usage_context["total_output_tokens"] = 0

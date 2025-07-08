import aiohttp
from typing import Dict, Any, Optional
from loguru import logger


async def send_to_webhook(
    webhook_url: str,
    metrics_data: Dict[str, Any],
    transcript_data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Send metrics and transcript data to a webhook URL.

    Args:
        webhook_url: The URL to send the data to
        metrics_data: Dictionary containing call metrics
        transcript_data: Dictionary containing transcript data
        headers: Optional headers to include in the request

    Returns:
        bool: True if the request was successful, False otherwise

    Example:
        metrics = {
            "avg_ttfb": 0.5,
            "total_llm_tokens": 1000,
            ...
        }
        transcript = {
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "2024-03-20T10:00:00"},
                {"role": "assistant", "content": "Hi there!", "timestamp": "2024-03-20T10:00:01"}
            ]
        }
        success = await send_to_webhook("https://api.example.com/webhook", metrics, transcript)
    """
    if not webhook_url:
        logger.error("Webhook URL is required")
        return False

    payload = {"metrics": metrics_data, "transcript": transcript_data}

    default_headers = {"Content-Type": "application/json"}

    if headers:
        default_headers.update(headers)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url, json=payload, headers=default_headers
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent data to webhook: {webhook_url}")
                    return True
                else:
                    logger.error(
                        f"Failed to send data to webhook. Status: {response.status}, "
                        f"Response: {await response.text()}"
                    )
                    return False
    except Exception as e:
        logger.error(f"Error sending data to webhook: {str(e)}")
        return False

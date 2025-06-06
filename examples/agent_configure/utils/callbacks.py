from typing import Dict, Any
import aiohttp
from loguru import logger
from foundation_voice.custom_plugins.agent_callbacks import AgentCallbacks, AgentEvent
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

async def on_client_connected_callback(client):
    """
    Callback function for when a client connects.
    Override this function in your config to customize the behavior.
    """
    pass

async def on_first_participant_joined_callback(participant: Dict[str, Any]):
    """
    Callback function for when the first participant joins.
    Override this function in your config to customize the behavior.
    """
    print(f"Participant joined: {participant}")
    

async def on_transcript_update_callback(data: Dict[str, Any]):
    """
    Callback function for when a participant leaves.
    Override this function in your config to customize the behavior.
    """
    # print(f"Participant left: {data}")    
    pass


async def on_participant_left_callback(data: Dict[str, Any]) -> bool:
    """
    Send data to a webhook URL.
    """
    webhook_url = "https://webhook-test.com/f384cd81d8463f23e68fc895254b1333"  # Replace with your actual webhook URL

    headers = {
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json={"transcript": data.get("transcript"), "metrics": data.get("metrics")},
                headers=headers
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

# Create a custom AgentCallbacks instance
custom_callbacks = AgentCallbacks()

# Override default callbacks with our custom implementations
custom_callbacks.register_callback(
    AgentEvent.CLIENT_CONNECTED,
    on_client_connected_callback
)

custom_callbacks.register_callback(
    AgentEvent.FIRST_PARTICIPANT_JOINED,
    on_first_participant_joined_callback
)

custom_callbacks.register_callback(
    AgentEvent.PARTICIPANT_LEFT,
    on_participant_left_callback
)

custom_callbacks.register_callback(
    AgentEvent.TRANSCRIPT_UPDATE,
    on_transcript_update_callback
) 

custom_callbacks.register_callback(
    AgentEvent.CLIENT_DISCONNECTED,
    on_participant_left_callback
) 
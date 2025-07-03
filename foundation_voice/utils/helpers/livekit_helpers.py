import os
import uuid

from livekit import api
from loguru import logger


def generate_token(room_name: str, participant_name: str, api_key: str, api_secret: str) -> str:
    token = api.AccessToken(api_key, api_secret)
    token.with_identity(participant_name).with_name(participant_name).with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
        )
    )
    return token.to_jwt()

def generate_token_with_agent(
    room_name: str, 
    participant_name: str, 
    api_key: str, 
    api_secret: str
) -> str:
    token = api.AccessToken(api_key, api_secret)
    token.with_identity(participant_name).with_name(participant_name).with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
            agent=True
        )
    )
    return token.to_jwt()


def get_token():
    room_name = os.getenv("LIVEKIT_ROOM_NAME") or "livekitRoom_" + str(uuid.uuid4())
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not url:
        raise Exception(
            "No LiveKit room name specified. Set LIVEKIT_ROOM_NAME in your environment."
        )
    if not api_key:
        raise Exception(
            "No LiveKit API key specified. Set LIVEKIT_API_KEY in your environment."
        )
    if not api_secret:
        raise Exception(
            "No LiveKit API secret specified. Set LIVEKIT_API_SECRET in your environment."
        )

    return room_name, url, api_key, api_secret


def configure_livekit() -> None:
    room_name, url, api_key, api_secret = get_token()

    token = generate_token_with_agent(
        room_name=room_name,
        participant_name="agent", 
        api_key=api_key,
        api_secret=api_secret
    )

    user_token = generate_token(
        room_name=room_name,
        participant_name="user", 
        api_key=api_key,
        api_secret=api_secret
    )

    logger.info(f"User token: {user_token}")

    return url, user_token, room_name, token


def configure_livekit_sip() -> None:
    room_name, url, api_key, api_secret = get_token()
    token = generate_token_with_agent(
        room_name=room_name,
        participant_name="agent", 
        api_key=api_key,
        api_secret=api_secret
    )

    return url, room_name, token

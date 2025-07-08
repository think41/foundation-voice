import os
import requests
import urllib.parse
import time
from typing import Tuple


def create_room() -> Tuple[str, str]:
    """Create a new Daily.co room and return its URL and name."""
    api_key = os.getenv("DAILY_API_KEY")
    if not api_key:
        raise ValueError(
            "No Daily API key specified. Set DAILY_API_KEY in your environment."
        )

    # Create a unique room name using timestamp
    room_name = f"room-{int(time.time())}"

    response = requests.post(
        "https://api.daily.co/v1/rooms",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"properties": {"enable_chat": True}},
    )

    if response.status_code != 200:
        raise Exception(
            f"Failed to create room: {response.status_code} {response.text}"
        )

    room_data = response.json()
    return room_data["url"], room_name


def get_token(room_url: str) -> str:
    """Generate a token for the given Daily.co room."""
    api_key = os.getenv("DAILY_API_KEY")
    if not api_key:
        raise ValueError(
            "No Daily API key specified. Set DAILY_API_KEY in your environment."
        )

    room_name = urllib.parse.urlparse(room_url).path[1:]
    expiration = time.time() + 60 * 60  # 1 hour expiration

    response = requests.post(
        "https://api.daily.co/v1/meeting-tokens",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "properties": {"room_name": room_name, "is_owner": True, "exp": expiration}
        },
    )

    if response.status_code != 200:
        raise Exception(
            f"Failed to create meeting token: {response.status_code} {response.text}"
        )

    return response.json()["token"]

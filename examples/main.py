import os
import argparse
import json

from dotenv import load_dotenv
from typing import Optional
import uvicorn
from fastapi import FastAPI, WebSocket, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from foundation_voice.utils.transport.session_manager import session_manager
from foundation_voice.utils.transport.connection_manager import WebRTCOffer
import logging
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from foundation_voice.lib import CaiSDK
from foundation_voice.utils.config_loader import ConfigLoader

from agent_configure.utils.context import contexts
from agent_configure.utils.tool import tool_config
from agent_configure.utils.callbacks import custom_callbacks



cai_sdk = CaiSDK()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path1 = os.path.join(BASE_DIR, "agent_configure", "config", "agent_config.json")
config_path2 = os.path.join(BASE_DIR, "agent_configure", "config", "config_with_keys.json")
config_path3 = os.path.join(BASE_DIR, "agent_configure", "config", "basic_agent.json")



agent_config_1 = ConfigLoader.load_config(config_path1)
agent_config_2 = ConfigLoader.load_config(config_path2)
agent_config_3 = ConfigLoader.load_config(config_path3)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(
    title="CAI Voice Bot API",
    description="API for voice-based conversational AI applications using the Pipecat framework",
    version="1.0.0",
    docs_url=None,  
    redoc_url=None,  
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

defined_agents = {
    "agent1": {
        "config": agent_config_1, 
        "contexts": contexts,
        "tool_dict": tool_config,
        "callbacks": custom_callbacks,
    },
    "agent2": {
        "config": agent_config_2,
        "callbacks": custom_callbacks,
    },
    "agent3": {
        "config": agent_config_3,
        "contexts": contexts,
        "tool_dict": tool_config,
        "callbacks": custom_callbacks,
    }
}


@app.get(
    "/",
    response_model=dict,
    summary="Health Check",
    description="Returns a simple health check message to verify the API is running",
    tags=["System"],
)
async def index():
    return {"message": "welcome to cai"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = Query(None), agent_name: str = Query(None)):
    agent = defined_agents.get(agent_name) or next(iter(defined_agents.values()))
    await cai_sdk.websocket_endpoint_with_agent(websocket, agent, session_id)


@app.post("/api/offer")
async def webrtc_endpoint(offer: WebRTCOffer, background_tasks: BackgroundTasks, metadata: Optional[str] = Query(None)):
    agent_name = offer.agent_name or next(iter(defined_agents))
    agent = defined_agents.get(agent_name)

    parsed_metadata = {}

    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            print("Failed to decode metadata JSON")

    # Get both answer and connection_data
    response = await cai_sdk.webrtc_endpoint(offer, agent, parsed_metadata)
    if "background_task_args" in response:
        task_args = response.pop("background_task_args")
        func = task_args.pop("func")
        background_tasks.add_task(func, **task_args)

    return response["answer"]


@app.post("/connect")
async def connect_handler(background_tasks: BackgroundTasks, request: dict):
    agent_name = request.get("agent_name") or next(iter(defined_agents))
    agent = defined_agents.get(agent_name)

    response = await cai_sdk.connect_handler(request, agent)
    if "background_task_args" in response:
        task_args = response.pop("background_task_args")
        func = task_args.pop("func")
        background_tasks.add_task(func, **task_args)
    print("response: ", response)
    return response


@app.get("/sessions")
async def get_sessions():
    return {"active_sessions": len(session_manager.active_sessions)}


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title="CAI Voice Bot API",
        version="1.0.0",
        description="API for voice-based conversational AI applications",
        routes=app.routes,
    )


@app.get("/docs", include_in_schema=False)
async def get_documentation():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="CAI Voice Bot API",
        swagger_favicon_url="/client/favicon.ico",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Assistant Server")
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        default=False,
        help="set the server in testing mode",
    )
    args, _ = parser.parse_known_args()

    app.state.testing = args.test

    uvicorn.run(app, host="0.0.0.0", port=8000)
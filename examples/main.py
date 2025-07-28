import os
import argparse
import json

from dotenv import load_dotenv
from typing import Optional
import uvicorn
from fastapi import FastAPI, WebSocket, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from foundation_voice.utils.transport.session_manager import session_manager
from foundation_voice.utils.transport.connection_manager import WebRTCOffer
import logging
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from foundation_voice.lib import CaiSDK
from foundation_voice.utils.config_loader import ConfigLoader
from starlette.responses import HTMLResponse
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from xml.sax.saxutils import escape

from examples.agent_configure.utils.context import contexts
from examples.agent_configure.utils.tool import tool_config
from examples.agent_configure.utils.callbacks import custom_callbacks
from foundation_voice.utils.api_utils import auto_detect_transport
import uuid

# Load environment variables
load_dotenv()

# Initialize the SDK - it handles all complexity internally
cai_sdk = CaiSDK()

# Initialize Twilio client (optional, only needed for outbound calls)
twilio_client = None
if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
    twilio_client = TwilioClient(
        os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    )

# Load agent configurations (simplified)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path1 = os.path.join(BASE_DIR, "agent_configure", "config", "agent_config.json")
config_path2 = os.path.join(
    BASE_DIR, "agent_configure", "config", "config_with_keys.json"
)
config_path3 = os.path.join(BASE_DIR, "agent_configure", "config", "basic_agent.json")
config_path4 = os.path.join(
    BASE_DIR, "agent_configure", "config", "language_agent.json"
)

agent_config_1 = ConfigLoader.load_config(config_path1)
agent_config_2 = ConfigLoader.load_config(config_path2)
agent_config_3 = ConfigLoader.load_config(config_path3)
agent_config_4 = ConfigLoader.load_config(config_path4)

logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO if you only want info and above
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

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

# Simple agent definitions (user-friendly)
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
    },
    "agent4": {"config": agent_config_4},
}

metadata = {
    "transcript": [
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "my name is shubham"},
    ]
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


@app.post("/api/sip")
async def handle_sip_webhook(request: Request, agent_name: str = Query("agent1")):
    """
    Simple SIP webhook handler - complexity handled by SDK
    """
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    websocket_url = f"wss://{host}/ws?agent_name={agent_name}"

    # Simple TwiML response (no need for complex templating)
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{escape(websocket_url)}">
            <Parameter name="agent_name" value="{agent_name}" />
            <Parameter name="session_id" value="{uuid.uuid4()}" />
        </Stream>
    </Connect>
    <Pause length="40"/>
</Response>"""

    return HTMLResponse(content=twiml_response, media_type="application/xml")


@app.post("/api/sip/create-call")
async def create_sip_call(
    request: Request,
    to_number: str,
    from_number: Optional[str] = None,
    agent_name: str = "agent1",
):
    """
    Create outbound SIP call via Twilio (optional feature)
    """
    if not twilio_client:
        return {
            "error": "Twilio client not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        }

    try:
        twilio_phone_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        if not twilio_phone_number:
            return {"error": "Twilio phone number not provided or configured in .env"}

        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        webhook_url = f"https://{host}/api/sip?agent_name={agent_name}"

        call = twilio_client.calls.create(
            to=to_number, from_=twilio_phone_number, url=webhook_url
        )
        logger.info(f"Created Twilio call to {to_number} with SID: {call.sid}")
        return {"status": "success", "call_sid": call.sid}

    except TwilioRestException as e:
        logger.error(f"Twilio API error: {e}")
        return {"error": f"Twilio error: {e.msg}", "code": e.code}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Super simple WebSocket endpoint - SDK handles all complexity!
    Users just need to specify which agent to use.
    """
    logger.info("New WebSocket connection request received")

    try:
        await websocket.accept()
        logger.debug("WebSocket connection accepted")

        transport_type, sip_params = await auto_detect_transport(websocket)
        logger.info(f"Detected transport type: {transport_type}")

        if sip_params:
            logger.info("Processing SIP connection")
            if sip_params.get("customParameters"):
                logger.info(
                    f"Processing SIP connection with custom parameters{sip_params}"
                )
                agent_name = sip_params.get("agent_name", "agent1")
                session_id = sip_params.get("session_id")
                if not session_id:
                    logger.warning(
                        "No session_id provided in SIP params, generating new one"
                    )
                    session_id = str(uuid.uuid4())
                sip_params = sip_params.pop("customParameters")

            metadata = {"session_id": session_id}
            try:
                agent = defined_agents.get(agent_name)
                if not agent:
                    logger.warning(
                        f"Agent '{agent_name}' not found, using default agent"
                    )
                    agent = next(iter(defined_agents.values()))
            except (KeyError, StopIteration) as e:
                logger.error("No agents defined or error accessing agents")
                raise ValueError("No valid agents available") from e

            logger.info(
                f"Starting SIP call with agent '{agent_name}' and session '{session_id}'"
            )
            await cai_sdk.websocket_endpoint_with_agent(
                websocket,
                agent,
                transport_type,
                session_id=session_id,
                metadata=metadata,
                auto_hang_up=False,
                sip_params=sip_params,
            )

        else:
            logger.info("Processing standard WebSocket connection")
            query_params = dict(websocket.query_params)
            agent_name = query_params.get("agent_name", "agent1")
            session_id = query_params.get("session_id")
            # agent_name = websocket.query_params.get("agent_name", "agent1")
            # session_id = websocket.query_params.get("session_id")
            if not session_id:
                logger.warning(
                    "No session_id provided in query params, generating new one"
                )
                session_id = str(uuid.uuid4())

            metadata = {"session_id": session_id}
            try:
                agent = defined_agents.get(agent_name)
                if not agent:
                    logger.warning(
                        f"Agent '{agent_name}' not found, using default agent"
                    )
                    agent = next(iter(defined_agents.values()))
            except (KeyError, StopIteration) as e:
                logger.error("No agents defined or error accessing agents")
                raise ValueError("No valid agents available") from e

            logger.info(
                f"Starting WebSocket session with agent '{agent_name}' and session '{session_id}'"
            )
            await cai_sdk.websocket_endpoint_with_agent(
                websocket,
                agent,
                transport_type,
                session_id=session_id,
                metadata=metadata,
            )

    except ValueError as e:
        logger.error(f"Validation error in websocket endpoint: {e}")
        if not websocket.client_state.DISCONNECTED:
            await websocket.close(code=1008, reason=str(e))
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}", exc_info=True)
        if not websocket.client_state.DISCONNECTED:
            await websocket.close(code=1011, reason="Server Error")


@app.post("/api/offer")
async def webrtc_endpoint(
    offer: WebRTCOffer,
    background_tasks: BackgroundTasks,
    metadata: Optional[str] = Query(None),
):
    agent_name = offer.agent_name or next(iter(defined_agents))
    agent = defined_agents.get(agent_name)

    parsed_metadata = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            logger.warning("Failed to decode metadata JSON")

    response = await cai_sdk.webrtc_endpoint(
        offer, agent, session_id=offer.session_id, metadata=parsed_metadata
    )
    if "background_task_args" in response:
        task_args = response.pop("background_task_args")
        func = task_args.pop("func")
        background_tasks.add_task(func, **task_args)

    return response["answer"]


@app.post("/connect")
async def connect_handler(background_tasks: BackgroundTasks, request: dict):
    agent_name = request.get("agent_name") or next(iter(defined_agents))
    agent = defined_agents.get(agent_name)
    session_id = request.get("session_id")

    # response = await cai_sdk.connect_handler(request, agent, session_id=session_id, session_resume=session_resume)
    response = await cai_sdk.connect_handler(
        request, agent, session_id=session_id, metadata=metadata
    )
    if "websocket_url" in response:
        response["ws_url"] = f"ws://localhost:8000{response['websocket_url']}"
        del response["websocket_url"]
    if "background_task_args" in response:
        task_args = response.pop("background_task_args")
        func = task_args.pop("func")
        background_tasks.add_task(func, **task_args)

    return response


@app.get("/sessions")
async def get_sessions():
    active_session_ids = list(session_manager.active_sessions.keys())
    return {
        "active_sessions_count": len(active_session_ids),
        "active_session_ids": active_session_ids,
    }


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

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
from foundation_voice.utils.transport.transport import TransportType
import logging
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from foundation_voice.lib import CaiSDK
from foundation_voice.utils.config_loader import ConfigLoader
from starlette.responses import HTMLResponse
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from xml.sax.saxutils import escape

from agent_configure.utils.context import contexts
from agent_configure.utils.tool import tool_config
from agent_configure.utils.callbacks import custom_callbacks


# Initialize Twilio client
twilio_client = None
if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
    twilio_client = TwilioClient(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )


cai_sdk = CaiSDK()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path1 = os.path.join(BASE_DIR, "agent_configure", "config", "agent_config.json")
config_path2 = os.path.join(BASE_DIR, "agent_configure", "config", "config_with_keys.json")
config_path3 = os.path.join(BASE_DIR, "agent_configure", "config", "basic_agent.json")
config_path4 = os.path.join(BASE_DIR, "agent_configure", "config", "language_agent.json")



agent_config_1 = ConfigLoader.load_config(config_path1)
agent_config_2 = ConfigLoader.load_config(config_path2)
agent_config_3 = ConfigLoader.load_config(config_path3)
agent_config_4 = ConfigLoader.load_config(config_path4)

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
    },
    "agent4": {
        "config": agent_config_4
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


@app.post("/api/sip")
async def handle_sip_webhook(request: Request, agent_name: str = Query("agent1")):
    """
    Handles incoming call webhooks from SIP providers like Twilio.
    Returns TwiML to connect the call to a WebSocket stream.
    """
    # Note: For production, you'd want a more robust way to determine the host.
    # Using the request headers is good for many deployments.
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    websocket_url = f"wss://{host}/ws?agent_name={agent_name}&transport_type=sip"

    template_path = os.path.join(BASE_DIR, "templates", "sip_streams.xml")
    with open(template_path, "r") as f:
        twiml_template = f.read()

    # Escape the URL to ensure it's valid XML
    escaped_url = escape(websocket_url)
    twiml_response = twiml_template.replace("WSS_URL_PLACEHOLDER", escaped_url)

    return HTMLResponse(content=twiml_response, media_type="application/xml")


@app.post("/api/sip/create-call")
async def create_sip_call(request: Request, to_number: str, from_number: Optional[str] = None, agent_name: str = "agent1"):
    """
    Creates an outbound SIP call via Twilio.
    """
    if not twilio_client:
        return {"error": "Twilio client not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."}

    try:
        twilio_phone_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        if not twilio_phone_number:
            return {"error": "Twilio phone number not provided or configured in .env"}

        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        webhook_url = f"https://{host}/api/sip?agent_name={agent_name}"

        call = twilio_client.calls.create(
            to=to_number,
            from_=twilio_phone_number,
            url=webhook_url
        )
        return {"status": "success", "call_sid": call.sid}
    except TwilioRestException as e:
        logger.error(f"Twilio API error: {e}")
        return {"error": f"Twilio error: {e.msg}", "code": e.code}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles incoming WebSocket connections and routes them to the appropriate agent."""
    await websocket.accept()

    # More robust parameter parsing
    query_string = str(websocket.url.query) if websocket.url.query else ""
    query_params = dict(websocket.query_params)
    
    # Get client IP and headers for Twilio detection
    client_ip = websocket.client.host if websocket.client else "unknown"
    headers = dict(websocket.headers) if hasattr(websocket, 'headers') else {}
    
    # Debug logging with both logger and print
    print(f"🔍 WebSocket connected from IP: {client_ip}")
    print(f"🔍 Headers: {headers}")
    print(f"🔍 Raw query string: {query_string}")
    print(f"🔍 Parsed query params: {query_params}")
    print(f"🔍 WebSocket URL: {websocket.url}")
    
    logger.info(f"WebSocket connected from IP: {client_ip}")
    logger.info(f"Headers: {headers}")
    logger.info(f"Raw query string: {query_string}")
    logger.info(f"Parsed query params: {query_params}")
    logger.info(f"WebSocket URL: {websocket.url}")

    # Extract parameters with multiple fallback methods
    session_id = query_params.get("session_id")
    agent_name = query_params.get("agent_name", "agent1")
    transport_type = query_params.get("transport_type", "websocket")
    
    # ENHANCED SIP DETECTION LOGIC
    # 1. Check for AWS/Cloud IP patterns (Twilio uses AWS infrastructure)
    aws_patterns = [
        "54.", "18.", "52.", "34.", "184.", "3.", "13.", "44.", "35.", "99.",  # Common AWS prefixes
        "168.86.",  # New Twilio media IP range
        "177.71.",  # Twilio South America
        "103.",     # Asia-Pacific
        "185.",     # Europe
        "208.78.",  # North America
        "67.213.",  # North America Oregon
    ]
    
    # 2. Check headers for Twilio indicators
    user_agent = headers.get("user-agent", "").lower()
    origin = headers.get("origin", "").lower()
    twilio_headers = ["x-twilio", "twilio"] 
    has_twilio_headers = any(key.lower().startswith(prefix) for key in headers.keys() for prefix in twilio_headers)
    
    # 3. Multiple detection criteria
    is_aws_ip = any(client_ip.startswith(prefix) for prefix in aws_patterns)
    is_twilio_ua = "twilio" in user_agent
    is_likely_twilio = is_aws_ip or is_twilio_ua or has_twilio_headers
    
    # 4. FINAL DETECTION: Examine first message for Twilio signature
    detected_sip_from_message = False
    if transport_type == "websocket" and not query_params:
        try:
            print(f"🔍 No query params detected, examining first message for Twilio signature...")
            logger.info("No query params detected, examining first message for Twilio signature...")
            
            # Peek at the first message without consuming it
            first_message = await websocket.receive_text()
            print(f"📥 First message received: {first_message}")
            logger.info(f"First message received: {first_message}")
            
            # Check if it looks like Twilio's "connected" event
            try:
                parsed_msg = json.loads(first_message)
                if (parsed_msg.get("event") == "connected" and 
                    "protocol" in parsed_msg and 
                    "version" in parsed_msg):
                    print(f"🎯 DETECTED: Twilio 'connected' event - this is definitely a SIP call!")
                    logger.info("Detected Twilio 'connected' event - forcing SIP transport")
                    transport_type = "sip"
                    detected_sip_from_message = True
                    # We'll handle the handshake below
                else:
                    print(f"📤 Not a Twilio message, putting it back...")
                    logger.info("Not a Twilio message format")
                    # We need to somehow put this message back or handle it in websocket transport
                    # For now, we'll continue with websocket and let it handle the message
            except json.JSONDecodeError:
                print(f"📤 Not JSON, likely binary WebSocket data for regular transport")
                logger.info("Non-JSON message, likely websocket transport")
                # This is probably binary data for websocket transport
                
        except Exception as e:
            print(f"⚠️ Error examining first message: {e}")
            logger.warning(f"Error examining first message: {e}")
    
    # 5. Force SIP transport based on previous detection criteria
    elif transport_type == "websocket" and is_likely_twilio and not query_params:
        print(f"🔧 DETECTED: Likely Twilio call from IP {client_ip}")
        print(f"🔧 Detection criteria: AWS_IP={is_aws_ip}, Twilio_UA={is_twilio_ua}, Twilio_Headers={has_twilio_headers}")
        print(f"🔧 FORCING: Transport type to SIP")
        transport_type = "sip"
        logger.warning(f"Detected Twilio call from IP {client_ip}, forcing SIP transport")
    
    # Additional logging for transport type detection
    print(f"🔍 Detected transport_type: '{transport_type}' (Twilio detection: {is_likely_twilio})")
    print(f"🔍 Agent name: '{agent_name}'")
    logger.info(f"Detected transport_type: '{transport_type}' (Twilio detection: {is_likely_twilio})")
    logger.info(f"Agent name: '{agent_name}'")

    try:
        transport_enum = TransportType(transport_type)
        print(f"✅ Using transport: {transport_enum.value}")
        logger.info(f"Using transport: {transport_enum.value}")
    except ValueError as e:
        print(f"❌ Invalid transport type '{transport_type}', defaulting to websocket. Error: {e}")
        logger.error(f"Invalid transport type '{transport_type}', defaulting to websocket. Error: {e}")
        transport_enum = TransportType.WEBSOCKET

    kwargs = {}

    if transport_enum == TransportType.SIP:
        print(f"🚀 Initiating SIP transport handshake with Twilio...")
        logger.info("Initiating SIP transport handshake with Twilio...")
        try:
            # If we already read the first message during detection, use it
            if detected_sip_from_message:
                first_message_data = first_message  # We already have this from detection
                print(f"📥 Using already received Twilio message: {first_message_data}")
            else:
                # Perform Twilio-specific handshake for SIP calls
                # The first message is a 'connected' event, which we can ignore.
                first_message_data = await websocket.receive_text()
                print(f"📥 Received first Twilio message: {first_message_data}")
            
            logger.info(f"Received first Twilio message: {first_message_data}")

            # The second message contains the call details.
            call_data_str = await websocket.receive_text()
            print(f"📥 Received Twilio call data: {call_data_str}")
            logger.info(f"Received Twilio call data: {call_data_str}")
            
            call_data = json.loads(call_data_str)

            if call_data.get("event") != "start":
                print(f"❌ Expected 'start' event from Twilio, but got: {call_data.get('event')}")
                logger.error(f"Expected 'start' event from Twilio, but got: {call_data.get('event')}")
                await websocket.close(code=1011, reason="Handshake Error: Expected 'start' event.")
                return

            stream_sid = call_data.get("start", {}).get("streamSid")
            call_sid = call_data.get("start", {}).get("callSid")

            if not stream_sid or not call_sid:
                print(f"❌ Missing streamSid or callSid in Twilio start event: {call_data}")
                logger.error(f"Missing streamSid or callSid in Twilio start event: {call_data}")
                await websocket.close(code=1011, reason="Handshake Error: Missing SID.")
                return

            print(f"✅ SIP call connected successfully. Stream SID: {stream_sid}, Call SID: {call_sid}")
            logger.info(f"SIP call connected successfully. Stream SID: {stream_sid}, Call SID: {call_sid}")

            kwargs["sip_params"] = {"stream_sid": stream_sid, "call_sid": call_sid}

        except StopAsyncIteration:
            print(f"⚠️ WebSocket closed before Twilio handshake could complete.")
            logger.warning("WebSocket closed before Twilio handshake could complete.")
            return
        except json.JSONDecodeError as e:
            print(f"❌ Failed to decode JSON from Twilio during handshake: {e}")
            logger.error(f"Failed to decode JSON from Twilio during handshake: {e}")
            await websocket.close(code=1011, reason="Handshake Error: Invalid JSON.")
            return
        except Exception as e:
            print(f"❌ An unexpected error during Twilio handshake: {e}")
            logger.error(f"An unexpected error during Twilio handshake: {e}", exc_info=True)
            await websocket.close(code=1011, reason="Handshake Error: Unexpected error.")
            return

    # Pass all necessary parameters to the agent runner
    kwargs["transport_type"] = transport_enum
    agent = defined_agents.get(agent_name) or next(iter(defined_agents.values()))
    
    print(f"🎯 Starting agent with transport: {transport_enum.value}")
    logger.info(f"Starting agent with transport: {transport_enum.value}")
    await cai_sdk.websocket_endpoint_with_agent(websocket, agent, session_id, **kwargs)


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
    response = await cai_sdk.webrtc_endpoint(offer, agent, metadata=parsed_metadata)
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
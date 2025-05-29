import argparse
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, WebSocket, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from agent.agent import run_agent
from utils.transport.session_manager import session_manager
from utils.transport.connection_manager import connection_manager, WebRTCOffer
import aiohttp
import logging
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Pipecat Voice Bot API",
    description="API for voice-based conversational AI applications using the Pipecat framework",
    version="1.0.0",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    response_model=dict,
    summary="Health Check",
    description="Returns a simple health check message to verify the API is running",
    tags=["System"],
)
async def index():
    """
    Health check endpoint that returns a simple status message.

    Returns:
        dict: A dictionary containing a status message
    """
    return {"message": "Ok. Working"}


@app.get("/client")
async def serve_index():
    return FileResponse("client/index.html")


@app.get("/frames.proto")
async def serve_proto():
    return FileResponse("client/frames.proto")


# WebSocket Connection
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for the AI assistant."""
    await websocket.accept()
    print("WebSocket connection accepted")
    try:
        await run_agent("websocket", connection=websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


# WebRTC Connection
@app.post("/api/offer")
async def webrtc_endpoint(offer: WebRTCOffer, background_tasks: BackgroundTasks):
    """WebRTC endpoint for the AI assistant.

    Args:
        offer: Validated WebRTC offer data
        background_tasks: FastAPI background tasks handler
    """
    # Check if there's an existing session for this pc_id
    if offer.pc_id and session_manager.get_webrtc_session(offer.pc_id):
        logger.info(f"Reusing existing WebRTC session for pc_id: {offer.pc_id}")
        answer, connection = await connection_manager.handle_webrtc_connection(offer)
        return answer

    # Create new connection and session
    answer, connection = await connection_manager.handle_webrtc_connection(offer)
    background_tasks.add_task(
        run_agent, "webrtc", connection=connection, session_id=answer["pc_id"]
    )
    return answer


# Daily Connection
@app.get("/daily")
async def daily_endpoint(background_tasks: BackgroundTasks):
    """Daily.co endpoint for the AI assistant."""
    try:
        async with aiohttp.ClientSession() as session:
            url, token = await connection_manager.handle_daily_connection(session)

            # Check if there's already a bot in this Daily room
            existing_session = session_manager.get_daily_room_session(url)
            if existing_session:
                logger.info(f"Bot already exists in Daily room: {url}")
                return HTMLResponse(
                    content=f"""
                    <html>
                        <head>
                            <title>Redirecting to Daily.co Room</title>
                            <script>
                                window.location.href = "{url}";
                            </script>
                        </head>
                        <body>
                            <p>Redirecting to Daily.co room...</p>
                        </body>
                    </html>
                """,
                    status_code=200,
                )

            # Run the agent with Daily transport in the background
            background_tasks.add_task(
                run_agent, "daily", room_url=url, token=token, bot_name="AI Assistant"
            )

            # Return HTML that automatically redirects to the Daily room
            html_content = f"""
            <html>
                <head>
                    <title>Redirecting to Daily.co Room</title>
                    <script>
                        window.location.href = "{url}";
                    </script>
                </head>
                <body>
                    <p>Redirecting to Daily.co room...</p>
                </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        return {"error": f"Failed to establish Daily.co connection: {str(e)}"}


# RTVI / Daily Transport Connection (used by the JavaScript client)
# RTVI / Daily Transport Connection (used by the JavaScript client)
@app.post("/connect")
async def rtvi_connect(
    background_tasks: BackgroundTasks,
    request: dict = Body(...),
):
    """RTVI connect endpoint that handles different transport types.

    Supports WebSocket, WebRTC, and Daily.co transport types. Based on the
    transport type specified in the request, it will establish the
    appropriate connection and return relevant credentials.
    """
    try:
        transport_type = request.get("transportType", "").lower()

        if transport_type == "websocket":
            # For WebSocket, return the WebSocket URL
            websocket_url = "ws://localhost:8000/ws"  # Adjust based on your setup
            return {"websocket_url": websocket_url}

        elif transport_type == "smallwebrtc":
            offer_url = "http://localhost:8000/api/offer"  # Adjust based on your setup
            return {
                "offer_url": offer_url,
                "webrtc_ui_url": "/webrtc",  # URL to the WebRTC UI
            }

        elif transport_type == "daily":
            # Handle Daily.co connection
            async with aiohttp.ClientSession() as session:
                url, token = await connection_manager.handle_daily_connection(session)

                # If a bot is not already active in this Daily room, launch one
                if not session_manager.get_daily_room_session(url):
                    background_tasks.add_task(
                        run_agent,
                        "daily",
                        room_url=url,
                        token=token,
                        bot_name="AI Assistant",
                    )

                return {"room_url": url, "token": token}

        else:
            return {"error": f"Unsupported transport type: {transport_type}"}

    except Exception as e:
        return {"error": f"Failed to establish connection: {str(e)}"}


# Add a new endpoint to get active sessions (optional, for monitoring)
@app.get("/sessions")
async def get_sessions():
    """Get count of active sessions."""
    return {"active_sessions": len(session_manager.active_sessions)}


# Add custom OpenAPI endpoint
@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title="Pipecat Voice Bot API",
        version="1.0.0",
        description="API for voice-based conversational AI applications",
        routes=app.routes,
    )


# Add custom Swagger UI endpoint
@app.get("/docs", include_in_schema=False)
async def get_documentation():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Pipecat Voice Bot API",
        swagger_favicon_url="/client/favicon.ico",
    )


# Example of documenting the WebRTC endpoint
@app.post(
    "/connect/webrtc",
    response_model=dict,
    summary="Initialize WebRTC Connection",
    description="Creates or renegotiates a WebRTC connection",
    tags=["Connection"],
)
async def handle_webrtc_connection(
    offer: WebRTCOffer = Body(
        ...,
        description="WebRTC connection offer details",
        example={
            "sdp": "v=0\no=- 123456789...",
            "type": "offer",
            "pc_id": None,
            "restart_pc": False,
        },
    ),
):
    """
    Handle WebRTC connection initialization or renegotiation.

    Args:
        offer: WebRTC offer containing SDP and connection details

    Returns:
        dict: WebRTC answer containing connection details
    """
    answer, connection = await connection_manager.handle_webrtc_connection(offer)
    return answer


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

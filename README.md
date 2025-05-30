# Foundational AI Server SDK

Welcome to the Foundational AI Server SDK! This SDK provides the core functionalities for building voice-based conversational AI applications using the Pipecat framework. It allows you to configure and run sophisticated AI agents capable of voice activity detection (VAD), speech-to-text (STT), language model processing (LLM), and text-to-speech (TTS).

This guide will walk you through setting up the SDK, configuring your agent, creating custom server endpoints, and utilizing callbacks.

## 1. Installation

To install the SDK, ensure you have Python 3.8 or higher. You can install the package directly from the GitHub repository using pip:

```bash
pip install "git+ssh://git@github.com/think41/foundational-ai-server.git#egg=foundational_ai_server"
```

This command will install the `foundational_ai_server` package and all its dependencies as listed in `pyproject.toml`.

### Environment Variables

Many services used by the SDK (like STT, LLM, TTS providers) require API keys. These should be set as environment variables. Create a `.env` file in your project's root directory (where you run your main application) with the necessary keys. Example:

```
# For OpenAI (LLM and TTS)
OPENAI_API_KEY="your_openai_api_key"

# For Deepgram (STT and TTS)
DEEPGRAM_API_KEY="your_deepgram_api_key"

# For Cartesia (TTS)
CARTESIA_API_KEY="your_cartesia_api_key"

# For Daily.co (Transport)
DAILY_API_KEY="your_daily_api_key"
DAILY_SAMPLE_ROOM_URL="your_daily_room_url_if_testing_daily"
```

Refer to the specific provider's documentation for how to obtain API keys.

## 2. Creating a Configuration File

The SDK uses a JSON file to configure the agent and the processing pipeline. You can create your own configuration file (e.g., `my_agent_config.json`).

Here's a breakdown of the main sections and options:

```json
{
  "agent": {
    "title": "My Custom Bot",
    "initial_greeting": "Hello! How can I help you today?",
    "prompt": "You are a helpful assistant.",
    "transport": {
      "type": "webrtc" // Supported: "webrtc", "websocket", "daily"
    },
    "vad": {
      "provider": "silero" // Supported: "silero", "none"
    },
    "stt": {
      "provider": "deepgram" // Supported: "deepgram" (ensure DEEPGRAM_API_KEY is set)
      // Add other STT provider configs if supported by the SDK
    },
    "llm": {
      "provider": "openai", // Supported: "openai", "openai_agents"
      "model": "gpt-4o-mini", // For "openai" provider
      // API Key: Set OPENAI_API_KEY environment variable
      "agent_config": { // Specific to "openai_agents" provider
        "start_agent": "main_agent",
        "context": "MyCustomContext", // Maps to a class in context.py
        "logfire_trace": true,
        "agents": {
          "main_agent": {
            "name": "Main Agent",
            "instructions": "Instructions for the main agent...",
            "handoff_description": "When to hand off...",
            "handoffs": ["another_agent"],
            "tools": ["my_custom_tool"], // Maps to tools in tools.py
            "context": "MyCustomContext"
          }
          // Define other agents if using a multi-agent setup
        }
      }
    },
    "tts": {
      "provider": "openai", // Supported: "openai", "cartesia", "deepgram"
      "voice": "alloy", // Specific to the provider (e.g., OpenAI voices)
      // API Key: Set relevant environment variables (OPENAI_API_KEY, CARTESIA_API_KEY, DEEPGRAM_API_KEY)
    },
    "mcp": { 
      "type": "llm_orchestrator",
      "config": {
        "max_turns": 10,
        "response_timeout": 15,
        "history_length": 5,
        "enable_tool_selection": true,
        "tool_selection_strategy": "highest_confidence"
      }
    }
  },
  "pipeline": {
    "name": "my_pipeline",
    "stages": [
      { "type": "input", "config": {} },
      { "type": "vad", "config": {} },
      { "type": "stt", "config": {} },
      { "type": "llm", "config": { "use_tools": true } }, // "use_tools" enables tool usage for LLM
      { "type": "tts", "config": {} },
      { "type": "output", "config": {} }
    ]
  }
}
```

**Key Configuration Details:**

*   **`agent` Section:**
    *   `transport.type`: Choose how the client will connect (e.g., `webrtc`, `websocket`, `daily`).
    *   `vad.provider`: `silero` is a common choice. Use `none` to disable VAD.
    *   `stt.provider`: Example `deepgram`. Ensure the corresponding API key (e.g., `DEEPGRAM_API_KEY`) is in your `.env` file.
    *   `llm.provider`:
        *   `openai`: Uses a standard OpenAI model. Set `model` (e.g., `gpt-4o-mini`). Requires `OPENAI_API_KEY`.
        *   `openai_agents`: For multi-agent setups. Configure `start_agent`, `agents` dictionary with individual agent instructions, tools, handoffs, and context.
    *   `llm.agent_config.context`: A string name that maps to a Pydantic `BaseModel` class you define (see Custom Contexts below).
    *   `llm.agent_config.agents.*.tools`: A list of tool names that map to functions (see Custom Tools below).
    *   `tts.provider`: Examples `openai`, `cartesia`, `deepgram`. Set `voice` and ensure the API key is in `.env`.
*   **`pipeline` Section:**
    *   Defines the sequence of processing stages. The example shows a typical voice pipeline.

### Custom Contexts

To manage state or share data across agent interactions, you can define custom context classes. These classes should inherit from Pydantic's `BaseModel`.

1.  Open/Create `foundational_ai_server/agent_configure/utils/context.py` (or your custom path if you modify the loading logic).
2.  Define your context class:
    ```python
    from pydantic import BaseModel

    class MyCustomContext(BaseModel):
        user_id: str | None = None
        session_data: dict = {}
        # Add other fields relevant to your application
    ```
3.  Register it in the `contexts` dictionary in the same file:
    ```python
    contexts = {
        "MyCustomContext": MyCustomContext,
        # Add other contexts here
        "MagicalNestContext": MagicalNestContext # Existing example
    }
    ```
4.  You can then reference `"MyCustomContext"` in your `agent_config.json`.

### Custom Tools

For agents to perform actions, you can define tools.

1.  Define tool functions in `foundational_ai_server/custom_plugins/services/openai_agents/agents_sdk/utils/tools.py` (or your custom path).
    ```python
    from agents import function_tool, RunContextWrapper # Assuming 'agents' library is used

    @function_tool
    def my_custom_tool(ctx: RunContextWrapper, parameter: str):
        # ctx.context gives access to the agent's context (e.g., MyCustomContext instance)
        # Perform some action with 'parameter'
        return f"Tool executed with {parameter}"
    ```
2.  Register these tools in the `tool_config` dictionary in `foundational_ai_server/agent_configure/utils/tool.py`:
    ```python
    from foundational_ai_server.custom_plugins.services.openai_agents.agents_sdk.utils.tools import my_custom_tool # Import your tool

    tool_config = {
        "my_custom_tool": my_custom_tool,
        # Add other tools here
        "weather_tool": weather_tool # Existing example
    }
    ```
3.  Reference `"my_custom_tool"` in the `tools` list for an agent in your `agent_config.json`.

## 3. Creating Server Endpoints

You can integrate the `CaiSDK` into your own FastAPI (or other ASGI framework) application to expose communication endpoints. Here's an example based on `examples/main.py`:

```python
# main_app.py (your application file)
import uvicorn
from fastapi import FastAPI, WebSocket, BackgroundTasks, Request
from dotenv import load_dotenv

from foundational_ai_server.lib import CaiSDK
from foundational_ai_server.utils.transport.connection_manager import WebRTCOffer
# Import your tool_config and custom_callbacks
from foundational_ai_server.agent_configure.utils.tool import tool_config
from foundational_ai_server.agent_configure.utils.callbacks import custom_callbacks, AgentCallbacks # AgentCallbacks for type hinting

# Load .env file from your project root
load_dotenv()

app = FastAPI()

# Initialize the SDK
# You can optionally pass a default agent_config dictionary here if you don't want it loaded by run_agent
# cai_sdk = CaiSDK(agent_config=your_loaded_config_dict)
cai_sdk = CaiSDK()

@app.get("/")
async def health_check():
    return {"status": "healthy"}

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # The agent_config, tools, and callbacks might be implicitly handled by the default run_agent
    # or passed if CaiSDK was initialized with a global agent_config.
    # For more explicit control per call, see the /connect endpoint example.
    await cai_sdk.websocket_endpoint(websocket)

@app.post("/api/offer") # For WebRTC offers
async def webrtc_offer_endpoint(offer: WebRTCOffer, background_tasks: BackgroundTasks):
    # Pass your specific tool configurations and callback handlers
    return await cai_sdk.webrtc_endpoint(offer, background_tasks, tool_config, custom_callbacks)

@app.post("/connect") # General connection handler
async def handle_connect(request_data: dict, background_tasks: BackgroundTasks):
    # request_data might contain 'transportType', 'agentConfig', 'sdp', 'type', etc.
    # This allows dynamic configuration per connection if needed.
    # The 'agentConfig' from request_data can override SDK's initial config for this call.
    return await cai_sdk.connect_handler(background_tasks, request_data, tool_config, custom_callbacks)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Explanation:**

1.  Import necessary modules, including `CaiSDK`, `WebRTCOffer`, your `tool_config`, and `custom_callbacks`.
2.  Initialize `CaiSDK()`. You can pass a default `agent_config` dictionary here, or it can be provided per call via the `/connect` endpoint.
3.  Define FastAPI routes for different transport types (`/ws` for WebSocket, `/api/offer` for WebRTC offers).
4.  The `/connect` endpoint is a versatile handler that can manage different transport types based on the `request_data` payload. It can also receive an `agentConfig` in the request to dynamically configure the agent for that specific session.
5.  Pass your `tool_config` and `custom_callbacks` instance to the relevant SDK methods (`webrtc_endpoint`, `connect_handler`).

## 4. Utilizing Callbacks

The SDK allows you to hook into various agent events using a callback system. This is useful for logging, custom event handling, or integrating with other systems.

**Available Events (`AgentEvent` enum in `foundational_ai_server.custom_plugins.agent_callbacks`):**

*   `CLIENT_CONNECTED`
*   `CLIENT_DISCONNECTED`
*   `FIRST_PARTICIPANT_JOINED`
*   `PARTICIPANT_LEFT`
*   `SESSION_TIMEOUT`
*   `TRANSCRIPT_UPDATE`

**Steps to Use Callbacks:**

1.  **Define Callback Functions:** Create Python functions that will handle specific events. These functions should be `async`.
    ```python
    # my_callbacks.py (or within your main application file)
    from foundational_ai_server.custom_plugins.agent_callbacks import AgentEvent, AgentCallbacks
    from loguru import logger

    async def my_transcript_handler(frame):
        # Process transcript frames (e.g., from pipecat.frames.frames.TranscriptionFrame)
        for message in frame.messages:
            logger.info(f"Live Transcript ({message.role}): {message.content}")

    async def my_client_disconnected_handler(data: dict):
        logger.warning(f"Client disconnected. Session ID: {data.get('session_id')}")
        if data.get('metrics'):
            logger.info(f"Call Metrics: {data['metrics']}")
        # Perform cleanup or logging

    # ... define other handlers as needed
    ```

2.  **Register Callbacks:** Create an instance of `AgentCallbacks` and register your handler functions.
    You can modify the existing `custom_callbacks` instance found in `foundational_ai_server/agent_configure/utils/callbacks.py` or create a new one.

    *Modifying existing `custom_callbacks` (in `foundational_ai_server/agent_configure/utils/callbacks.py`):*
    ```python
    from foundational_ai_server.custom_plugins.agent_callbacks import AgentCallbacks, AgentEvent
    # Import your custom handlers
    # from .my_app_specific_handlers import my_transcript_handler, my_client_disconnected_handler

    custom_callbacks = AgentCallbacks() # Instantiates with default (pass-through) handlers

    # Example: Override default transcript handler
    # async def custom_on_transcript_update(frame):
    # print(f"Custom Transcript: {frame}")
    # custom_callbacks.register_callback(AgentEvent.TRANSCRIPT_UPDATE, custom_on_transcript_update)

    # If your handlers are defined elsewhere:
    # custom_callbacks.register_callback(AgentEvent.TRANSCRIPT_UPDATE, my_transcript_handler)
    # custom_callbacks.register_callback(AgentEvent.CLIENT_DISCONNECTED, my_client_disconnected_handler)
    ```

    *Creating a new `AgentCallbacks` instance in your application:*
    ```python
    # In your main_app.py
    from foundational_ai_server.custom_plugins.agent_callbacks import AgentCallbacks, AgentEvent
    # Import your handlers
    # from .my_callbacks import my_transcript_handler, my_client_disconnected_handler

    app_callbacks = AgentCallbacks()
    # app_callbacks.register_callback(AgentEvent.TRANSCRIPT_UPDATE, my_transcript_handler)
    # app_callbacks.register_callback(AgentEvent.CLIENT_DISCONNECTED, my_client_disconnected_handler)
    ```

3.  **Pass to SDK:** When calling SDK methods like `webrtc_endpoint` or `connect_handler` in your FastAPI endpoints, pass your `AgentCallbacks` instance.
    ```python
    # In your main_app.py, inside an endpoint function:
    # If using a new instance:
    # return await cai_sdk.connect_handler(background_tasks, request_data, tool_config, app_callbacks)
    # If using the modified custom_callbacks from the SDK files:
    from foundational_ai_server.agent_configure.utils.callbacks import custom_callbacks
    return await cai_sdk.connect_handler(background_tasks, request_data, tool_config, custom_callbacks)
    ```

This setup allows you to react to key events in the agent's lifecycle and processing pipeline.

## Further Exploration

*   **Multi-Agent Scenarios:** Explore the `llm.agent_config.agents` section in the JSON configuration for setting up multiple interacting agents with handoffs.
*   **Advanced Tools:** Tools can access shared context via `ctx.context` for more stateful operations.
*   **Custom Pipeline Stages:** While not covered here, the Pipecat framework (which this SDK builds upon) allows for creating custom pipeline stages if needed.

We hope this guide helps you get started with the Foundational AI Server SDK! If you have any questions or encounter issues, please refer to the source code or raise an issue on the GitHub repository.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A robust Python framework for building AI-powered voice applications using the Pipecat framework. This package provides essential tools and integrations for creating sophisticated voice-based conversational AI applications with ease.

## ✨ Features

- 🎙️ Voice interaction capabilities
- 🤖 AI-powered conversation management
- 🛠️ Extensible plugin architecture
- 🔌 Multiple AI provider integrations (OpenAI, Deepgram, etc.)
- 🚀 FastAPI-based web server
- 📊 Real-time analytics and monitoring
- 🔄 WebRTC support for real-time communication

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Git
- pip (Python package manager)

### Installation

You can install the package directly from GitHub using pip:

```bash
# Using HTTPS
pip install git+https://github.com/think41/foundational-ai-server.git

# Or using SSH (if you have SSH keys set up)
pip install git+ssh://git@github.com/think41/foundational-ai-server.git
```

Or add it to your `requirements.txt`:

```
git+https://github.com/think41/foundational-ai-server.git#egg=foundational_ai_server
```

## 🏗️ Project Structure

```
foundational-ai-server/
├── foundational_ai_server/     # Main package
│   ├── agent/                  # Agent implementation
│   ├── agent_configure/        # Agent configuration
│   ├── custom_plugins/         # Custom plugins
│   │   ├── frames/            # Frame definitions
│   │   ├── processors/        # Data processors
│   │   └── services/          # Service integrations
│   └── utils/                  # Utility functions
├── examples/                   # Example implementations
├── tests/                      # Test suite
├── .env.example               # Example environment variables
├── pyproject.toml             # Project configuration
└── README.md                  # This file
```

## 🛠️ Configuration

1. Update the `.env` file with your API keys and configuration:

```env
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
DAILY_API_KEY=your_daily_api_key
DAILY_SAMPLE_ROOM_URL=your_daily_room_url
```

## 🚀 Running the Example

1. Navigate to the examples directory:

```bash
cd examples
```

2. Run the example server:

```bash
uvicorn main:app --reload
```

3. Open your browser and navigate to `http://localhost:8000`



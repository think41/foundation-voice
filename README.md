# Foundational AI Server SDK

## 1. Introduction

Welcome to the Foundational AI Server SDK! This SDK provides the core functionalities for building voice-based conversational AI applications using the Pipecat framework. It allows you to configure and run sophisticated AI agents capable of:

- Voice Activity Detection (VAD)
- Speech-to-Text (STT) conversion
- Language Model Processing (LLM)
- Text-to-Speech (TTS) synthesis

This guide will walk you through setting up the SDK, configuring your agent, creating custom server endpoints, and utilizing callbacks to build powerful conversational AI applications.

## 2. Installation

To install the SDK, ensure you have Python 3.8 or higher. You can install the package directly from the GitHub repository using pip:

```bash
# Always use a virtual environment for Python projects
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the SDK
pip install "git+ssh://git@github.com/think41/foundational-ai-server.git#egg=foundational_ai_server"
```

This command will install the `foundational_ai_server` package and all its dependencies as listed in `pyproject.toml`.

### 2.1 Environment Variables

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

## 3. Basic Implementation Example

Here's a minimal example of implementing agent callbacks and tool configuration with a `/connect` endpoint in `main.py`:

```python
# main.py
import uvicorn
from fastapi import FastAPI, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional

from foundational_ai_server.lib import CaiSDK
from foundational_ai_server.agent_configure.utils.callbacks import AgentCallbacks
from foundational_ai_server.agent_configure.utils.tool import tool_config

# 1. Create a custom context model
class MyContext(BaseModel):
    user_id: Optional[str] = None
    conversation_history: list = []

# 2. Define your tool functions
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    # Replace with actual weather API call
    return f"The weather in {location} is sunny."

# 3. Create custom callbacks
class MyCallbacks(AgentCallbacks):
    async def on_agent_start(self, context: Dict[str, Any]):
        print(f"Agent started with context: {context}")

    async def on_agent_end(self, context: Dict[str, Any]):
        print(f"Agent ended with context: {context}")

    async def on_tool_call(self, tool_name: str, tool_args: Dict[str, Any]):
        print(f"Tool called: {tool_name} with args: {tool_args}")

# 4. Initialize FastAPI and SDK
app = FastAPI()
cai_sdk = CaiSDK()

# 5. Create /connect endpoint
@app.post("/connect")
async def connect_endpoint(
    request_data: dict, 
    background_tasks: BackgroundTasks
):
    # Initialize callbacks and tools
    callbacks = MyCallbacks()
    tool_config["get_weather"] = get_weather
    context = MyContext()

    # Handle the connection
    return await cai_sdk.connect_handler(
        background_tasks=background_tasks,
        request_data=request_data,
        tool_config=tool_config,
        app_callbacks=callbacks,
        context=context  # Pass your custom context
    )

# 6. Run the application
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

### 3.1 Example Explanation


1. **Tool Functions**: Define regular Python functions that your agent can call. Each tool has a docstring, type hints, and a meaningful name.

2. **Custom Callbacks**: The `AgentCallbacks` class provides hooks for various agent events. You can override these methods to add custom behavior

3. **SDK Initialization**: Create a FastAPI app and initialize the SDK.

4. **Connect Endpoint**: Set up an endpoint that initializes callbacks, registers tools, and handles connections.

5. **Application Execution**: Run the FastAPI application with Uvicorn.

6. **Configuration**: To configure the agent, create a JSON file with the agent configuration and put it's path in the .env file. below you will find an example and explanation of a configuration file.

## 4. Core Concepts

The Foundational AI Server SDK is built around several key concepts that work together to create a flexible and powerful conversational AI system:

### 4.1 Agent Configuration

Agent configuration defines the behavior, capabilities, and components of your AI agent. This includes:

- **Transport**: How clients connect to your agent (WebSocket, WebRTC, Daily.co)
- **Voice Processing**: VAD, STT, and TTS settings
- **Language Model**: Which LLM to use and how to configure it
- **Prompts**: Instructions that guide the agent's behavior

You can configure these through a JSON file. [Jump to Configuration File](#5-creating-a-configuration-file)

### 4.2 Tool Configuration

Tools are functions that extend your agent's capabilities, allowing it to perform actions beyond conversation. Tools can:

- Access external APIs or databases
- Modify application state
- Perform calculations or data processing
- Interact with other systems

Tools are registered in the `tool_config` dictionary. [Jump to Using Custom Tools](#6-using-custom-tools)

### 4.3 Callbacks

Callbacks provide hooks into the agent's lifecycle, allowing your application to respond to events such as:

- Agent starting/ending
- Tool calls
- Transcript updates
- Client connections/disconnections

Callbacks enable integration with your application logic. [Jump to Transport and Callbacks](#7-transport-and-callbacks-guide)

## 5. Creating a Configuration File

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
      "provider": "deepgram",
      "model": "nova-2"
    },
    "llm": {
      "provider": "openai", // Supported: "openai", "openai_agents"
      "model": "gpt-4o-mini", // For "openai" provider
      "api_key": "${OPENAI_API_KEY}" // Will be replaced with the env var value
    },
    "tts": {
      "provider": "openai", // Supported: "openai", "deepgram", "cartesia"
      "voice": "alloy" // For "openai" provider
    }
  },
  "pipeline": {
    "name": "my_pipeline",
    "stages": [
      { "type": "input", "config": {} },
      { "type": "vad", "config": {} },
      { "type": "stt", "config": {} },
      { "type": "llm", "config": { "use_tools": true } },
      { "type": "tts", "config": {} },
      { "type": "output", "config": {} }
    ]
  }
}
```

### 5.1 Configuration Options Explained

1. **Agent Settings**:
   - `title`: The name of your agent
   - `initial_greeting`: First message sent by the agent
   - `prompt`: System prompt that defines the agent's behavior

2. **Transport Configuration**:
   - `agent.transport.type`: Choose how the client will connect (`webrtc`, `websocket`, `daily`)

3. **Voice Activity Detection**:
   - `agent.vad.provider`: `silero` is recommended. Use `none` to disable VAD.

4. **Speech-to-Text**:
   - `agent.stt.provider`: Example `deepgram`. Requires the corresponding API key in your `.env` file.
   - `agent.stt.model`: Model to use (provider-specific)

5. **Language Model**:
   - `agent.llm.provider`: Example `openai`. Requires `OPENAI_API_KEY` in your `.env` file.
   - `agent.llm.model`: Model name (e.g., `gpt-4o-mini`)
   - For multi-agent setups, use `openai_agents` provider with additional configuration

6. **Text-to-Speech**:
   - `agent.tts.provider`: Example `openai`. Requires the corresponding API key.
   - `agent.tts.voice`: Voice ID to use (provider-specific)

7. **Pipeline Configuration**:
   - Defines the sequence of processing stages for your agent
   - The `use_tools: true` setting in the LLM stage enables tool usage

### 5.2 Example Configurations

#### 5.2.1 Basic Example with OpenAI

This is a simple configuration using OpenAI for both LLM and TTS:

```json
{
  "agent": {
    "title": "Customer Support Bot",
    "initial_greeting": "Hello! I'm your customer support assistant. How can I help you today?",
    "prompt": "You are a helpful customer support assistant for a software company. Answer questions about our products, pricing, and provide technical support. Be friendly, concise, and professional.",
    "transport": {
      "type": "webrtc"
    },
    "vad": {
      "provider": "silero"
    },
    "stt": {
      "provider": "deepgram",
      "model": "nova-2"
    },
    "llm": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.7,
      "max_tokens": 150,
    },
    "tts": {
      "provider": "openai",
      "voice": "nova"
    }
  },
  "pipeline": {
    "name": "support_pipeline",
    "stages": [
      { "type": "input", "config": {} },
      { "type": "vad", "config": {} },
      { "type": "stt", "config": {} },
      { "type": "llm", "config": { "use_tools": true } },
      { "type": "tts", "config": {} },
      { "type": "output", "config": {} }
    ]
  }
}
```

**Explanation:**

1. **Agent Configuration**:
   - `title`: Names the bot "Customer Support Bot" - this will be displayed to users
   - `initial_greeting`: The first message users will hear when connecting
   - `prompt`: System instructions that define the bot's personality and capabilities

2. **Transport**:
   - Uses WebRTC for real-time audio communication (requires browser support)

3. **Voice Processing**:
   - `vad`: Uses Silero for voice activity detection to determine when the user is speaking
   - `stt`: Configures Deepgram with the nova-2 model for speech-to-text conversion
   - `tts`: Uses OpenAI's nova voice for text-to-speech synthesis

4. **Language Model**:
   - `provider`: Uses OpenAI's API
   - `model`: Specifies gpt-4o-mini as the model
   - `temperature`: Sets creativity level to 0.7 (moderate creativity)
   - `max_tokens`: Limits responses to 150 tokens for concise answers

5. **Pipeline**:
   - Defines a linear processing flow from input to output
   - `use_tools: true` in the LLM stage enables the bot to use custom tool functions

#### 5.2.2 Complex Example with OpenAI Agents

This example demonstrates a multi-agent system using `openai_agents` provider, similar to the MagicalNest Bot configuration:

```json
{
  "agent": {
    "title": "E-Commerce Assistant",
    "initial_greeting": "Welcome to our online store! I'm here to help you find the perfect products.",
    "prompt": "You are a helpful and informative assistant for an e-commerce platform. Please provide accurate and concise responses, and you have access to tools.",
    "transport": {
      "type": "daily-webrtc"
    },
    "vad": {
      "provider": "silero"
    },
    "stt": {
      "provider": "deepgram"
    },
    "llm": {
      "provider": "openai_agents",
      "logfire_trace": true,
      "triage": false,
      "agent_config": {
        "start_agent": "welcome_agent",
        "context": "ShoppingContext",
        "logfire_trace": true,
        "agents": {
          "welcome_agent": {
            "name": "welcome_agent",
            "instructions": "You are the Welcome Agent for an e-commerce platform.\nIMPORTANT: Keep all responses SHORT, CRISP and CONVERSATIONAL - suitable for a voice interface.\nLimit responses to 1-2 short sentences whenever possible.\nYour responsibilities:\n- Warmly welcome customers to the store\n- Ask about what type of products they're looking for\n- Collect basic information about their preferences\n\nBe friendly and professional.\nAsk only ONE question at a time.\n\nWhen you've collected basic information, hand off to the Product Agent.",
            "handoff_description": "When the conversation starts or needs to return to introduction",
            "handoffs": ["product_agent"],
            "tools": ["update_customer_info"],
            "context": "ShoppingContext"
          },
          "product_agent": {
            "name": "product_agent",
            "instructions": "You are the Product Agent for an e-commerce platform.\nIMPORTANT: Keep all responses SHORT, CRISP and CONVERSATIONAL - suitable for a voice interface.\nLimit responses to 1-2 short sentences whenever possible.\n\nYour responsibilities:\n- Recommend products based on customer preferences\n- Provide details about products (features, pricing, availability)\n- Help customers compare different options\n- Add items to the shopping cart\n\nBe knowledgeable and helpful. Focus on suggesting products that match the customer's needs.\nAsk only ONE question at a time.\n\nIf the customer wants to check out, hand off to the Checkout Agent.\nIf the customer wants to start over, hand off to the Welcome Agent.",
            "handoff_description": "When product information is needed or items need to be added to cart",
            "handoffs": ["welcome_agent", "checkout_agent"],
            "tools": ["search_products", "add_to_cart", "get_product_details"],
            "context": "ShoppingContext"
          },
          "checkout_agent": {
            "name": "checkout_agent",
            "instructions": "You are the Checkout Agent for an e-commerce platform.\nIMPORTANT: Keep all responses SHORT, CRISP and CONVERSATIONAL - suitable for a voice interface.\nLimit responses to 1-2 short sentences whenever possible.\n\nYour responsibilities:\n- Guide customers through the checkout process\n- Handle payment method selection\n- Process shipping information\n- Confirm orders and provide order summaries\n\nBe efficient and reassuring. Make the checkout process as smooth as possible.\nAsk only ONE question at a time.\n\nIf the customer wants to continue shopping, hand off to the Product Agent.\nIf the customer wants to start over, hand off to the Welcome Agent.",
            "handoff_description": "When the customer is ready to checkout",
            "handoffs": ["welcome_agent", "product_agent"],
            "tools": ["process_payment", "update_shipping", "complete_order"],
            "context": "ShoppingContext"
          }
        }
      }
    },
    "tts": {
      "provider": "openai",
      "voice": "shimmer"
    },
    "mcp": { 
      "type": "llm_orchestrator",
      "config": {
        "max_turns": 5,
        "response_timeout": 10,
        "history_length": 5,
        "enable_tool_selection": true,
        "tool_selection_strategy": "highest_confidence"
      }
    }
  },
  "pipeline": {
    "name": "ecommerce_pipeline",
    "stages": [
      { "type": "input", "config": {} },
      { "type": "vad", "config": {} },
      { "type": "stt", "config": {} },
      { "type": "llm", "config": { "use_tools": true } },
      { "type": "tts", "config": {} },
      { "type": "output", "config": {} }
    ]
  }
}
```

**Explanation:**

1. **Multi-Agent Architecture**:
   - This configuration uses the `openai_agents` provider to create a system with three specialized agents
   - Each agent has a specific role in the customer journey
   - The system maintains a shared context (`ShoppingContext`) across all agents

2. **Agent Configuration**:
   - `start_agent`: Specifies that conversations begin with the welcome_agent
   - Each agent has:
     - **Instructions**: Detailed prompts that define behavior and responsibilities
     - **Handoffs**: List of other agents this agent can transfer control to
     - **Tools**: Specific functions this agent can access
     - **Context**: Shared data structure for maintaining state

3. **Agent Specialization**:
   - **welcome_agent**: Handles initial greetings and collects basic preferences
   - **product_agent**: Manages product recommendations and cart operations
   - **checkout_agent**: Processes payments and finalizes orders

4. **Transport and Voice Processing**:
   - Uses Daily's WebRTC implementation for high-quality audio
   - Silero for VAD and Deepgram for STT (without specifying model, will use default)
   - OpenAI's shimmer voice for TTS

5. **MCP (Model Context Protocol) Configuration**:
   - Type: `llm_orchestrator` manages the flow between agents
   - Settings control conversation flow:
     - `max_turns`: Limits conversation length
     - `response_timeout`: Sets maximum wait time for responses
     - `history_length`: Controls how much conversation history is maintained
     - `tool_selection`: Enables and configures how tools are selected

6. **Pipeline**:
   - Similar to the basic example but optimized for the multi-agent workflow

**Note:** After creating the `agent_config.json` file, set its path in your `.env` file:
```
AGENT_CONFIG_PATH="/path/to/your/agent_config.json"
```

## 6. Using Custom Tools

Tools extend your agent's capabilities by allowing it to perform actions beyond conversation. Here's how to create and register custom tools:

### 6.1 Basic Tool Definition

Tools are regular Python functions with type hints and docstrings:

```python
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    # Implementation here - could call a weather API
    return f"The weather in {location} is sunny."
```

### 6.2 Tool Registration

Register your tools by adding them to the `tool_config` dictionary:

```python
from foundational_ai_server.agent_configure.utils.tool import tool_config

# Register your tools
tool_config["get_weather"] = get_weather
tool_config["search_database"] = search_database
```

### 6.3 Using Context in Tools

For more advanced tools that need to access or modify the conversation context:
```python
# main.py
import uvicorn
from fastapi import FastAPI, BackgroundTasks, Request
from typing import Dict, Any, Optional

from foundational_ai_server.lib import CaiSDK
from foundational_ai_server.agent_configure.utils.tool import tool_config


#Define your tool functions
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    # Replace with actual weather API call
    return f"The weather in {location} is sunny."


#Initialize FastAPI and SDK
app = FastAPI()
cai_sdk = CaiSDK()

# 5. Create /connect endpoint
@app.post("/connect")
async def connect_endpoint(
    request_data: dict, 
    background_tasks: BackgroundTasks
):
    # Initialize callbacks and tools
    callbacks = MyCallbacks()
    tool_config["get_weather"] = get_weather
    context = MyContext()

    # Handle the connection
    return await cai_sdk.connect_handler(
        background_tasks=background_tasks,
        request_data=request_data,
        tool_config=tool_config,
        app_callbacks=callbacks,
        context=context  # Pass your custom context
    )

# 6. Run the application
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

## 7. Transport and Callbacks Guide

The SDK supports multiple transport methods for communication between clients and your agent. Each transport type supports specific callbacks.

### 7.1 Available Callbacks and Their Parameters

All callbacks are asynchronous and should be defined with `async def`. The following callbacks are available in the `AgentCallbacks` class:

1. **on_client_connected(client: Dict[str, Any]) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when a client connects to the agent
   - `client`: Dictionary containing client connection details (format varies by transport)
   - Default implementation: No-op

2. **on_client_disconnected(data: Dict[str, Any]) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when a client disconnects
   - `data`: Dictionary containing:
     - `transcript`: List[Dict] - Complete conversation transcript
     - `metrics`: Dict - Call metrics and statistics including duration, latency, etc.
   - Default implementation: Logs transcript and metrics to console

3. **on_first_participant_joined(participant: Dict[str, Any]) -> None**
   - **Supported Transport**: Daily.co only
   - Triggered when the first participant joins a Daily.co room
   - `participant`: Dictionary containing participant details (Daily.co participant object)
   - Default implementation: Logs participant info to console

4. **on_participant_left(participant: Dict[str, Any], reason: str) -> None**
   - **Supported Transport**: Daily.co only
   - Triggered when a participant leaves a Daily.co room
   - `participant`: Dictionary containing participant details
   - `reason`: String describing why the participant left
   - Default implementation: Logs participant and reason to console

5. **on_transcript_update(frame: Any) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when there's an update to the conversation transcript
   - `frame`: Object containing:
     - `messages`: List[Dict] - Message objects with:
       - `role`: str - 'user' or 'assistant'
       - `content`: str - Message content
       - `timestamp`: str - ISO 8601 timestamp
   - Default implementation: Logs transcript updates to console

6. **on_session_timeout() -> None**
   - **Status**: Defined but not implemented
   - Note: This event is defined in the `AgentEvent` enum but is not currently used in the agent implementation

### 7.2 Notes

- All callbacks are optional. If not implemented, default no-op implementations will be used.
- Callbacks are called asynchronously, so they should be defined with `async def`.
- The `data` parameter in `on_client_disconnected` contains both the transcript and call metrics.
- For Daily.co transport, `on_first_participant_joined` is called only for the first participant.
- The `on_participant_left` callback is only available for Daily.co transport.


### 7.3 Implementing Custom Callbacks

Create a custom callbacks class by extending `AgentCallbacks`:

```python
from foundational_ai_server.agent_configure.utils.callbacks import AgentCallbacks

class MyCallbacks(AgentCallbacks):
    async def on_client_connected(self, client):
        print(f"Client connected: {client}")
    
    async def on_transcript_update(self, frame):
        # Process new transcript data
        for message in frame.messages:
            print(f"Transcript: {message.role}: {message.content}")
            
    async def on_client_disconnected(self, data):
        transcript = data.get("transcript", [])
        metrics = data.get("metrics", {})
        print(f"Client disconnected. Transcript length: {len(transcript)}")
        
    async def on_first_participant_joined(self, participant):
        print(f"First participant joined: {participant}")
        
    async def on_participant_left(self, participant, reason):
        print(f"Participant left: {participant}, reason: {reason}")
        print(f"Participant left: {participant}, reason: {reason}")
```


## 8. Advanced Topics

### 8.1 Custom Contexts

To manage state or share data across agent interactions, define custom context classes inheriting from Pydantic's `BaseModel`:

```python
from pydantic import BaseModel
from typing import Optional, Dict, List

class MyCustomContext(BaseModel):
    user_id: Optional[str] = None
    session_data: Dict[str, any] = {}
    conversation_history: List[Dict] = []
    
    def add_to_history(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
```

Pass an instance to the SDK handler:

```python
context = MyCustomContext(user_id="user123")
return await cai_sdk.connect_handler(
    # ... other parameters
    context=context
)
```

### 8.2 Advanced Tool Definitions

Tools can perform complex operations and integrate with external systems:

```python
from foundational_ai_server.agent_configure.utils.tool import function_tool
import requests

@function_tool
def search_knowledge_base(query: str, max_results: int = 5) -> Dict[str, any]:
    """Search the knowledge base for information related to the query."""
    # Call an external API
    response = requests.get(
        "https://your-api.example.com/search",
        params={"q": query, "limit": max_results}
    )
    
    # Process and return the results
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Search failed with status {response.status_code}"}
```

### 8.3 Creating Server Endpoints

Integrate `CaiSDK` into your FastAPI application with custom endpoints:

```python
from fastapi import FastAPI, WebSocket, BackgroundTasks
from foundational_ai_server.lib import CaiSDK, TransportType

app = FastAPI()
cai_sdk = CaiSDK()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await cai_sdk.websocket_endpoint(websocket)

# WebRTC endpoint
@app.post("/webrtc")
async def webrtc_endpoint(request_data: dict, background_tasks: BackgroundTasks):
    return await cai_sdk.webrtc_endpoint(
        background_tasks=background_tasks,
        request_data=request_data
    )

# Custom connect endpoint with additional logic
@app.post("/connect")
async def connect_endpoint(request_data: dict, background_tasks: BackgroundTasks):
    # Add custom pre-processing here
    user_id = request_data.get("user_id")
    
    # Initialize context with user data
    context = MyCustomContext(user_id=user_id)
    
    # Set up custom callbacks
    callbacks = MyCallbacks()
    
    # Register tools specific to this user
    tool_config["get_user_data"] = lambda: get_user_data(user_id)
    
    return await cai_sdk.connect_handler(
        background_tasks=background_tasks,
        request_data=request_data,
        tool_config=tool_config,
        app_callbacks=callbacks,
        context=context
    )
```

## 9. Project Structure

A typical project using the Foundational AI Server SDK might have the following structure:

```
my-app/
├── main.py                # Your FastAPI app with endpoints
├── tools/
│   ├── __init__.py
│   ├── weather.py         # Weather-related tools
│   └── database.py        # Database query tools
├── callbacks/
│   ├── __init__.py
│   └── handlers.py        # Custom callback implementations
├── context/
│   ├── __init__.py
│   └── models.py          # Custom context models
├── config/
│   └── agent_config.json  # Agent configuration
├── .env                   # Environment variables
└── requirements.txt       # Dependencies
```

This structure keeps your code organized and modular, making it easier to maintain and extend.

## 10. Running the Example

To run the basic example from Section 3:

1. Create a virtual environment and install the SDK:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install "git+ssh://git@github.com/think41/foundational-ai-server.git#egg=foundational_ai_server"
   ```

2. Create a `.env` file with your API keys (see Section 2.1).

3. Create an `agent_config.json` file (see Section 5) and set its path in `.env`.

4. Create a `main.py` file with the example code from Section 3.

5. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

6. Your server will be available at `http://localhost:8000`.


---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---


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



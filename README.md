# Foundation Voice SDK

## 1. Introduction

Welcome to the Foundation Voice SDK! This SDK provides the core functionalities for building voice-based conversational AI applications using the Pipecat framework. It allows you to configure and run sophisticated AI agents capable of:

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
pip install "git+ssh://git@github.com/think41/foundation-voice.git#egg=foundation_voice"
```

This command will install the `foundation_voice` package and all its dependencies as listed in `pyproject.toml`.

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

#config path
CONFIG_PATH="path_to_your_config_file"
```

Refer to the specific provider's documentation for how to obtain API keys.

## 3. Basic Implementation Example

Here's a minimal example of implementing agent callbacks and tool configuration with a `/connect` endpoint in `main.py`:

```python
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from foundation_voice.utils.transport.connection_manager import WebRTCOffer
from foundation_voice.lib import CaiSDK
from agent_configure.utils.context import contexts
from agent_configure.utils.tool import tool_config
from agent_configure.utils.callbacks import custom_callbacks
from foundation_voice.utils.config_loader import ConfigLoader
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize the CAI SDK
cai_sdk = CaiSDK()

config_path = os.getenv("CONFIG_PATH")
agent_config = ConfigLoader.load_config(config_path)

defined_agent = {
    "agent": {
        "config": agent_config, 
        "contexts": contexts,
        "tool_dict": tool_config,
        "callbacks": custom_callbacks,
    },
}

# Create FastAPI app
app = FastAPI(
    title="WebRTC Endpoint",
    description="Basic WebRTC endpoint implementation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/connect") # rename this with your actual endpoint name
async def webrtc_endpoint(offer: WebRTCOffer, background_tasks: BackgroundTasks):
    """
    Handle WebRTC offer and return answer
    """
    agent = defined_agent.get("agent")
    # Process the WebRTC offer and get response
    response = await cai_sdk.webrtc_endpoint(offer, agent)
    
    # Handle background tasks if any
    if "background_task_args" in response:
        task_args = response.pop("background_task_args")
        func = task_args.pop("func")
        background_tasks.add_task(func, **task_args)

    return response["answer"]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

### 3.1 Example Explanation


1. You can use the cai sdk which is a class which provides multiple methods to run the agent with the choice of transport.

2. Before running the agent, we need to create a json file with all the configartaions for the agent, then either put the path manual or load it from the environment variable.

3. The ConfigLoader class is a utility class that loads the agent configuration from a JSON file. It can be used to load the configuration from a file.

4. to use an agent we need to define it as a dictionary that contains the [agent configuration](#4-creating-a-configuration-file), [contexts](#3-context), [tools](#2-tool-configuration), and [callbacks](#3-callbacks), below you will find examples and explanation of each.

5. create the FastAPI app:- the FastAPI app is a web server that handles the HTTP requests.

6. create a endpoint:- for connecting to the agent, the example shows the webrtc endpoint, you can choose your any transport of your choice.

> Note: we currently support webrtc, websocket and daily transports, make sure your client is configured to use the same transport, as the client is responsible for handling the connection.


### 3.2 Core Concepts

The Foundation Voice SDK is built around several key concepts that work together to create a flexible and powerful conversational AI system:

#### 1. Agent Configuration

Agent configuration defines the behavior, capabilities, and components of your AI agent. This includes:

- **Voice Processing**: VAD, STT, and TTS settings
- **Language Model**: Which LLM to use and how to configure it
- **Prompts**: Instructions that guide the agent's behavior

You can configure these through a JSON file. [Jump to Configuration File](#4-creating-a-configuration-file)

> Note: agent configuration is optional and can be defined in the agent you define in your main application.

#### 2. Tool Configuration

Tools are functions that extend your LLM capabilities, allowing it to perform actions beyond conversation. Tools can:

- Access external APIs or databases
- Modify application state
- Perform calculations or data processing
- Interact with other systems

Tools are registered in the `tool_config` [Jump to Custom Tools](#4-using-custom-tools-with-openai-agents)

> Note: tools are optional and can be defined in the agent you define in your main application.

#### 3. Callbacks

Callbacks provide hooks into the agent's lifecycle, allowing your application to respond to events such as:

- Agent starting/ending
- Tool calls
- Transcript updates
- Client connections/disconnections

Callbacks enable integration with your application logic [Jump to Callbacks](#3-callbacks)

> Note: callbacks are optional and can be defined in the agent you define in your main application. See [Callbacks Guide](#6callbacks-guide) for more details.

#### 4. Context

Context is the mechanism that allows your LLM to maintain state, remember information across conversational turns, and personalize interactions. It's key for building more sophisticated and stateful conversational experiences. Context is typically defined as a data structure (often a Pydantic model) and configured in your agent's JSON settings. This allows the LLM to store and retrieve relevant information throughout a session.

For a detailed guide on how context is configured, defined in Python, and utilized during agent operations, see [Context In-Depth](#7-context-in-depth) section below.

> Note: context is optional and can be defined in the agent you define in your main application.

## 4. Creating a Configuration File

The SDK uses a JSON file to configure the agent and the processing pipeline. You can create your own configuration file (e.g., `my_agent_config.json`).

Here's a breakdown of the main sections and options:

```json
{
  "agent": {
    "title": "My Custom Bot",
    "initial_greeting": "Hello! How can I help you today?",
    "prompt": "You are a helpful assistant.",
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
      "tools": ['get_current_weather'],
    },
    "tts": {
      "provider": "openai", // Supported: "openai", "deepgram", "cartesia"
      "voice": "alloy" // For "openai" provider
    }
  }
}
```

### 4.1 Configuration Options Explained

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

### 4.2 Supported Configurations

#### Agent Settings
- `title`: String (any text)
- `initial_greeting`: String (any text)
- `prompt`: String (system prompt text)

#### Transport Configuration
- `agent.transport.type`:
  - `webrtc`: For WebRTC connections
  - `websocket`: For WebSocket connections
  - `daily`: For Daily.co integration

#### Voice Activity Detection (VAD)
- `agent.vad.provider`:
  - `silero`: Recommended VAD provider
  - `none`: Disable VAD

#### Speech-to-Text (STT)
- `agent.stt.provider`:
  - `deepgram`: Deepgram speech recognition
  - (Additional providers as supported)
- `agent.stt.model`: Provider-specific model name (e.g., `nova-2` for Deepgram)

#### Language Model (LLM)
- `agent.llm.provider`:
  - `openai`: Standard OpenAI models
  - `openai_agents`: For multi-agent setups
- `agent.llm.model`: Model name (e.g., `gpt-4o-mini` for OpenAI)
- `agent.llm.temperature`: Float (0.0 to 2.0)
- `agent.llm.max_tokens`: Integer

#### Text-to-Speech (TTS)
- `agent.tts.provider`:
  - `openai`: OpenAI's text-to-speech
  - `deepgram`: Deepgram's text-to-speech
  - `cartesia`: Cartesia's text-to-speech
- `agent.tts.voice`: Provider-specific voice ID (e.g., `alloy`, `nova` for OpenAI)


### 4.3 Example Configurations:-

#### 1. Basic Example with OpenAI

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

#### 2. Complex Example with OpenAI Agents

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
     - **name**: The unique identifier for the agent
     - **Instructions**: Detailed prompts that define behavior and responsibilities
     - **Handoffs**: List of other agents this agent can transfer control to
     - **handoff_description**: Description of when the handoff should occur
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

> **Note:** After creating the `agent_config.json` file, make sure to load it in your app by setting the `AGENT_CONFIG_PATH` environment variable or by loading it manually.

## 5. Using Custom Tools With Openai Agents

Custom tools allow your OpenAI agent to perform specific actions and maintain state during conversations. Here's how to define and use custom tools with OpenAI agents in your application:

### Creating Custom Tools

To create a new tool, use the `@function_tool` decorator:

```python
from agents import function_tool, RunContextWrapper

@function_tool(
    description_override='Your tool description here.'
)
def your_tool_name(ctx: RunContextWrapper, param1: type = None, param2: type = None):
    # Your tool logic here
    return "Result message"

# Don't forget to add it to tool_config
tool_config["your_tool_name"] = your_tool_name
```

### Example Usage in Agent Configuration

In your `agent_config.json`, you can reference these tools in the tools section:

```json
{
  "agent": {
    "tools": [
      "update_basic_info",
      "update_room_data",
      "update_products",
      "search_tool"
    ]
  }
}
```
> Note: Ensure you import your defined tool in the main.py file and pass it to your agent definition like shown in the example [here](#4-basic-implementation-example)


## 6.Callbacks Guide

The SDK supports multiple transport methods for communication between clients and your agent. Each transport type supports specific callbacks.

### 6.1 Available Callbacks and Their Parameters

All callbacks are asynchronous and should be defined with `async def`. The following callbacks are available in the `AgentCallbacks` class:

1. **on_client_connected(client: Dict[str, Any]) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when a client connects to the agent
   - `client`: Dictionary containing client connection details (format varies by transport)

2. **on_client_disconnected(data: Dict[str, Any]) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when a client disconnects
   - `data`: Dictionary containing:
     - `transcript`: List[Dict] - Complete conversation transcript
     - `metrics`: Dict - Call metrics and statistics including duration, latency, etc.

3. **on_first_participant_joined(participant: Dict[str, Any]) -> None**
   - **Supported Transport**: Daily.co only
   - Triggered when the first participant joins a Daily.co room
   - `participant`: Dictionary containing participant details (Daily.co participant object)

4. **on_participant_left(participant: Dict[str, Any], reason: str) -> None**
   - **Supported Transport**: Daily.co only
   - Triggered when a participant leaves a Daily.co room
   - `participant`: Dictionary containing participant details
   - `reason`: String describing why the participant left

5. **on_transcript_update(frame: Any) -> None**
   - **Supported Transports**: WebSocket, WebRTC, Daily.co
   - Triggered when there's an update to the conversation transcript
   - `frame`: Object containing:
     - `messages`: List[Dict] - Message objects with:
       - `role`: str - 'user' or 'assistant'
       - `content`: str - Message content
       - `timestamp`: str - ISO 8601 timestamp

6. **on_session_timeout() -> None**
   - **Status**: Defined but not implemented
   - Note: This event is defined in the `AgentEvent` enum but is not currently used in the agent implementation

### 6.2 Notes

- All callbacks are optional.
- Callbacks are called asynchronously, so they should be defined with `async def`.
- The `data` parameter in `on_client_disconnected` contains both the transcript and call metrics.
- For Daily.co transport, `on_first_participant_joined` is called only for the first participant.
- The `on_participant_left` callback is only available for Daily.co transport.


### 6.3 Implementing Custom Callbacks

Create a custom callbacks class by extending `AgentCallbacks`:

```python
from foundation_voice.agent_configure.utils.callbacks import AgentCallbacks

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


## 7. Context In-Depth

Context allows your agent to maintain state, remember information across conversational turns, and tailor its responses. It's a crucial component for building more sophisticated and personalized interactions. This section provides a detailed look into how context is managed within the Foundation Voice SDK.

**7.1. Configuration (in JSON files like `agent_config.json`):**

*   Context is typically specified within your agent's configuration file (e.g., `my_agent_config.json` or the default `agent_config.json`).
*   It's defined using a string name that refers to a predefined context structure. For example:
    ```json
    // In your agent_config.json
    "agent_config": {
      "start_agent": "your_start_agent_name",
      "context": "MyCustomContextName", // Global context for the agent setup
      // ... other agent_config settings
    }
    ```
*   If you're using a multi-agent setup, context can also be specified for individual sub-agents.

**7.2. Explanation :**

*   The string names used in the JSON configuration (e.g., `"MyCustomContextName"`) should be mapped to a Python class that define the actual structure of the context.
*   These classes are usually Pydantic `BaseModel`s. You can define your own custom context structures by creating new classes and importing it in your server endpoint 
    ```python
    # Example in foundation-voice/agent_configure/utils/context.py
    from pydantic import BaseModel
    from typing import Optional, List, Dict, Any # Ensure necessary imports

    class MyCustomContextName(BaseModel):
        user_id: Optional[str] = None
        session_data: Dict[str, Any] = {}
        conversation_history: List[Dict] = []
        # ... other fields relevant to your application
    
    # ... ensure it's added to the 'contexts' dictionary
    # This dictionary is typically located in the same file (context.py)
    contexts = {
        "MyCustomContextName": MyCustomContextName,
        # ... other predefined contexts like MagicalNestContext
    }
    ```
> Note ensure you import your defined context in the main.py file and pass it to your agent definition like shown in the example [here](#3-basic-implementation-example)


## 8. SIP Integration (via Webhook)

This SDK supports SIP integration through a webhook-based model, similar to how services like Twilio work. Instead of handling the SIP protocol directly, the application exposes endpoints that a SIP provider can call. The provider manages the SIP trunk and bridges the call to a WebSocket stream that the agent connects to.

This approach is robust, scalable, and avoids the complexity of a native SIP implementation.

### 8.1 Configuration for SIP

To enable SIP integration (using Twilio as the provider in this example), add the following to your `.env` file:

```env
# Twilio credentials for SIP integration
TWILIO_ACCOUNT_SID="your_twilio_account_sid"
TWILIO_AUTH_TOKEN="your_twilio_auth_token"
TWILIO_PHONE_NUMBER="your_twilio_phone_number"
```

You will also need a publicly accessible URL for your running application (e.g., using a service like `ngrok`).

### 8.2 Handling Inbound Calls

1.  **Configure Your SIP Provider:** In your Twilio phone number's configuration, set the "A CALL COMES IN" webhook to point to your server's `/api/sip` endpoint (e.g., `https://your-public-url.com/api/sip`).
2.  **How It Works:** When a call comes in, Twilio sends a POST request to `/api/sip`. The application responds with TwiML (Twilio Markup Language) that instructs Twilio to open a WebSocket connection to the `/ws` endpoint of your agent. The agent then communicates over this stream.

### 8.3 Initiating Outbound Calls

You can trigger an outbound call by sending a POST request to the `/api/sip/create-call` endpoint.

**Example using cURL:**

```bash
curl -X POST "http://localhost:8000/api/sip/create-call?to_number=+1234567890"
```

-   `to_number`: The E.164 formatted phone number to call.
-   You can also optionally provide `from_number` and `agent_name` as query parameters. If `from_number` is not provided, it will use the `TWILIO_PHONE_NUMBER` from your `.env` file.


## 9. Advanced Topics

### 9.1 Advanced Tool Definitions

Tools can perform complex operations and integrate with external systems:

```python
from foundation_voice.agent_configure.utils.tool import function_tool
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

### 9.2 Creating Server Endpoints

Integrate `CaiSDK` into your FastAPI application with custom endpoints:

```python
from fastapi import FastAPI, WebSocket, BackgroundTasks
from foundation_voice.lib import CaiSDK, TransportType

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

## 10. Project Structure

A typical project using the Foundation Voice SDK follows this structure, as shown in the examples directory:

```
my-app/
├── main.py                    # Main FastAPI application with WebSocket and HTTP endpoints
├── main.py                    # Your application's entry point
├── agent_config.json          # Example agent configuration for your app
├── app_callbacks.py           # Your application's custom callbacks
├── app_context.py             # Your application's custom context definitions
├── app_tools.py               # Your application's custom tools
├── .env                       # Environment variables
└── requirements.txt           # Python dependencies (will include foundation_voice)
```

This structure provides a clean separation of concerns, making it easy to maintain and extend your AI agent implementation. The configuration files allow for different agent behaviors, and the utils directory contains reusable components for callbacks, context management, and tools.

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
* Automated releases with semantic-release.

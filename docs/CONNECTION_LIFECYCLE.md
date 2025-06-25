# Voice Connection Architecture and Lifecycle

This document provides a comprehensive guide to the connection handling in `foundation-voice`, covering both WebSocket and SIP (Session Initiation Protocol) communications, including detailed explanations of inbound/outbound call flows and a complete reference of all related components.

## Table of Contents

1. [Core Architecture](#core-architecture)
2. [Connection Lifecycle](#connection-lifecycle)
   - [WebSocket Connections](#websocket-connections)
   - [SIP Connections](#sip-connections)
3. [Inbound Call Flow](#inbound-call-flow)
4. [Outbound Call Flow](#outbound-call-flow)
5. [Component Reference](#component-reference)
6. [Configuration Reference](#configuration-reference)

## Core Architecture

The system is built around a flexible transport layer that can handle multiple communication protocols through a unified interface. The core components are:

### 1. Transport Layer (`foundation_voice/utils/transport/`)
- **`transport.py`**: Contains the `TransportFactory` and `TransportType` enum
- **`sip_detection.py`**: Handles SIP connection detection and handshaking
- **`connection_manager.py`**: Manages active WebRTC connections
- **`session_manager.py`**: Tracks active sessions

### 2. Core SDK (`foundation_voice/lib.py`)
- `CaiSDK` class: Main entry point for all voice interactions
- Handles connection routing and transport initialization

### 3. Agent System
- Processes audio streams and generates responses
- Works with any configured transport

## Connection Lifecycle

### WebSocket Connections

1. **Connection Initiation**
   - Client connects to `/ws` endpoint
   - Can include `?transport_type=websocket` (optional)

2. **Transport Detection**
   - `CaiSDK._auto_detect_transport()` identifies connection type
   - Falls back to WebSocket if no other type is detected

3. **Transport Initialization**
   - `TransportFactory` creates `FastAPIWebsocketTransport`
   - Configures with `ProtobufFrameSerializer`
   - Sets up audio processing pipeline

4. **Session Management**
   - New session created with unique ID
   - Session tracked in `session_manager`

5. **Data Flow**
   - Binary audio frames exchanged over WebSocket
   - Agent processes audio and generates responses

6. **Termination**
   - Client disconnection
   - Session timeout (default: 3 minutes)
   - Cleanup of resources

### SIP Connections

SIP connections are more complex due to the intermediary (Twilio) and the SIP protocol requirements.

#### Inbound Call Flow

1. **Call Initiation**
   ```plaintext
   [Caller] --> [Twilio SIP Trunk] --> [Your Server /ws]
   ```

2. **Connection Detection**
   - WebSocket connection established by Twilio
   - No query parameters (unlike browser clients)
   - `SIPDetector.detect_sip_connection()` identifies as potential SIP

3. **SIP Handshake**
   - `SIPDetector.handle_sip_handshake()` executed
   - Waits for Twilio's handshake sequence:
     1. `{"event": "connected"}`
     2. `{"event": "start", "start": {"streamSid": "...", "callSid": "..."}}`
   - Extracts `streamSid` and `callSid`

4. **Transport Initialization**
   - `TransportFactory` creates `FastAPIWebsocketTransport`
   - Configures with `TwilioFrameSerializer`
   - Sets up Twilio-specific audio processing

5. **Call Handling**
   - Audio stream processed by agent
   - DTMF and call control events handled
   - Real-time transcription available

6. **Call Termination**
   - Caller hangs up
   - Twilio sends `stop` event
   - WebSocket connection closed
   - Resources cleaned up

#### Outbound Call Flow

1. **Call Initiation**
   ```python
   from twilio.rest import Client
   
   client = Client(account_sid, auth_token)
   call = client.calls.create(
       twiml=f'<Response><Connect><Stream url="wss://your-server/ws"/></Connect></Response>',
       to='+1234567890',
       from_='+1987654321'
   )
   ```

2. **Connection Handling**
   - Same as inbound flow from step 2 onward
   - Twilio initiates WebSocket connection to your endpoint

3. **Call Control**
   - Use Twilio's REST API for advanced control:
     - Transfer calls
     - Play messages
     - Record calls
     - Gather DTMF input

## Component Reference

### `CaiSDK` (lib.py)

Main class handling all voice interactions.

#### Key Methods:

1. **`websocket_endpoint_with_agent(websocket, agent, **kwargs)`**
   - Entry point for all WebSocket connections
   - Handles both browser and SIP connections
   - Parameters:
     - `websocket`: FastAPI WebSocket connection
     - `agent`: Configuration for the voice agent
     - `**kwargs`: Additional parameters passed to agent

2. **`_auto_detect_transport(websocket)`**
   - Determines connection type
   - Returns tuple of (TransportType, params)
   - Handles SIP detection fallback

3. **`_ensure_metadata_and_session_id(kwargs)`**
   - Ensures required metadata is present
   - Generates session ID if not provided

### `TransportFactory` (transport.py)

Creates and configures transport instances.

#### Key Methods:

1. **`create_transport(transport_type, connection, **kwargs)`**
   - Factory method for transport instances
   - Handles all transport types (WebSocket, SIP, Daily, WebRTC)
   - Configures appropriate serializers and parameters

### `SIPDetector` (sip_detection.py)

Handles SIP connection detection and handshaking.

#### Key Methods:

1. **`detect_sip_connection(client_ip, headers, query_params)`**
   - Determines if connection is likely SIP
   - Checks for Twilio-specific patterns
   - Returns boolean

2. **`handle_sip_handshake(websocket)`**
   - Performs Twilio SIP handshake
   - Returns SIP parameters (streamSid, callSid) or None
   - Handles timeouts and errors

### `TwilioFrameSerializer` (via pipecat)

Serializes/deserializes Twilio's media stream format.

#### Key Features:
- Handles mulaw audio encoding
- Processes Twilio control messages
- Manages call state

## Configuration Reference

### Environment Variables

```bash
# Required for SIP
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token

# Optional
VAD_ENABLED=true  # Voice Activity Detection
VAD_THRESHOLD=0.5  # Sensitivity (0.0 to 1.0)
```

### Agent Configuration

```python
agent_config = {
    "config": {
        "model": "gpt-4",
        "temperature": 0.7,
    },
    "callbacks": [
        # Custom callbacks
    ],
    "tool_dict": {
        # Custom tools
    }
}
```

## Troubleshooting

### Common Issues

1. **SIP Handshake Failing**
   - Verify Twilio credentials
   - Check WebSocket URL in TwiML
   - Inspect WebSocket messages for errors

2. **Audio Quality Issues**
   - Check network latency
   - Verify codec settings
   - Adjust VAD threshold if needed

3. **Connection Drops**
   - Check timeouts
   - Verify WebSocket ping/pong
   - Monitor server resources

## Best Practices

1. **Error Handling**
   - Implement proper error handling
   - Log all connection events
   - Monitor call quality metrics

2. **Security**
   - Validate all WebSocket messages
   - Use WSS (secure WebSocket)
   - Implement rate limiting

3. **Performance**
   - Optimize audio processing
   - Use connection pooling
   - Monitor resource usage

from typing import Dict, Any

class AgentTemplates:
    """Templates for different agent configurations"""
    
    @staticmethod
    def get_single_agent_template() -> Dict[str, Any]:
        return {
            "agent": {
                "title": "",
                "initial_greeting": "",
                "prompt": "",
                "transport": {
                    "type": "small-webrtc"
                },
                "vad": {
                    "provider": "silero"
                },
                "stt": {
                    "provider": "deepgram",
                    "model": "nova-2"
                },
                "llm": {
                    "provider": "cerebras",
                    "model": "llama-3.3-70b",
                    "tools": []
                },
                "tts": {
                    "provider": "smallestai",
                    "voice_id": "ananya",
                    "speed": 1.5
                }
            },
            "pipeline": {
                "enable_tracing": False
            }
        }
    
    @staticmethod
    def get_multi_agent_template() -> Dict[str, Any]:
        return {
            "agent": {
                "title": "",
                "initial_greeting": "",
                "prompt": "",
                "transport": {
                    "type": "sip"
                },
                "vad": {
                    "provider": "silerio"
                },
                "stt": {
                    "provider": "deepgram",
                    "audio_passthrough": True
                },
                "llm": {
                    "provider": "openai_agents",
                    "logfire_trace": False,
                    "triage": False,
                    "agent_config": {
                        "start_agent": "",
                        "logfire_trace": True,
                        "triage": True,
                        "context": "",
                        "agents": {},
                        "guardrails": {}
                    }
                },
                "tts": {
                    "provider": "smallestai",
                    "voice_id": "ananya",
                    "speed": 1.5
                },
                "mcp": {
                    "type": "llm_orchestrator",
                    "config": {
                        "max_turns": 15,
                        "response_timeout": 20,
                        "history_length": 10,
                        "enable_tool_selection": True,
                        "tool_selection_strategy": "highest_confidence",
                        "context_management": ""
                    }
                }
            },
            "pipeline": {
                "name": "llm_agent_pipeline",
                "sample_rate_in": 8000,
                "sample_rate_out": 8000,
                "stages": [
                    {"type": "input", "config": {}},
                    {"type": "vad", "config": {"min_silence_duration": 0.8, "speech_detection_sensitivity": 0.7}},
                    {"type": "stt", "config": {"language": "en", "model": "nova-2"}},
                    {"type": "llm", "config": {"use_tools": True, "context_window": 4000, "temperature": 0.7}},
                    {"type": "tts", "config": {"sample_rate": 8000, "voice_settings": {"speed": 1.1, "pitch": 0.9}}},
                    {"type": "output", "config": {}}
                ]
            }
        }
    
    @staticmethod
    def get_python_file_template() -> str:
        return '''import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp
from loguru import logger
from foundation_voice.custom_plugins.agent_callbacks import AgentCallbacks, AgentEvent
from pydantic import BaseModel, Field

{tools_section}

tool_config = {{
{tool_config_section}
}}

{callbacks_section}

# Create a custom AgentCallbacks instance
custom_callbacks = AgentCallbacks()

# Override default callbacks with our custom implementations
custom_callbacks.register_callback(
    AgentEvent.CLIENT_CONNECTED,
    on_client_connected_callback
)

custom_callbacks.register_callback(
    AgentEvent.FIRST_PARTICIPANT_JOINED,
    on_first_participant_joined_callback
)

custom_callbacks.register_callback(
    AgentEvent.PARTICIPANT_LEFT,
    on_participant_left_callback
)

custom_callbacks.register_callback(
    AgentEvent.TRANSCRIPT_UPDATE,
    on_transcript_update_callback
) 

custom_callbacks.register_callback(
    AgentEvent.CLIENT_DISCONNECTED,
    on_participant_left_callback
) 

{context_section}

{contexts_dict}
'''
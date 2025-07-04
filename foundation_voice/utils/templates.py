from typing import Any, Dict, List


class AgentTemplates:
    """Templates for different agent configurations"""

    @staticmethod
    def get_single_agent_template() -> Dict[str, Any]:
        return {
            "agent": {
                "title": "",
                "initial_greeting": "",
                "prompt": "",
                "transport": {"type": "daily"},
                "vad": {"provider": "silero"},
                "stt": {"provider": "deepgram", "model": "nova-2"},
                "llm": {
                    "provider": "cerebras",
                    "model": "llama-3.3-70b",
                    "tools": [],
                    "guardrails": [],
                },
                "tts": {"provider": "smallestai", "voice_id": "emily", "speed": "1.0"},
            },
            "pipeline": {
                "enable_tracing": True,
                "sample_rate_in": 8000,
                "sample_rate_out": 8000,
            },
        }

    @staticmethod
    def get_multi_agent_template() -> Dict[str, Any]:
        return {
            "agent": {
                "title": "",
                "initial_greeting": "",
                "prompt": "",
                "transport": {"type": "daily"},
                "vad": {"provider": "silero"},
                "stt": {"provider": "deepgram", "audio_passthrough": True},
                "llm": {
                    "provider": "openai_agents",
                    "logfire_trace": False,
                    "triage": False,
                    "agent_config": {
                        "start_agent": "",
                        "logfire_trace": True,
                        "triage": True,
                        "context": "",
                        "agents": {
                            # This will be populated by the LLM
                        },
                        "guardrails": {
                            # This will be populated by the LLM
                        },
                    },
                },
                "tts": {"provider": "smallestai", "voice_id": "emily", "speed": "1.0"},
                "mcp": {
                    "type": "llm_orchestrator",
                    "config": {
                        "max_turns": 15,
                        "response_timeout": 20,
                        "history_length": 10,
                        "enable_tool_selection": True,
                        "tool_selection_strategy": "highest_confidence",
                        "context_management": "",
                    },
                },
            },
            "pipeline": {
                "enable_tracing": False,
                "sample_rate_in": 8000,
                "sample_rate_out": 8000,
            },
        }

    @staticmethod
    def get_llm_response_template(agent_type: str) -> Dict[str, Any]:
        """Get the complete template structure that LLMPrompts expects"""
        if agent_type == "single":
            agent_template = AgentTemplates.get_single_agent_template()
        else:
            agent_template = AgentTemplates.get_multi_agent_template()

        return {
            "agent_config": agent_template,
            "python_content": AgentTemplates.get_python_file_template(),
            "tools_list": [],
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

# EXAMPLE OF TOOLS SECTION FORMAT:
# def get_account_balance():
#     """Get the current account balance"""
#     return "Balance: $1,524.67"
#
# def get_recent_transactions():
#     """Fetch the most recent transactions"""
#     return "Here are your 3 most recent transactions."
#
# tool_config = {{
#     "get_account_balance": get_account_balance,
#     "get_recent_transactions": get_recent_transactions,
# }}


{callbacks_section}

# EXAMPLE OF CALLBACKS SECTION FORMAT:
# async def on_client_connected_callback(client):
#     """Callback function for when a client connects"""
#     pass
#
# async def on_first_participant_joined_callback(participant):
#     """Callback function for when the first participant joins"""
#     pass
#
# async def on_transcript_update_callback(data):
#     """Callback function for when a participant leaves"""
#     pass
# 
# async def on_participant_left_callback(data):
#     """Callback function for when a participant leaves"""
#     pass

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

    @staticmethod
    def add_guardrails_to_config(
        config: Dict[str, Any], guardrails_list: List[Dict[str, Any]], agent_type: str
    ) -> Dict[str, Any]:
        """Add guardrails configuration to the agent config"""
        if agent_type == "single":
            # For single agents, add guardrails to the LLM section
            config["agent"]["llm"]["guardrails"] = guardrails_list
        else:
            # For multi-agents, add guardrails to the agent_config and each individual agent
            config["agent"]["llm"]["agent_config"]["guardrails"] = {}

            # Add guardrails definitions
            for guardrail in guardrails_list:
                config["agent"]["llm"]["agent_config"]["guardrails"][
                    guardrail["name"]
                ] = {
                    "name": guardrail["name"],
                    "instructions": guardrail["instructions"],
                }

            # Add guardrails to each agent (this will be handled by the LLM when creating agents)

        return config

import os
import logfire

from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from agents import (
    Agent,
    Runner,
    InputGuardrail,
    RunContextWrapper,
    GuardrailFunctionOutput,
)

from .utils.tools import tool_config


class OffTopic(BaseModel):
    is_off_topic: bool
    reasoning: str


class AgentFactory:
    def __init__(
        self,
        config: Dict,
        context: Optional[RunContextWrapper] = None,
        user_defined_tools: Optional[Dict[str, Any]] = None,
    ):
        self._config = config
        self._context = context
        self._user_defined_tools = user_defined_tools
        self._setup()

    def _setup(self):
        if self._config.get("logfire_trace", False):
            self._traceSetup()

        agent_config = self._config.get("agents", {})
        self._model = self._config.get("model", "gpt-4o-mini")
        input_guardrails = self._setup_input_guardrails(
            self._config.get("guardrails", {})
        )

        self._setup_agents(agent_config, input_guardrails)

    def _traceSetup(self):
        """
        Optional
        Setups span tracing for OpenAI agents using Logfire.

        Requires Logfire variables in the .env file
            TOKEN
            PROJECT_NAME
            PROJECT_URL
            LOGFIRE_API_URL
        """
        load_dotenv()

        token = os.getenv("TOKEN")
        if not token:
            print("Logfire token not found in .env file. Tracing will be disabled.")
            return

        logfire.configure(
            service_name="agent_handler",
            token=token,
            console=False,
        )
        logfire.instrument_openai_agents()

    def _setup_agents(
        self,
        agent_config: Dict[str, Dict],
        input_guardrails: Optional[List[InputGuardrail]],
    ):
        self.agents: Dict[str, Agent] = {}
        handoffs: Dict[str, List[str]] = {}

        for key, value in agent_config.items():
            handoffs[key] = value.get("handoffs", [])
            tools = self._setup_tools(required_tools=value.get("tools", []))

            guardrails = (
                [
                    input_guardrails[name]
                    for name in value.get("input_guardrails", [])
                    if input_guardrails and name in input_guardrails
                ]
                if input_guardrails
                else []
            )

            agent_params = {
                # Major parameters
                "name": value.get("name"),
                "instructions": value.get("instructions"),
                "handoff_description": value.get("handoff_description"),
                # Defined parameters
                "tools": tools,
                # Optional parameters
                "output_type": value.get("output_type"),
            }

            agent = self._create_agent(self._context, **agent_params)
            self.agents[key] = (agent, guardrails)

        self._setup_handoffs(handoffs)

    def _setup_handoffs(self, handoffs: Dict[str, List[str]]):
        """
        Sets up handoffs for agents

        Called after all agents are created
        (There may be circular handoffs, henceforth the handoffs are setup at the end)
        """
        for name, handoff_names in handoffs.items():
            agent = self.agents.get(name)[0]
            if not agent:
                raise ValueError(f"Agent {name} not found")
            handoff_agents = [
                self.agents.get(agent_name)[0] for agent_name in handoff_names
            ]
            agent.handoffs = handoff_agents

    def _setup_input_guardrails(self, input_guardrails: Dict[str, Dict]):
        guardrails = {}
        for key, value in input_guardrails.items():
            name = value.get("name")
            instructions = value.get("instructions")

            if not name or not instructions:
                raise ValueError(f"Guardrail '{key}' must have a name and instructions")

            agent = self._create_agent(
                name=name,
                instructions=instructions,
                output_type=OffTopic,
            )

            guardrails[key] = self._make_guardrail_function(agent, key)

        return guardrails

    def _make_guardrail_function(self, guardrail_agent: Agent, name: str):
        async def guardrail(
            ctx: RunContextWrapper, agent: Agent, input: str
        ) -> GuardrailFunctionOutput:
            result = await Runner.run(guardrail_agent, input, context=ctx.context)
            final_output = result.final_output_as(OffTopic)
            return GuardrailFunctionOutput(
                output_info=final_output,
                tripwire_triggered=final_output.is_off_topic,
            )

        return InputGuardrail(guardrail_function=guardrail, name=name)

    def _setup_tools(self, required_tools: List[str]):
        tool_lt = []
        for tool_name in required_tools:
            tool = self._user_defined_tools.get(tool_name) or tool_config.get(tool_name)
            if not tool:
                raise ValueError(
                    f"Tool '{tool_name}' not found in userdefined_tools or tool_config"
                )
            tool_lt.append(tool)
        return tool_lt

    def _create_agent(self, context: RunContextWrapper | None = None, **kwargs):
        if not kwargs["name"] or not kwargs["instructions"]:
            raise ValueError("Agent name and instructions are required parameters")
        return Agent[context](model=self._model, **kwargs)

    def get_agent(self, name: str):
        return self.agents.get(name, (None, None))

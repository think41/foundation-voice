from typing import Dict, List, override
from pipecat.services.cerebras.llm import CerebrasLLMService as _OG_CerebrasLLMService


class GuardrailCerebrasLLMService(_OG_CerebrasLLMService):
    def __init__(self, model: str, instructions: str, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.instructions = instructions

    def _create_base_message(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    f"{self.instructions}\n\n"
                    "You must respond in JSON format with the following structure:\n"
                    "{\n"
                    '  "is_off_topic": boolean,\n'
                    '  "reasoning": "string explanation"\n'
                    "}\n\n"
                    "Determine whether the user's message is an appropriate and relevant response "
                    "to the assistant's message and follows the context of the system prompt.\n\n"
                    "Here are the last two messages from the conversation:\n"
                    f"{messages}"
                ),
            }
        ]

    @override
    async def get_chat_completions(
        self,
        messages: List[Dict[str, str]],
    ):
        output_schema = {
            "type": "object",
            "properties": {
                "is_off_topic": {
                    "type": "boolean",
                },
                "reasoning": {
                    "type": "string",
                },
            },
            "required": ["is_off_topic", "reasoning"],
            "additional_properties": False,
        }

        check_messages = self._create_base_message(messages)

        params = {
            "model": self.model,
            "stream": False,
            "messages": check_messages,
            "tool_choice": "none",
            "seed": self._settings["seed"],
            "temperature": self._settings["temperature"],
            "top_p": self._settings["top_p"],
            "max_completion_tokens": self._settings["max_completion_tokens"],
        }

        params["response_format"] = {
            "type": "json_object",  # Changed from json_schema to json_object
            "schema": output_schema,
        }

        response = await self._client.chat.completions.create(**params)
        return response

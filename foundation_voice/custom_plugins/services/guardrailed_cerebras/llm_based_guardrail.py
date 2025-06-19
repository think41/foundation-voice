from typing import Dict, override
from pipecat.services.cerebras.llm import CerebrasLLMService as _OG_CerebrasLLMService


class GuardrailCerebrasLLMService(_OG_CerebrasLLMService):
    def __init__(
        self, 
        model: str,
        instructions: str,
        **kwargs    
    ):
        super().__init__(**kwargs)
        self.model = model 
        self.instructions = instructions

    def _create_base_message(self):
        return [
            {
                "role": "system",
                "content": f"{self.instructions}\n\nYou must respond in JSON format with the following structure: {{\"is_off_topic\": boolean, \"reasoning\": \"string explanation\"}}."
            }
        ]

    @override
    async def get_chat_completions(
        self, 
        message: Dict[str, str],
    ):
        output_schema = {
            "type": "object",
            "properties": {
                "is_off_topic": {
                    "type": "boolean",
                },
                "reasoning": {
                    "type": "string",
                }
            },
            "required": ["is_off_topic", "reasoning"],
            "additional_properties": False 
        }

        messages = self._create_base_message()
        messages.append(message)

        params = {
            "model": self.model,
            "stream": False,
            "messages": messages,
            "seed": self._settings["seed"],
            "temperature": self._settings["temperature"],
            "top_p": self._settings["top_p"],
            "max_completion_tokens": self._settings["max_completion_tokens"],
        }

        params["response_format"] = {
            "type": "json_object",  # Changed from json_schema to json_object
            "schema": output_schema
        }

        response = await self._client.chat.completions.create(**params)
        return response
        
        
        

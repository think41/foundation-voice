import asyncio

from loguru import logger
from typing import Any, Dict, List, override

from pipecat.frames.frames import LLMTextFrame, FunctionCallFromLLM
from pipecat.metrics.metrics import LLMTokenUsage
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.tracing.service_decorators import traced_llm
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

from foundation_voice.custom_plugins.services.guardrailed_cerebras.llm_based_guardrail import (
    GuardrailCerebrasLLMService,
)


class GuardrailedLLMService(OpenAILLMService):
    def __init__(
        self,
        llm_service,
        guardrails: List[Dict[str, Any]],
        prompt: str,
        api_key: str = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.llm_service = llm_service
        self.guardrails = self._create_guardrails(guardrails)
        self.prompt = prompt

    def _create_guardrails(self, guardrails_lt: List[Dict[str, Any]]):
        guardrails = {}
        for guardrail in guardrails_lt:
            guardrails[guardrail["name"]] = GuardrailCerebrasLLMService(
                model=guardrail["model"],
                instructions=guardrail["instructions"],
                api_key=self.api_key,
            )

        return guardrails

    @override
    @traced_llm
    async def _process_context(self, context: OpenAILLMContext):
        # Extract user input for guardrail evaluation
        user_input = self._get_user_input(context)
        assistant_input = self._get_assistant_input(context)

        # Variables to collect tool call information
        functions_list = []
        arguments_list = []
        tool_id_list = []
        func_idx = 0
        function_name = ""
        arguments = ""
        tool_call_id = ""

        # Create an event for cancellation
        cancel_event = asyncio.Event()

        await self.start_ttfb_metrics()

        # Define a task to stream chunks directly from LLM service
        async def stream_llm():
            try:
                # Get the stream from the underlying LLM service
                chunk_stream = await self.llm_service._stream_chat_completions(context)

                nonlocal \
                    functions_list, \
                    arguments_list, \
                    tool_id_list, \
                    func_idx, \
                    function_name, \
                    arguments, \
                    tool_call_id

                async for chunk in chunk_stream:
                    if cancel_event.is_set():
                        break

                    # Process metrics
                    if chunk.usage:
                        tokens = LLMTokenUsage(
                            prompt_tokens=chunk.usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens,
                        )
                        await self.start_llm_usage_metrics(tokens)

                    if chunk.choices is None or len(chunk.choices) == 0:
                        continue

                    await self.stop_ttfb_metrics()

                    if not chunk.choices[0].delta:
                        continue

                    # Handle tool calls
                    if chunk.choices[0].delta.tool_calls:
                        tool_call = chunk.choices[0].delta.tool_calls[0]
                        if tool_call.index != func_idx:
                            functions_list.append(function_name)
                            arguments_list.append(arguments)
                            tool_id_list.append(tool_call_id)
                            function_name = ""
                            arguments = ""
                            tool_call_id = ""
                            func_idx += 1
                        if tool_call.function and tool_call.function.name:
                            function_name += tool_call.function.name
                            tool_call_id = tool_call.id
                        if tool_call.function and tool_call.function.arguments:
                            arguments += tool_call.function.arguments
                    # Forward content chunks directly
                    elif chunk.choices[0].delta.content:
                        await self.push_frame(
                            LLMTextFrame(chunk.choices[0].delta.content)
                        )
                    elif hasattr(chunk.choices[0].delta, "audio") and chunk.choices[
                        0
                    ].delta.audio.get("transcript"):
                        await self.push_frame(
                            LLMTextFrame(chunk.choices[0].delta.audio["transcript"])
                        )
            except Exception as e:
                logger.error(f"Error in LLM streaming: {e}")

        # Create and start the streaming task
        stream_task = asyncio.create_task(stream_llm())

        # Run guardrails in parallel if we have user input
        guardrail_failure_reason = ""

        if self.guardrails and user_input:
            logger.info("Running guardrails")

            # Run guardrails in parallel
            guardrail_tasks = []
            for name, guardrail in self.guardrails.items():
                # Create a message with user input for guardrail evaluation
                message = [
                    {"role": "system", "content": self.prompt},
                    {"role": "assistant", "content": assistant_input},
                    {"role": "user", "content": user_input},
                ]
                guardrail_tasks.append((name, guardrail.get_chat_completions(message)))

            # Wait for all guardrail evaluations
            for name, task in guardrail_tasks:
                try:
                    result = await task
                    # Parse the JSON response from the guardrail
                    response_json = result.choices[0].message.content
                    if isinstance(response_json, str):
                        import json

                        try:
                            response_json = json.loads(response_json)
                        except json.JSONDecodeError:
                            logger.error(
                                f"Failed to parse guardrail response: {response_json}"
                            )
                            continue

                    logger.info(f"Guardrail {name} response: {response_json}")

                    # Check if guardrail triggered
                    if response_json.get("is_off_topic", False):
                        guardrail_failure_reason = response_json.get("reasoning", "")

                        # Cancel the streaming task
                        cancel_event.set()
                        try:
                            await stream_task
                        except asyncio.CancelledError:
                            pass

                        # Send blocked response
                        await self.push_frame(
                            LLMTextFrame(
                                "I'm unable to provide a response to that request."
                            )
                        )
                        logger.warning(
                            f"Guardrail {name} blocked output: {guardrail_failure_reason}"
                        )
                        return
                except Exception as e:
                    # Log error but continue (assume guardrail passed if it fails)
                    logger.error(f"Error evaluating guardrail {name}: {e}")

        # Wait for streaming to complete if guardrails passed
        await stream_task

        # Process function calls if any
        if function_name and arguments:
            # Add the last function call
            functions_list.append(function_name)
            arguments_list.append(arguments)
            tool_id_list.append(tool_call_id)

            function_calls = []

            for function_name, arguments, tool_id in zip(
                functions_list, arguments_list, tool_id_list
            ):
                try:
                    import json

                    arguments = json.loads(arguments)
                    function_calls.append(
                        FunctionCallFromLLM(
                            context=context,
                            tool_call_id=tool_id,
                            function_name=function_name,
                            arguments=arguments,
                        )
                    )
                except json.JSONDecodeError:
                    logger.error(f"Error decoding arguments: {arguments}")

            await self.run_function_calls(function_calls)

    def _get_user_input(self, context):
        """Extract the user input from the context"""
        if hasattr(context, "messages") and context.messages:
            for msg in reversed(context.messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
        return ""

    def _get_assistant_input(self, context):
        """Extract the assistant input from the context"""
        if hasattr(context, "messages") and context.messages:
            for msg in reversed(context.messages):
                if msg.get("role") == "assistant":
                    return msg.get("content", "")
        return ""

    def _extract_full_output(self, buffer):
        """Extract the full text output from buffer chunks"""
        full_output = ""
        for chunk in buffer:
            if (
                chunk.choices
                and chunk.choices[0].delta
                and chunk.choices[0].delta.content
            ):
                full_output += chunk.choices[0].delta.content
        return full_output

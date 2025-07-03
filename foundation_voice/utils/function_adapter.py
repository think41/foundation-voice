import inspect
from loguru import logger

from typing import Callable, Dict, get_type_hints, Union

try:
    from agents import function_tool
except ImportError:
    function_tool = None

from pipecat.adapters.schemas.function_schema import FunctionSchema


class FunctionAdapter:
    def __init__(self, func: Callable, description: str = ""):
        self.func = func
        self.description = description or func.__doc__
        self.name = func.__name__
        self.signature = inspect.signature(func)
        self.annotations = get_type_hints(func)

    def to_tool_schema(self):
        if function_tool is None:
            raise RuntimeError(
                "The 'agents' package is not installed, but it's required to use 'to_tool_schema'. "
                "Please install it, for example, with 'pip install foundation-voice[openai_agents]' or your specific extras."
            )
        return function_tool(
            name_override=self.name, description_override=self.description
        )(self.func)

    def to_function_schema(self):
        properties = {}
        required = []

        for param_name, param in self.signature.parameters.items():
            logger.info(param_name)
            if param_name == "ctx":
                logger.warning(
                    "Context parameter not allowed for llm functions. Skipping function"
                )
                return None

            annotation = self.annotations.get(param_name, str)

            json_type = self._python_type_to_json_type(annotation)

            properties[param_name] = {
                "type": json_type,
                "description": f"{param_name} parameter",
            }

            if param.default is inspect.Parameter.empty and not self._is_optional(
                annotation
            ):
                required.append(param_name)

        schema = FunctionSchema(
            name=self.name,
            description=self.description,
            properties=properties,
            required=required,
        )

        return {"schema": schema, "function": self._wrap_function()}

    def _wrap_function(self):
        async def wrapped_function(
            function_name, tool_call_id, args, llm, context, result_callback
        ):
            try:
                if inspect.iscoroutinefunction(self.func):
                    result = await self.func(**args)
                else:
                    result = self.func(**args)

                await result_callback(result)

            except Exception as e:
                logger.error(f"Failed to execute function {self.name}: {e}")
                await result_callback({"error": str(e)})

        return wrapped_function

    def _is_optional(self, annotation):
        origin = getattr(annotation, "__origin__", None)
        if origin is Union:
            return getattr(annotation, "__origin__", None) is Union and type(
                None
            ) in getattr(annotation, "__args__", [])
        return False

    def _python_type_to_json_type(self, annotation) -> str:
        origin = getattr(annotation, "__origin__", None)
        base = origin or annotation

        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        return mapping.get(base, "string")


class FunctionFactory:
    def __init__(self, provider: str, functions: Dict[str, Callable]):
        self.provider = provider
        self.functions = functions
        self.built_tools = self.create_functions()  # <--- Store result here

    def create_functions(self) -> Dict[str, Callable]:
        if self.provider == "openai_agents":
            tools = {}
            for name, func in self.functions.items():
                tools[name] = FunctionAdapter(func).to_tool_schema()
            return tools

        elif self.provider in ["openai", "cerebras", "groq"]:
            functions_dt = {}
            for name, func in self.functions.items():
                function = FunctionAdapter(func).to_function_schema()
                if function is not None:
                    functions_dt[name] = function
            return functions_dt
        else:
            raise ValueError(f"Invalid provider: {self.provider}")

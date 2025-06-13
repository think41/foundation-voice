from typing import Callable, Awaitable, Any, Optional

from agents.lifecycle import RunHooks  # type: ignore
from agents import Agent, Tool, RunContextWrapper  # type: ignore


class BufferRunHooks(RunHooks):
    """Custom ``RunHooks`` implementation that exposes the ``on_tool_start``
    lifecycle event to the application layer.

    The primary motivation is to allow emitting a pre-emptive response (e.g.
    "Hang on while I look that up…") before a tool call is executed.

    A callback can be provided which will be invoked whenever the event fires.
    The callback receives the *context*, *agent* and *tool* objects so that it
    can decide what to do – for example, enqueue a chunk onto a buffer that is
    streamed back to the client.
    """

    def __init__(
        self,
        on_tool_start: Optional[
            Callable[[RunContextWrapper, Agent, Tool], Awaitable[Any] | Any]
        ] = None,
    ) -> None:
        super().__init__()
        self._on_tool_start_cb = on_tool_start

    # ---------------------------------------------------------------------
    # Lifecycle events
    # ---------------------------------------------------------------------
    async def on_tool_start(
        self,
        context: RunContextWrapper,
        agent: Agent,
        tool: Tool,
    ) -> None:
        """Forward the *tool-start* event to the registered callback (if any)."""
        if self._on_tool_start_cb is None:
            return

        result = self._on_tool_start_cb(context, agent, tool)
        # Support both sync and async callbacks
        if isinstance(result, Awaitable):
            await result

    # Optionally expose ``on_tool_end`` here too so that future
    # use-cases can easily hook into it without changing this class.
    async def on_tool_end(
        self,
        context: RunContextWrapper,
        agent: Agent,
        tool: Tool,
        result: str,
    ) -> None:
        if self._on_tool_start_cb is None:
            return
        # We ignore the return value on purpose – future users can subclass
        # this class and override the method if they need custom behaviour.
        return

import asyncio
from inspect import iscoroutinefunction
from typing import Callable, Coroutine, NamedTuple, Union

from utils.events.interfaces import EventsInterface


class EventHandler(NamedTuple):
    name: str
    handler: Union[Callable, asyncio.Future]


class Events(EventsInterface):
    def __init__(self):
        self._events = []

    def subscribe(self, name: str, handler: Union[Callable, Coroutine]):
        # Check if already subscribed to prevent duplicate event handlers
        for event in self._events:
            if event.name == name and event.handler == handler:
                return  # Already subscribed, don't add again
        
        self._events.append(EventHandler(name=name, handler=handler))

    def unsubscribe(self, name: str, handler: Union[Callable, Coroutine]):
        for index, event in enumerate(self._events):
            if event.name == name and event.handler == handler:
                self._events.pop(index)

    async def async_dispatch(self, name: str, *args, **kwargs):
        tmp = []
        for event in self._events:
            if event.name == name:
                try:
                    if iscoroutinefunction(event.handler):
                        output = await event.handler(*args, **kwargs)
                    else:
                        output = event.handler(*args, **kwargs)
                    tmp.append(output)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Error in event handler for '{name}': {e}",
                        exc_info=True,
                    )
                    # Continue processing other handlers even if one fails
                    tmp.append(None)

        return tmp

    def dispatch(self, name: str, *args, **kwargs):
        return asyncio.to_thread(self.async_dispatch, name, *args, **kwargs)

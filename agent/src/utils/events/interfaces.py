from typing import Callable, Coroutine, Union


class EventsInterface:
    def subscribe(self, name: str, handler: Union[Callable, Coroutine]):
        pass

    def unsubscribe(self, name: str, handler: Union[Callable, Coroutine]):
        pass

    async def async_dispatch(self, name: str, *args, **kwargs):
        pass

    def dispatch(self, name: str, *args, **kwargs):
        pass

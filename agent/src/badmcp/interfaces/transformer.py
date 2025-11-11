from abc import ABC, abstractmethod


class TransformerInterface(ABC):
    @abstractmethod
    def transform(self, schema: dict) -> dict:
        pass

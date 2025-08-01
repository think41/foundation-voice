from enum import Enum
from abc import ABC, abstractmethod


class SIPService(ABC):
    def __init__(self):
        self._api = None

    def _setup(self):
        pass

    @abstractmethod
    async def create_trunk(self):
        pass

    def update_trunk(self, trunk_id: str):
        pass

    def delete_trunk(self, trunk_id: str):
        pass

    def list_trunks(self):
        pass

    @abstractmethod
    async def create_dispatch(self):
        pass

    @abstractmethod
    async def transfer_call(self):
        pass


class Stream(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

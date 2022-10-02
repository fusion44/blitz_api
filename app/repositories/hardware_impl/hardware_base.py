from abc import abstractmethod


class HardwareBase:
    @abstractmethod
    async def get_hardware_info(self) -> map:
        raise NotImplementedError()

    @abstractmethod
    def get_hardware_info_yield_time(self) -> float:
        raise NotImplementedError()

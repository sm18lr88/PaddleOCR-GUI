class CudaDevice:
    def device_count(self) -> int: ...


class DeviceModule:
    cuda: CudaDevice

    def is_compiled_with_cuda(self) -> bool: ...
    def get_device(self) -> str: ...


device: DeviceModule

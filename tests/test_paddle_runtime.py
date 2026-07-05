import pytest

from paddlepdf.errors import PaddleVlServerUnavailableError
from paddlepdf.models import ConversionOptions, DeviceChoice
from paddlepdf.paddle_runtime import device_warnings, paddle_device, vl_health_url


def test_vl_health_url_rejects_credentials() -> None:
    with pytest.raises(PaddleVlServerUnavailableError) as exc_info:
        vl_health_url("http://user:secret@localhost:8118/v1")

    assert "must not include credentials" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_vl_health_url_maps_server_endpoint_to_health() -> None:
    assert vl_health_url("http://127.0.0.1:8118/v1") == "http://127.0.0.1:8118/health"


def test_gpu_device_falls_back_to_cpu_with_warning_when_cuda_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("paddlepdf.paddle_runtime.paddle_gpu_available", lambda: False)
    options = ConversionOptions(device=DeviceChoice.GPU)

    assert paddle_device(DeviceChoice.GPU) == "cpu"
    assert device_warnings(options) == (
        "GPU was requested but PaddlePaddle CUDA is unavailable; using CPU.",
    )


def test_gpu_device_has_no_warning_when_cuda_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("paddlepdf.paddle_runtime.paddle_gpu_available", lambda: True)
    options = ConversionOptions(device=DeviceChoice.GPU)

    assert paddle_device(DeviceChoice.GPU) == "gpu:0"
    assert device_warnings(options) == ()

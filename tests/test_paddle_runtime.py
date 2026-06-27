import pytest

from paddlepdf.errors import PaddleVlServerUnavailableError
from paddlepdf.paddle_runtime import vl_health_url


def test_vl_health_url_rejects_credentials() -> None:
    with pytest.raises(PaddleVlServerUnavailableError) as exc_info:
        vl_health_url("http://user:secret@localhost:8118/v1")

    assert "must not include credentials" in str(exc_info.value)


def test_vl_health_url_maps_server_endpoint_to_health() -> None:
    assert vl_health_url("http://127.0.0.1:8118/v1") == "http://127.0.0.1:8118/health"

from __future__ import annotations

import os
from http import HTTPStatus
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

from paddlepdf.cuda_paths import add_windows_cuda_dll_directories
from paddlepdf.errors import (
    PaddleRuntimeUnavailableError,
    PaddleVlServerUnavailableError,
)
from paddlepdf.models import MODEL_PIPELINE_VERSION, ConversionOptions, DeviceChoice

if TYPE_CHECKING:
    from paddleocr import PaddleOCRVL

SERVER_URL_ENV = "PADDLEOCR_VL_SERVER_URL"
HEALTH_TIMEOUT_SECONDS = 3
HTTP_PORT = 80
HTTPS_PORT = 443


def create_vl_pipeline(options: ConversionOptions) -> PaddleOCRVL:
    prepare_paddle_runtime()
    server_url = resolve_vl_server_url(options)
    verify_vl_server(server_url)
    try:
        from paddleocr import PaddleOCRVL
    except ModuleNotFoundError as exc:
        raise PaddleRuntimeUnavailableError(package_name="paddleocr") from exc
    device = paddle_device(options.device)
    backend = f"{options.vl_backend.value}-server"
    if device is None:
        return PaddleOCRVL(
            pipeline_version=MODEL_PIPELINE_VERSION,
            vl_rec_backend=backend,
            vl_rec_server_url=server_url,
            use_doc_orientation_classify=options.orientation_correction,
            use_doc_unwarping=options.document_unwarping,
            use_layout_detection=options.preserve_layout,
        )
    return PaddleOCRVL(
        pipeline_version=MODEL_PIPELINE_VERSION,
        device=device,
        vl_rec_backend=backend,
        vl_rec_server_url=server_url,
        use_doc_orientation_classify=options.orientation_correction,
        use_doc_unwarping=options.document_unwarping,
        use_layout_detection=options.preserve_layout,
    )


def close_vl_pipeline(pipeline: PaddleOCRVL) -> None:
    pipeline.paddlex_pipeline.vl_rec_model.genai_client.close()


def prepare_paddle_runtime() -> None:
    add_windows_cuda_dll_directories()
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("FLAGS_minloglevel", "2")


def resolve_vl_server_url(options: ConversionOptions) -> str:
    server_url = options.vl_server_url or os.environ.get(SERVER_URL_ENV)
    if server_url is None or server_url.strip() == "":
        raise PaddleVlServerUnavailableError(
            url=f"${SERVER_URL_ENV}",
            reason=(
                "set --vl-server-url or PADDLEOCR_VL_SERVER_URL to an "
                "optimized GenAI server /v1 endpoint"
            ),
        )
    return server_url.rstrip("/")


def verify_vl_server(server_url: str) -> None:
    health_url = vl_health_url(server_url)
    parsed = urlparse(health_url)
    port = parsed.port or (HTTPS_PORT if parsed.scheme == "https" else HTTP_PORT)
    connection_class = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
    connection = connection_class(
        parsed.hostname or "", port=port, timeout=HEALTH_TIMEOUT_SECONDS
    )
    try:
        connection.request("GET", parsed.path)
        response = connection.getresponse()
        if response.status != HTTPStatus.OK:
            raise PaddleVlServerUnavailableError(
                url=server_url,
                reason=f"health endpoint returned HTTP {response.status}",
            )
    except (HTTPException, OSError) as exc:
        raise PaddleVlServerUnavailableError(
            url=server_url, reason=f"health check failed: {exc}"
        ) from exc
    finally:
        connection.close()


def vl_health_url(server_url: str) -> str:
    parsed = urlparse(server_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
        raise PaddleVlServerUnavailableError(
            url=server_url,
            reason="expected an HTTP(S) URL such as http://localhost:8118/v1",
        )
    if parsed.username is not None or parsed.password is not None:
        raise PaddleVlServerUnavailableError(
            url=server_url,
            reason="server URL must not include credentials",
        )
    return urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))


def paddle_device(device: DeviceChoice) -> str | None:
    match device:
        case DeviceChoice.AUTO:
            return None
        case DeviceChoice.CPU:
            return "cpu"
        case DeviceChoice.GPU:
            return "gpu:0"

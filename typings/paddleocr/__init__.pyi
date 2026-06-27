from collections.abc import Iterable
from pathlib import Path

class PaddleOCRVLResult:
    def save_to_json(self, save_path: str | Path) -> None: ...
    def save_to_markdown(self, save_path: str | Path) -> None: ...

class GenAIClient:
    def close(self) -> None: ...

class VlRecModel:
    genai_client: GenAIClient

class PaddleXPipeline:
    vl_rec_model: VlRecModel

class PaddleOCRVL:
    paddlex_pipeline: PaddleXPipeline

    def __init__(
        self,
        *,
        pipeline_version: str = ...,
        device: str | None = ...,
        vl_rec_backend: str | None = ...,
        vl_rec_server_url: str | None = ...,
        use_doc_orientation_classify: bool = ...,
        use_doc_unwarping: bool = ...,
        use_layout_detection: bool = ...,
    ) -> None: ...
    def predict(
        self,
        input_path: str,
        *,
        use_layout_detection: bool | None = ...,
        prompt_label: str | None = ...,
        max_new_tokens: int | None = ...,
        max_pixels: int | None = ...,
    ) -> Iterable[PaddleOCRVLResult]: ...

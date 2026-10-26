from pathlib import Path

class ResourceAccessPolicy:
    def __init__(
        self,
        *,
        allow_remote: bool = ...,
        base_dir: str | Path | None = ...,
    ) -> None: ...

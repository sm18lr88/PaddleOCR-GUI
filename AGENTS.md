# Agent usage contract

Agents must use the CLI surface, not the GUI, for automated document processing.

Preferred local MCP server:

```bash
uv --directory D:\Apps\Document_Processing\paddlepdf run paddlepdf-mcp
```

## Fresh clone setup

Do not expect GitHub to contain `.venv`, `dist`, PaddleOCR model caches, CUDA DLL
caches, OCR outputs, or bundled zips. Recreate them locally.

Windows GPU-first setup:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv sync --dev --extra ocr --extra gpu
uv run paddlepdf convert test\2606.27226v1.pdf --out output --format markdown --agent
```

CPU-only fallback:

```bash
uv sync --dev --extra ocr --extra cpu
```

Windows bundle rebuild:

```powershell
.\package_windows.ps1
```

First real conversion downloads PaddleOCR/PaddleOCR-VL weights into the user's
normal model cache. Default conversion is native and GPU-first on Windows; a
report warning means PaddlePaddle CUDA was unavailable or CPU was selected.

Use the `convert_documents` MCP tool with top-level `input_files`, `output_dir`, `output_format`, optional OCR/server settings, and `dry_run` when validation should not contact PaddleOCR-VL.

Windows bundle:

```powershell
.\PaddleOCR-GUI-CLI.exe convert input.pdf --out output --format markdown --vl-server-url http://127.0.0.1:8118/v1 --agent
```

Native Windows GPU-first bundle command:

```powershell
.\PaddleOCR-GUI-CLI.exe convert input.pdf --out output --format markdown --agent
```

Source checkout:

```bash
uv run paddlepdf convert input.pdf --out output --format markdown --agent
```

The agent contract is:

- Always pass `--agent` for deterministic JSON on stdout.
- Treat exit code `0` as success and any nonzero exit as failed/partial.
- Read `status`, `output_files`, `warnings`, `errors`, and `documents` from stdout JSON.
- Preserve every path in `output_files`; it may include sidecar assets such as extracted figures/page images referenced by Markdown output.
- Do not scrape GUI text or terminal progress bars.
- Supported inputs are PDF and common image files: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`.
- Every distribution format, including any future Docker image, must expose this same CLI command shape and JSON contract.
- Default conversion is native and GPU-first on Windows; pass `--vl-server-url` or set `PADDLEOCR_VL_SERVER_URL` only when intentionally targeting a separate PaddleOCR-VL GenAI server. `dry_run` does not contact PaddleOCR-VL.

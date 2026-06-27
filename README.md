# PaddleOCR-GUI

PaddleOCR-GUI is a Python desktop app and CLI for converting one or more PDFs with the SOTA PaddleOCR-VL-1.6 document parsing pipeline.

It uses `PaddleOCRVL(pipeline_version="v1.6")` with an optimized GenAI server backend (`vllm`, `sglang`, or `fastdeploy`). The slow native in-process VL backend is intentionally not exposed. Model weights are not included in this repo; PaddleOCR downloads and caches the official files on first use.

## Install UV

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup: client app

```bash
uv sync --dev --extra ocr --extra gpu
```

This installs the client app, PaddleOCR document parser, and CUDA 12.9 PaddlePaddle GPU runtime by default. The project uses UV's `[tool.uv.sources]` configuration so normal Python packages resolve from PyPI and only `paddlepaddle-gpu` resolves from PaddlePaddle's official CUDA 12.9 wheel index.

Windows PowerShell users can run:

```powershell
.\setup.ps1
```

macOS/Linux users can run:

```bash
chmod +x setup.sh run_gui.sh
./setup.sh
```

## Start an optimized PaddleOCR-VL server

PaddleOCR-GUI requires an optimized PaddleOCR-VL GenAI server. Native local VL inference was measured at several minutes for only a few pages, so the app fails fast if no server URL is configured.

Official PaddleOCR server commands use one of these backends:

```bash
paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --backend vllm --port 8118
paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --backend sglang --port 8118
paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --backend fastdeploy --port 8118
```

Then configure the app with either:

```bash
export PADDLEOCR_VL_SERVER_URL=http://localhost:8118/v1
```

or pass `--vl-server-url http://localhost:8118/v1` to the CLI. On Windows PowerShell:

```powershell
$env:PADDLEOCR_VL_SERVER_URL = "http://localhost:8118/v1"
```

The server machine should be configured according to PaddleOCR's hardware/backend guide. On Windows client machines, running the GenAI server in Linux, WSL2, Docker, or a remote GPU host is recommended.

Validated Docker GPU server path:

```bash
docker run --rm --name paddleocr-vl-server --gpus all --shm-size 8g -p 8118:8118 \
  ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddleocr-genai-vllm-server:latest-nvidia-gpu \
  paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --host 0.0.0.0 --port 8118 --backend vllm
```

Use `http://127.0.0.1:8118/v1` from the client after the container health endpoint is ready.

## Optional CPU-only client setup

Use this only when the client machine does not need local CUDA libraries. SOTA VL inference still happens on the configured GenAI server.

```bash
uv sync --dev --extra ocr --extra cpu
```

Windows PowerShell users can run `./setup_cpu.ps1`. macOS/Linux users can run `./setup_cpu.sh`.

Do not install CPU and GPU PaddlePaddle packages together. UV marks these extras as conflicting.

## Other GPU versions

CUDA 12.9 is the default pinned GPU path. CUDA 12.6 from the PaddleOCR-VL model card can be installed manually if your environment requires it:

```bash
uv pip uninstall paddlepaddle-gpu
uv pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

For Apple Silicon or other accelerators, follow the official PaddleOCR-VL hardware guide first, then run this app in that environment.

## Run the GUI

```bash
uv run paddlepdf-gui
```

Windows PowerShell:

```powershell
.\run_gui.ps1
```

macOS/Linux:

```bash
./run_gui.sh
```

The GUI lets users select PDFs, choose an output folder, choose Markdown/JSON/text/all, set the VL backend and server URL, set OCR knobs, watch progress, and open the output folder when conversion completes. Conversion runs in a worker thread so the window stays responsive. The interface auto-detects the OS language and can be switched manually between English, Spanish, Korean, Chinese, Japanese, Hebrew, and Arabic.

## Run the CLI

```bash
uv run paddlepdf convert input1.pdf input2.pdf --out ./output --format markdown --vl-server-url http://localhost:8118/v1
```

Useful options:

```bash
uv run paddlepdf convert paper.pdf --out ./output --format all --vl-backend vllm --vl-server-url http://localhost:8118/v1
uv run paddlepdf convert paper.pdf --out ./output --format text --plain-flow --vl-server-url http://localhost:8118/v1
uv run paddlepdf convert paper.pdf --out ./output --dry-run
```

Outputs are written into predictable per-document folders under the selected output folder. PDF names are sanitized and duplicate stems become `name`, `name-2`, and so on.

## Agent usage

Setup:

```bash
uv sync --dev --extra ocr --extra gpu
```

Command:

```bash
uv run paddlepdf convert input1.pdf input2.pdf --out ./output --format markdown --vl-server-url http://localhost:8118/v1 --agent
```

Dry-run command that does not load PaddleOCR:

```bash
uv run paddlepdf convert input.pdf --out ./output --format all --dry-run --agent
```

`--agent` prints deterministic JSON to stdout with:

- `status`
- `input_files`
- `output_files`
- `warnings`
- `errors`
- `elapsed_seconds`
- per-document status details

Exit code is `0` for success and nonzero for failed or partial runs.

## Package a zip

Windows PowerShell:

```powershell
Compress-Archive -Path pyproject.toml,README.md,setup.ps1,setup.sh,setup_cpu.ps1,setup_cpu.sh,run_gui.ps1,run_gui.sh,src,tests,typings -DestinationPath paddlepdf.zip -Force
```

macOS/Linux:

```bash
zip -r paddlepdf.zip pyproject.toml README.md setup.ps1 setup.sh setup_cpu.ps1 setup_cpu.sh run_gui.ps1 run_gui.sh src tests typings
```

Do not include `.venv`, model caches, or downloaded PaddleOCR weights in the zip.

## Troubleshooting

- First server conversion is slow because PaddleOCR downloads model files and initializes the GenAI backend.
- PaddleOCR downloads official models from Hugging Face by default. PaddleOCR-GUI disables PaddleOCR's pre-download hoster health check to avoid false negatives; set `PADDLE_PDX_MODEL_SOURCE=BOS` only if Hugging Face is inaccessible on your network.
- If `paddleocr is not installed`, run `uv sync --dev --extra ocr --extra gpu`.
- If PaddlePaddle import fails, install exactly one runtime package: CPU `paddlepaddle` or GPU `paddlepaddle-gpu`.
- If the app reports `PaddleOCR-VL server unavailable`, start the GenAI server and set `PADDLEOCR_VL_SERVER_URL` or pass `--vl-server-url`.
- If GPU runs out of memory, adjust the GenAI server backend configuration or use a larger remote GPU host.
- If macOS PaddlePaddle wheels are unavailable for your machine, use the official PaddleOCR-VL Docker or hardware-specific guide.
- Native local PaddleOCR-VL is not exposed because it was measured as too slow for a smooth GUI and currently emits upstream warnings under strict warning policy.

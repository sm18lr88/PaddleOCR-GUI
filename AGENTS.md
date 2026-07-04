# Agent usage contract

Agents must use the CLI surface, not the GUI, for automated document processing.

Preferred local MCP server:

```bash
uv --directory D:\Apps\Document_Processing\paddlepdf run paddlepdf-mcp
```

Use the `convert_documents` MCP tool with top-level `input_files`, `output_dir`, `output_format`, optional OCR/server settings, and `dry_run` when validation should not contact PaddleOCR-VL.

Windows bundle:

```powershell
.\PaddleOCR-GUI-CLI.exe convert input.pdf --out output --format markdown --vl-server-url http://127.0.0.1:8118/v1 --agent
```

Source checkout:

```bash
uv run paddlepdf convert input.pdf --out output --format markdown --vl-server-url http://127.0.0.1:8118/v1 --agent
```

The agent contract is:

- Always pass `--agent` for deterministic JSON on stdout.
- Treat exit code `0` as success and any nonzero exit as failed/partial.
- Read `status`, `output_files`, `warnings`, `errors`, and `documents` from stdout JSON.
- Preserve every path in `output_files`; it may include sidecar assets such as extracted figures/page images referenced by Markdown output.
- Do not scrape GUI text or terminal progress bars.
- Supported inputs are PDF and common image files: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`.
- Every distribution format, including any future Docker image, must expose this same CLI command shape and JSON contract.
- Start or target a PaddleOCR-VL GenAI server before conversion, then pass `--vl-server-url` or set `PADDLEOCR_VL_SERVER_URL`.

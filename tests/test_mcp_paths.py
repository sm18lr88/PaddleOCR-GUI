from pathlib import Path

from paddlepdf.mcp_server import McpConversionRequest, convert_mcp_request
from paddlepdf.models import RunStatus


def test_mcp_dry_run_accepts_quoted_escaped_input_path(tmp_path: Path) -> None:
    input_pdf = tmp_path / "1.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    escaped_input = str(input_pdf).replace("\\", "\\\\")

    report = convert_mcp_request(
        McpConversionRequest(
            input_files=(f'"{escaped_input}"',),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
        )
    )

    assert report.status == RunStatus.SUCCESS
    assert report.input_files == (input_pdf.resolve(),)

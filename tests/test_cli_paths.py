from pathlib import Path

from typer.testing import CliRunner

from paddlepdf.cli import app
from paddlepdf.models import AgentRunReport, RunStatus


def test_agent_json_dry_run_accepts_quoted_escaped_input_path(tmp_path: Path) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "1.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    escaped_input = str(input_pdf).replace("\\", "\\\\")

    result = runner.invoke(
        app,
        [
            "convert",
            f'"{escaped_input}"',
            "--out",
            str(tmp_path / "out"),
            "--dry-run",
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS
    assert report.input_files == (input_pdf.resolve(),)

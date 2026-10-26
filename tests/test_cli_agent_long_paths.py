from pathlib import Path

from typer.testing import CliRunner

from paddlepdf.cli import app
from paddlepdf.models import AgentRunReport, RunStatus


def test_agent_json_remains_valid_when_output_path_is_long(tmp_path: Path) -> None:
    input_image = tmp_path / "scan.png"
    input_image.write_bytes(b"not-a-real-image")
    output_dir = tmp_path / ("long-output-segment-" * 8)

    result = CliRunner().invoke(
        app,
        [
            "convert",
            str(input_image),
            "--out",
            str(output_dir),
            "--dry-run",
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paddlepdf.cli import app
from paddlepdf.models import AgentRunReport, ConversionOptions, RunStatus


class FakeVlResult:
    def save_to_json(self, save_path: str | Path) -> None:
        Path(save_path, "paper_0.json").write_text("{}", encoding="utf-8")

    def save_to_markdown(self, save_path: str | Path) -> None:
        Path(save_path, "paper_0.md").write_text("# Paper", encoding="utf-8")


class FakeBenignPipeline:
    def predict(self, input_path: str) -> tuple[FakeVlResult, ...]:
        Path(input_path).is_file()
        sys.stdout.write("Creating model: ('PaddleOCR-VL-1.6-0.9B', None, None)\n")
        return (FakeVlResult(),)


class FakeWarningPipeline:
    def predict(self, input_path: str) -> tuple[FakeVlResult, ...]:
        Path(input_path).is_file()
        sys.stdout.write("ResourceWarning: unclosed socket\n")
        return (FakeVlResult(),)


def create_benign_pipeline(options: ConversionOptions) -> FakeBenignPipeline:
    options.model_dump()
    return FakeBenignPipeline()


def create_warning_pipeline(options: ConversionOptions) -> FakeWarningPipeline:
    options.model_dump()
    return FakeWarningPipeline()


def close_benign_pipeline(_pipeline: FakeBenignPipeline) -> None:
    return None


def close_warning_pipeline(_pipeline: FakeWarningPipeline) -> None:
    return None


def test_agent_json_when_input_missing(tmp_path: Path) -> None:
    runner = CliRunner()
    missing_pdf = tmp_path / "missing.pdf"

    result = runner.invoke(
        app, ["convert", str(missing_pdf), "--out", str(tmp_path), "--agent"]
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 1
    assert report.status == RunStatus.FAILED
    assert str(missing_pdf) in report.errors[0]


def test_agent_json_when_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "Example PDF.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    result = runner.invoke(
        app,
        [
            "convert",
            str(input_pdf),
            "--out",
            str(tmp_path / "out"),
            "--format",
            "all",
            "--dry-run",
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    suffixes = sorted(path.suffix for path in report.output_files)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS
    assert suffixes == [".json", ".md", ".txt"]
    assert report.warnings == ()
    assert report.documents[0].warnings == ()
    assert not (tmp_path / "out").exists()


def test_agent_json_when_image_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    input_image = tmp_path / "scan.png"
    input_image.write_bytes(b"not-a-real-image")

    result = runner.invoke(
        app,
        [
            "convert",
            str(input_image),
            "--out",
            str(tmp_path / "out"),
            "--dry-run",
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS
    assert report.input_files == (input_image,)


def test_agent_json_rejects_unsupported_input_file(tmp_path: Path) -> None:
    runner = CliRunner()
    input_text = tmp_path / "notes.txt"
    input_text.write_text("not a document", encoding="utf-8")

    result = runner.invoke(
        app,
        ["convert", str(input_text), "--out", str(tmp_path / "out"), "--agent"],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 1
    assert report.status == RunStatus.FAILED
    assert ".png" in report.errors[0]


def test_agent_json_when_vl_server_missing(tmp_path: Path) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "paper.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    result = runner.invoke(
        app,
        ["convert", str(input_pdf), "--out", str(tmp_path / "out"), "--agent"],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 1
    assert report.status == RunStatus.FAILED
    assert "PADDLEOCR_VL_SERVER_URL" in report.errors[0]


def test_agent_json_suppresses_benign_paddle_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "paper.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "paddlepdf.ocr_service.create_vl_pipeline",
        create_benign_pipeline,
    )
    monkeypatch.setattr(
        "paddlepdf.ocr_service.close_vl_pipeline",
        close_benign_pipeline,
    )

    result = runner.invoke(
        app,
        [
            "convert",
            str(input_pdf),
            "--out",
            str(tmp_path / "out"),
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS
    assert report.warnings == ()
    assert report.errors == ()


def test_agent_json_fails_when_paddle_emits_warning_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "paper.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "paddlepdf.ocr_service.create_vl_pipeline",
        create_warning_pipeline,
    )
    monkeypatch.setattr(
        "paddlepdf.ocr_service.close_vl_pipeline",
        close_warning_pipeline,
    )

    result = runner.invoke(
        app,
        [
            "convert",
            str(input_pdf),
            "--out",
            str(tmp_path / "out"),
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 1
    assert report.status == RunStatus.FAILED
    assert "ResourceWarning" in report.errors[0]


def test_cli_quality_profile_sets_quality_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    input_pdf = tmp_path / "paper.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    seen_options: list[ConversionOptions] = []

    def create_pipeline(options: ConversionOptions) -> FakeBenignPipeline:
        seen_options.append(options)
        return FakeBenignPipeline()

    monkeypatch.setattr("paddlepdf.ocr_service.create_vl_pipeline", create_pipeline)
    monkeypatch.setattr(
        "paddlepdf.ocr_service.close_vl_pipeline",
        close_benign_pipeline,
    )

    result = runner.invoke(
        app,
        [
            "convert",
            str(input_pdf),
            "--out",
            str(tmp_path / "out"),
            "--profile",
            "quality",
            "--agent",
        ],
    )

    report = AgentRunReport.model_validate_json(result.output)
    assert result.exit_code == 0
    assert report.status == RunStatus.SUCCESS
    assert seen_options[0].orientation_correction is True
    assert seen_options[0].document_unwarping is True
    assert seen_options[0].preserve_layout is True

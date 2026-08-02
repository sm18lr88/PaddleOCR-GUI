from collections.abc import Iterator
from pathlib import Path

import pytest

from paddlepdf import ocr_service
from paddlepdf.models import (
    ArtifactFormat,
    ConversionOptions,
    ConversionRequest,
    DeviceChoice,
    QualityProfile,
    RunStatus,
)
from paddlepdf.ocr_service import PaddleDocumentConverter


@pytest.mark.parametrize(
    ("profile", "expected_token_limit"),
    [
        (QualityProfile.FAST, 128),
        (QualityProfile.BALANCED, 256),
        (QualityProfile.QUALITY, 512),
    ],
)
def test_converter_streams_results_with_profile_token_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: QualityProfile,
    expected_token_limit: int,
) -> None:
    input_file = tmp_path / "paper.pdf"
    input_file.write_bytes(b"%PDF-1.4\n")
    events: list[str] = []

    class FakeResult:
        pass

    class FakePipeline:
        def predict_iter(
            self, input_path: str, *, max_new_tokens: int
        ) -> Iterator[FakeResult]:
            assert input_path == str(input_file)
            assert max_new_tokens == expected_token_limit
            events.append("yield-1")
            yield FakeResult()
            events.append("yield-2")
            yield FakeResult()

    def create_pipeline(options: ConversionOptions) -> FakePipeline:
        assert options.profile == profile
        return FakePipeline()

    def save_result(
        result: FakeResult,
        output_dir: Path,
        formats: tuple[ArtifactFormat, ...],
    ) -> None:
        del result, output_dir, formats
        events.append("save")

    def close_pipeline(pipeline: FakePipeline) -> None:
        del pipeline

    def no_device_warnings(options: ConversionOptions) -> tuple[str, ...]:
        del options
        return ()

    monkeypatch.setattr(ocr_service, "create_vl_pipeline", create_pipeline)
    monkeypatch.setattr(ocr_service, "save_vl_result", save_result)
    monkeypatch.setattr(ocr_service, "close_vl_pipeline", close_pipeline)
    monkeypatch.setattr(ocr_service, "device_warnings", no_device_warnings)

    report = PaddleDocumentConverter().convert(
        ConversionRequest(
            input_files=(input_file,),
            output_dir=tmp_path / "out",
            options=ConversionOptions(
                profile=profile,
                device=DeviceChoice.GPU,
            ),
        )
    )

    assert report.status == RunStatus.SUCCESS
    assert events == ["yield-1", "save", "yield-2", "save"]

from pathlib import Path

from paddlepdf.planning import plan_documents, safe_document_stem


def test_plan_documents_accepts_image_stems(tmp_path: Path) -> None:
    planned = plan_documents((Path("Scan 01.png"),), tmp_path)

    assert planned[0].safe_stem == "Scan-01"


def test_safe_document_stem_when_name_has_symbols() -> None:
    raw_path = Path("quarterly report (final!) 🌊.pdf")

    result = safe_document_stem(raw_path)

    assert result == "quarterly-report-final"


def test_plan_documents_when_duplicate_names() -> None:
    output_dir = Path("out")
    input_files = (Path("a/report.pdf"), Path("b/report.pdf"))

    result = plan_documents(input_files, output_dir)

    assert [document.safe_stem for document in result] == ["report", "report-2"]
    assert [document.output_dir for document in result] == [
        output_dir / "report",
        output_dir / "report-2",
    ]

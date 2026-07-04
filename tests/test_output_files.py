from pathlib import Path

from paddlepdf.models import ConversionOptions, OutputFormat, PlannedDocument
from paddlepdf.output_files import collect_output_files


def test_collect_output_files_includes_markdown_assets(tmp_path: Path) -> None:
    document = PlannedDocument(
        input_file=Path("paper.pdf"), output_dir=tmp_path, safe_stem="paper"
    )
    markdown = tmp_path / "paper_0.md"
    image = tmp_path / "paper_0_img_0.png"
    markdown.write_text("![figure](paper_0_img_0.png)", encoding="utf-8")
    image.write_bytes(b"image")

    output_files = collect_output_files(
        document, ConversionOptions(output_format=OutputFormat.MARKDOWN), frozenset()
    )

    assert output_files == (markdown, image)

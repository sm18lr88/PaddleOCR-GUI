from pathlib import Path

from paddlepdf.user_paths import user_path


def test_user_path_accepts_quoted_escaped_windows_path(tmp_path: Path) -> None:
    input_pdf = tmp_path / "1.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    escaped_path = str(input_pdf).replace("\\", "\\\\")

    parsed = user_path(f'"{escaped_path}"')

    assert parsed == input_pdf.resolve()


def test_user_path_accepts_file_uri(tmp_path: Path) -> None:
    input_pdf = tmp_path / "1.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    parsed = user_path(input_pdf.as_uri())

    assert parsed == input_pdf.resolve()

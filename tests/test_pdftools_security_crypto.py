import hashlib
from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest

from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.security import TOOLS

type MakePdf = Callable[..., Path]

SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in TOOLS}
OPEN_KEY = "u1"
READER_KEY = "reader"


def test_lane_registers_exactly_the_paperpilot_names() -> None:
    assert sorted(SPECS) == [
        "document_pii_scan",
        "pdf_change_permissions",
        "pdf_decrypt",
        "pdf_encrypt",
        "pdf_hash",
        "pdf_redact",
        "pdf_sanitize",
    ]


def test_encrypt_requires_password_with_aes256(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "locked.pdf"
    result = run_tool(
        SPECS["pdf_encrypt"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "user_password": OPEN_KEY,
        },
    )
    assert result.status == "success", result.errors
    assert result.output_files == (str(out),)
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(out)
    with pikepdf.open(out, password=OPEN_KEY) as pdf:
        assert pdf.is_encrypted
        assert pdf.encryption.R == 6
        assert pdf.encryption.bits == 256
        assert len(pdf.pages) == 3
    assert "Page 2" in page_texts(out, password=OPEN_KEY)[1]


def test_decrypt_removes_encryption(make_pdf: MakePdf, tmp_path: Path) -> None:
    locked = tmp_path / "locked.pdf"
    with pikepdf.open(make_pdf()) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(user="pw", owner="own"))
    out = tmp_path / "open.pdf"
    result = run_tool(
        SPECS["pdf_decrypt"],
        {"input_file": str(locked), "output_file": str(out), "password": "own"},
    )
    assert result.status == "success", result.errors
    assert result.data == {"was_encrypted": True}
    with pikepdf.open(out) as pdf:
        assert not pdf.is_encrypted
    assert "Page 1" in page_texts(out)[0]


def test_decrypt_with_wrong_password_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    locked = tmp_path / "locked.pdf"
    with pikepdf.open(make_pdf()) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(user="pw", owner="own"))
    out = tmp_path / "open.pdf"
    result = run_tool(
        SPECS["pdf_decrypt"],
        {"input_file": str(locked), "output_file": str(out), "password": "nope"},
    )
    assert result.status == "failed"
    assert result.errors
    assert result.errors[0]
    assert not out.exists()


def test_change_permissions_restricts_flags(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "restricted.pdf"
    result = run_tool(
        SPECS["pdf_change_permissions"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "allow_printing": False,
            "allow_copying": False,
        },
    )
    assert result.status == "success", result.errors
    assert isinstance(result.data, dict)
    owner = result.data["generated_owner_password"]
    assert isinstance(owner, str)
    assert owner
    assert result.warnings
    with pikepdf.open(out) as pdf:
        assert pdf.is_encrypted
        assert not pdf.owner_password_matched
        assert not pdf.allow.print_highres
        assert not pdf.allow.print_lowres
        assert not pdf.allow.extract
        assert pdf.allow.modify_form
        assert pdf.allow.modify_other
    with pikepdf.open(out, password=owner) as pdf:
        assert pdf.owner_password_matched


def test_change_permissions_with_user_password(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "restricted.pdf"
    result = run_tool(
        SPECS["pdf_change_permissions"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "allow_modifying": False,
            "user_password": READER_KEY,
            "owner_password": "boss",
        },
    )
    assert result.status == "success", result.errors
    assert isinstance(result.data, dict)
    assert "generated_owner_password" not in result.data
    with pikepdf.open(out, password=READER_KEY) as pdf:
        assert not pdf.allow.modify_other
        assert not pdf.allow.modify_assembly
        assert pdf.allow.print_highres


def test_hash_matches_file_bytes(make_pdf: MakePdf) -> None:
    source = make_pdf()
    payload = source.read_bytes()
    result = run_tool(
        SPECS["pdf_hash"],
        {"input_file": str(source), "algorithms": ["sha256", "md5"]},
    )
    assert result.status == "success", result.errors
    assert result.output_files == ()
    assert result.data == {
        "hash": hashlib.sha256(payload).hexdigest(),
        "algorithm": "sha256",
        "digests": {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
        },
        "size_bytes": len(payload),
    }


def test_hash_missing_file_fails(tmp_path: Path) -> None:
    result = run_tool(SPECS["pdf_hash"], {"input_file": str(tmp_path / "none.pdf")})
    assert result.status == "failed"
    assert result.errors

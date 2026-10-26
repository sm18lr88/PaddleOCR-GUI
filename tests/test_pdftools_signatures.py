import datetime
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pikepdf
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import JsonValue, TypeAdapter

from paddlepdf.pdftools.contract import ToolResult, ToolStatus
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.signatures import TOOLS

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}
KEY_PHRASE = "lane-key-phrase"
WRONG_PHRASE = "not-the-key-phrase"


@dataclass(frozen=True)
class Credentials:
    pkcs12_file: Path
    certificate_pem: Path


@pytest.fixture
def credentials(tmp_path: Path) -> Credentials:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Lane Test Signer")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=10))
        .sign(key, hashes.SHA256())
    )
    p12 = tmp_path / "signer.p12"
    p12.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"signer",
            key,
            certificate,
            None,
            serialization.BestAvailableEncryption(KEY_PHRASE.encode()),
        )
    )
    pem = tmp_path / "root.pem"
    pem.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return Credentials(pkcs12_file=p12, certificate_pem=pem)


def run(name: str, **params: object) -> ToolResult:
    return run_tool(SPECS[name], params)


def sign(source: Path, target: Path, creds: Credentials) -> ToolResult:
    return run(
        "pdf_sign",
        input_file=str(source),
        output_file=str(target),
        pkcs12_file=str(creds.pkcs12_file),
        pkcs12_password=KEY_PHRASE,
        reason="Approval",
        location="Lab",
    )


def only_signature(result: ToolResult) -> dict[str, JsonValue]:
    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    signatures = result.data["signatures"]
    assert isinstance(signatures, list)
    assert len(signatures) == 1
    first = signatures[0]
    assert isinstance(first, dict)
    return first


def test_sign_then_validate_is_intact_but_untrusted(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    signed = tmp_path / "signed.pdf"
    result = sign(make_pdf(), signed, credentials)
    assert result.status == ToolStatus.SUCCESS, result.errors
    assert result.output_files == (str(signed),)
    with pikepdf.open(signed) as pdf:
        assert len(pdf.pages) == 3
        sig_field = pdf.Root.AcroForm.Fields[0]
        assert str(sig_field.FT) == "/Sig"
        assert str(sig_field.V.Type) == "/Sig"
    report = run("pdf_validate_signatures", input_file=str(signed))
    info = only_signature(report)
    assert info["field_name"] == "Signature1"
    assert info["intact"] is True
    assert info["cryptographically_valid"] is True
    assert info["covers_entire_file"] is True
    assert info["trusted"] is False
    assert info["is_valid"] is True
    assert "Lane Test Signer" in str(info["signer_subject"])
    assert info["signing_time"]
    assert any("trust_roots" in warning for warning in report.warnings)


def test_validate_with_trust_roots_and_json_output(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    source = make_pdf()
    signed = tmp_path / "signed.pdf"
    sign(source, signed, credentials)
    report_file = tmp_path / "report.json"
    report = run(
        "pdf_validate_signatures",
        input_file=str(signed),
        output_file=str(report_file),
        trust_roots=[str(credentials.certificate_pem)],
        baseline_file=str(source),
    )
    info = only_signature(report)
    assert info["trusted"] is True
    assert report.warnings == ()
    assert report.output_files == (str(report_file),)
    written = TypeAdapter(dict[str, JsonValue]).validate_json(
        report_file.read_text(encoding="utf-8")
    )
    baseline = written["baseline_report"]
    assert isinstance(baseline, dict)
    assert written["all_trusted"] is True
    assert baseline["verdict"] == "UNTOUCHED_JUST_SIGNED"


def test_appended_bytes_are_reported(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    signed = tmp_path / "signed.pdf"
    sign(make_pdf(), signed, credentials)
    tampered = tmp_path / "appended.pdf"
    tampered.write_bytes(signed.read_bytes() + b"\n% appended after signing\n")
    report = run("pdf_validate_signatures", input_file=str(tampered))
    info = only_signature(report)
    assert info["covers_entire_file"] is False
    assert info["is_valid"] is False
    assert info["is_tampered"] is True
    assert info["problems"]
    assert isinstance(report.data, dict)
    assert report.data["all_valid"] is False


def test_modified_signed_bytes_break_integrity(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    signed = tmp_path / "signed.pdf"
    sign(make_pdf(), signed, credentials)
    original = signed.read_bytes()
    assert b"ReportLab Generated" in original
    tampered = tmp_path / "modified.pdf"
    tampered.write_bytes(
        original.replace(b"ReportLab Generated", b"ReportLab Xenerated", 1)
    )
    info = only_signature(run("pdf_validate_signatures", input_file=str(tampered)))
    assert info["intact"] is False
    assert info["is_tampered"] is True
    assert info["is_valid"] is False


def test_self_signed_visible_signature(make_pdf: MakePdf, tmp_path: Path) -> None:
    signed = tmp_path / "visible.pdf"
    result = run(
        "pdf_sign",
        input_file=str(make_pdf()),
        output_file=str(signed),
        self_signed=True,
        signer_name="Throwaway",
        field_name="Approval",
        visible_box=(72, 72, 272, 132),
        page=2,
    )
    assert result.status == ToolStatus.SUCCESS, result.errors
    assert any("self-signed" in warning for warning in result.warnings)
    with pikepdf.open(signed) as pdf:
        widgets = pdf.pages[1].obj.Annots
        assert len(widgets) == 1
        assert [float(value) for value in widgets[0].Rect] == [72, 72, 272, 132]
        assert "/Annots" not in pdf.pages[0].obj
    info = only_signature(run("pdf_validate_signatures", input_file=str(signed)))
    assert info["field_name"] == "Approval"
    assert info["is_valid"] is True
    assert "Throwaway" in str(info["signer_subject"])


def test_remove_signatures_strips_fields(make_pdf: MakePdf, tmp_path: Path) -> None:
    signed = tmp_path / "signed.pdf"
    run(
        "pdf_sign",
        input_file=str(make_pdf()),
        output_file=str(signed),
        self_signed=True,
        visible_box=(50, 50, 150, 100),
    )
    stripped = tmp_path / "stripped.pdf"
    result = run(
        "pdf_remove_signatures", input_file=str(signed), output_file=str(stripped)
    )
    assert result.status == ToolStatus.SUCCESS, result.errors
    assert result.data == {"signatures_removed": 1, "fields_removed": 1}
    with pikepdf.open(stripped) as pdf:
        assert "/AcroForm" not in pdf.Root
        assert "/Annots" not in pdf.pages[0].obj
    assert page_texts(stripped)[0].strip().startswith("Page 1")
    report = run("pdf_validate_signatures", input_file=str(stripped))
    assert isinstance(report.data, dict)
    assert report.data["total_signatures"] == 0


def test_remove_values_only_keeps_empty_field(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    signed = tmp_path / "signed.pdf"
    sign(make_pdf(), signed, credentials)
    stripped = tmp_path / "cleared.pdf"
    result = run(
        "pdf_remove_signatures",
        input_file=str(signed),
        output_file=str(stripped),
        remove_empty_signature_fields=False,
    )
    assert result.data == {"signatures_removed": 1, "fields_removed": 0}
    with pikepdf.open(stripped) as pdf:
        sig_field = pdf.Root.AcroForm.Fields[0]
        assert str(sig_field.FT) == "/Sig"
        assert "/V" not in sig_field


def test_sign_failures_are_reported(
    make_pdf: MakePdf, tmp_path: Path, credentials: Credentials
) -> None:
    source = make_pdf()
    missing_cert = run(
        "pdf_sign", input_file=str(source), output_file=str(tmp_path / "a.pdf")
    )
    assert missing_cert.status == ToolStatus.FAILED
    assert missing_cert.errors
    assert "pkcs12_file" in missing_cert.errors[0]
    wrong_password = run(
        "pdf_sign",
        input_file=str(source),
        output_file=str(tmp_path / "b.pdf"),
        pkcs12_file=str(credentials.pkcs12_file),
        pkcs12_password=WRONG_PHRASE,
    )
    assert wrong_password.status == ToolStatus.FAILED
    assert wrong_password.errors
    assert not (tmp_path / "b.pdf").exists()

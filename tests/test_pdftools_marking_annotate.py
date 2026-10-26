from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pikepdf
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pyhanko import keys as hanko_keys
from pyhanko.sign.timestamps import DummyTimeStamper

from paddlepdf.pdftools.contract import ToolStatus
from paddlepdf.pdftools.marking import TOOLS
from paddlepdf.pdftools.marking.timestamp import apply_timestamp
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

ANNOTATE = next(spec for spec in TOOLS if spec.name == "pdf_annotate")
TIMESTAMP = next(spec for spec in TOOLS if spec.name == "pdf_timestamp")


def test_annotate_writes_real_annotation_dictionaries(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    target = tmp_path / "annotated.pdf"
    result = run_tool(
        ANNOTATE,
        {
            "input_file": str(make_pdf()),
            "output_file": str(target),
            "annotations": [
                {
                    "id": "h1",
                    "type": "highlight",
                    "page": 1,
                    "x": 10,
                    "y": 20,
                    "w": 50,
                    "h": 12,
                    "color": "#ff0000",
                },
                {
                    "type": "note",
                    "page": 1,
                    "x": 200,
                    "y": 300,
                    "content": "check this",
                },
                {
                    "type": "pen",
                    "page": 3,
                    "x": 5,
                    "y": 5,
                    "points": [[5, 5], [30, 40]],
                },
                {"type": "strikethrough", "page": 2, "x": 1, "y": 2},
                {"type": "underline", "page": 2, "x": 1, "y": 2},
            ],
        },
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.data == {"annotations_added": 5}
    with pikepdf.open(target) as pdf:
        first = list(pdf.pages[0].Annots)
        assert [str(a.Subtype) for a in first] == ["/Highlight", "/Text"]
        highlight = first[0]
        assert [float(v) for v in highlight.Rect] == [10, 20, 60, 32]
        assert [float(v) for v in highlight.C] == [1, 0, 0]
        assert len(highlight.QuadPoints) == 8
        assert str(highlight.NM) == "h1"
        assert str(first[1].Contents) == "check this"
        ink = pdf.pages[2].Annots[0]
        assert str(ink.Subtype) == "/Ink"
        assert [float(v) for v in ink.InkList[0]] == [5, 5, 30, 40]
        assert [str(a.Subtype) for a in pdf.pages[1].Annots] == [
            "/StrikeOut",
            "/Underline",
        ]


def test_annotate_rejects_out_of_range_page_and_bad_color(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=1)
    for annotation in (
        {"type": "highlight", "page": 2, "x": 0, "y": 0},
        {"type": "highlight", "page": 1, "x": 0, "y": 0, "color": "nope"},
        {"type": "squiggle", "page": 1, "x": 0, "y": 0},
    ):
        result = run_tool(
            ANNOTATE,
            {
                "input_file": str(source),
                "output_file": str(tmp_path / "o.pdf"),
                "annotations": [annotation],
            },
        )
        assert result.status is ToolStatus.FAILED
        assert result.errors


def _dummy_timestamper(directory: Path) -> DummyTimeStamper:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test tsa")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    cert_file = directory / "tsa_cert.pem"
    key_file = directory / "tsa_key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    load_cert = cast("Callable[[str], object]", hanko_keys.load_cert_from_pemder)
    load_key = cast(
        "Callable[[str, bytes | None], object]", hanko_keys.load_private_key_from_pemder
    )
    build = cast("Callable[..., DummyTimeStamper]", DummyTimeStamper)
    return build(
        tsa_cert=load_cert(str(cert_file)), tsa_key=load_key(str(key_file), None)
    )


def test_apply_timestamp_appends_document_timestamp(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf()
    target = tmp_path / "stamped.pdf"
    apply_timestamp(source, target, _dummy_timestamper(tmp_path), None)
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 3
        fields = pdf.Root.AcroForm.Fields
        timestamp = fields[0].V
        assert str(timestamp.Type) == "/DocTimeStamp"
        assert str(timestamp.SubFilter) == "/ETSI.RFC3161"


def test_timestamp_unreachable_tsa_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    target = tmp_path / "o.pdf"
    result = run_tool(
        TIMESTAMP,
        {
            "input_file": str(make_pdf()),
            "output_file": str(target),
            "tsa_url": "http://127.0.0.1:9/tsa",
            "timeout_seconds": 2,
        },
    )
    assert result.status is ToolStatus.FAILED
    assert result.errors
    assert not target.exists()

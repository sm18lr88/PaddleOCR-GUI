"""pdf_validate_signatures: cryptographic, coverage, trust, and baseline checks."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, cast

import pikepdf
from pydantic import Field, JsonValue
from pyhanko import keys
from pyhanko.pdf_utils.crypt import AuthStatus
from pyhanko.pdf_utils.misc import PdfError as HankoPdfError
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko_certvalidator import ValidationContext

from paddlepdf.pdftools.common import input_path, open_pdf, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.signatures.inspect_sig import inspect_signature

if TYPE_CHECKING:
    from pyhanko_certvalidator.registry import TrustRootList

_CERT_SUFFIXES: Final = (".pem", ".crt", ".cer", ".der")


def pdf_validate_signatures(
    input_file: Annotated[str, Field(description="Signed PDF to validate.")],
    output_file: Annotated[
        str | None,
        Field(description="Optional .json path to also write the report to."),
    ] = None,
    trust_roots: Annotated[
        list[str] | None,
        Field(
            description=(
                "PEM/DER CA certificates to trust; without them every "
                "signer is reported untrusted."
            )
        ),
    ] = None,
    baseline_file: Annotated[
        str | None,
        Field(
            description=(
                "Original unsigned PDF; pages are compared to detect "
                "content altered before signing."
            )
        ),
    ] = None,
    password: Annotated[
        str | None, Field(description="Password of an encrypted input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source) if output_file else None
    context = _validation_context(trust_roots or [])
    with source.open("rb") as stream:
        try:
            reader = PdfFileReader(stream, strict=False)
            _unlock(reader, password, source)
            revisions = reader.xrefs.total_revisions
            signatures = [
                inspect_signature(signature, context, revisions)
                for signature in reader.embedded_signatures
            ]
        except HankoPdfError as error:
            msg = f"Cannot read signatures from {source}: {error}"
            raise PdfToolError(msg) from error
    report: dict[str, JsonValue] = {
        "total_signatures": len(signatures),
        "valid_signatures": sum(1 for item in signatures if item["is_valid"]),
        "all_valid": all(item["is_valid"] for item in signatures),
        "all_trusted": bool(signatures) and all(item["trusted"] for item in signatures),
        "signatures": list[JsonValue](signatures),
    }
    if baseline_file:
        report["baseline_report"] = _baseline_report(
            input_path(baseline_file), source, password
        )
    warnings = _warnings(signatures, trusting=bool(trust_roots))
    outputs: tuple[str, ...] = ()
    if target is not None:
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        outputs = (str(target),)
    return ToolOutcome(output_files=outputs, data=report, warnings=warnings)


def _validation_context(paths: list[str]) -> ValidationContext:
    files = [str(input_path(path, suffixes=_CERT_SUFFIXES)) for path in paths]
    try:
        roots = list(cast("TrustRootList", keys.load_certs_from_pemder(files)))
    except ValueError as error:
        msg = f"Cannot load trust root certificates: {error}"
        raise PdfToolError(msg) from error
    return ValidationContext(trust_roots=roots, allow_fetching=False)


def _unlock(reader: PdfFileReader, password: str | None, path: Path) -> None:
    if not reader.encrypted:
        return
    if reader.decrypt(password or "").status == AuthStatus.FAILED:
        msg = f"Wrong or missing password for {path}"
        raise PdfToolError(msg)


def _warnings(
    signatures: list[dict[str, JsonValue]], *, trusting: bool
) -> tuple[str, ...]:
    if not signatures:
        return ("No digital signatures found in the document",)
    if all(item["trusted"] for item in signatures):
        return ()
    if trusting:
        return ("Some signers do not chain to the given trust_roots",)
    return ("No trust_roots given: signer identities are reported untrusted",)


def _baseline_report(
    baseline: Path, signed: Path, password: str | None
) -> dict[str, JsonValue]:
    with open_pdf(baseline) as original, open_pdf(signed, password) as current:
        before = [_page_content(page) for page in original.pages]
        after = [_page_content(page) for page in current.pages]
    summary: list[JsonValue] = []
    old, new = len(before), len(after)
    if old != new:
        summary.append(f"Page count mismatch: baseline {old}, signed document {new}")
    altered: list[JsonValue] = [
        number
        for number, (old, new) in enumerate(zip(before, after, strict=False), start=1)
        if old != new
    ]
    summary.extend(
        f"Page {number}: content stream was altered prior to signing"
        for number in altered
    )
    match = not summary
    return {
        "baseline_checked": True,
        "baseline_match": match,
        "verdict": (
            "UNTOUCHED_JUST_SIGNED" if match else "CONTENT_ALTERED_PRIOR_TO_SIGNATURE"
        ),
        "altered_pages": altered,
        "diff_summary": summary,
    }


def _page_content(page: pikepdf.Page) -> bytes:
    contents = page.obj.get("/Contents")
    if isinstance(contents, pikepdf.Stream):
        return contents.read_bytes()
    if isinstance(contents, pikepdf.Array):
        return b"".join(
            item.read_bytes() for item in contents if isinstance(item, pikepdf.Stream)
        )
    return b""

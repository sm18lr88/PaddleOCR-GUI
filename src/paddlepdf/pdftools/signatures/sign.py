"""pdf_sign: apply a real PAdES/CMS digital signature as an incremental update."""

from io import BytesIO
from pathlib import Path
from typing import Annotated, Final, cast

from pydantic import Field
from pyhanko.pdf_utils.crypt import AuthStatus
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.misc import PdfError as HankoPdfError
from pyhanko.sign import fields, signers
from pyhanko.sign.general import SigningError
from pyhanko.sign.signers import SimpleSigner

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.signatures.credentials import (
    load_pkcs12_signer,
    self_signed_signer,
)

_SELF_SIGNED_WARNING: Final = (
    "Signed with a throwaway self-signed certificate: integrity can be verified, "
    "but no viewer will trust the signer identity."
)


def pdf_sign(
    input_file: Annotated[str, Field(description="PDF to sign.")],
    output_file: Annotated[str, Field(description="Path for the signed PDF.")],
    pkcs12_file: Annotated[
        str | None,
        Field(description="PKCS#12 (.p12/.pfx) file with the signing key and cert."),
    ] = None,
    pkcs12_password: Annotated[
        str | None, Field(description="Password protecting the PKCS#12 file.")
    ] = None,
    self_signed: Annotated[
        bool,
        Field(
            description=(
                "Sign with a generated throwaway self-signed certificate "
                "instead of pkcs12_file (untrusted; for testing/integrity only)."
            )
        ),
    ] = False,
    field_name: Annotated[
        str, Field(description="Signature field to fill or create.")
    ] = "Signature1",
    signer_name: Annotated[
        str | None,
        Field(
            description="Signer name recorded in the signature (and self-signed CN)."
        ),
    ] = None,
    reason: Annotated[str | None, Field(description="Reason for signing.")] = None,
    location: Annotated[str | None, Field(description="Signing location.")] = None,
    contact_info: Annotated[
        str | None, Field(description="Signer contact information.")
    ] = None,
    visible_box: Annotated[
        tuple[float, float, float, float] | None,
        Field(
            description=(
                "Visible signature rectangle (x1, y1, x2, y2) in PDF points; "
                "omit for an invisible signature."
            )
        ),
    ] = None,
    page: Annotated[
        int, Field(description="1-based page for a visible signature.", ge=1)
    ] = 1,
    password: Annotated[
        str | None, Field(description="Password of an encrypted input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    warnings: list[str] = []
    signer = _choose_signer(pkcs12_file, pkcs12_password, self_signed, signer_name)
    if self_signed:
        warnings.append(_SELF_SIGNED_WARNING)
    metadata = signers.PdfSignatureMetadata(
        field_name=field_name,
        md_algorithm="sha256",
        reason=reason,
        location=location,
        contact_info=contact_info,
        name=signer_name,
    )
    field_spec = _field_spec(field_name, visible_box, page)
    with source.open("rb") as stream:
        try:
            writer = IncrementalPdfFileWriter(stream, strict=False)
            _unlock(writer, password, source)
            _check_page(writer, page, visible_box)
            signed = BytesIO()
            signers.sign_pdf(
                writer,
                metadata,
                signer=signer,
                new_field_spec=field_spec,
                output=signed,
            )
        except (HankoPdfError, SigningError) as error:
            msg = f"Could not sign {source}: {error}"
            raise PdfToolError(msg) from error
        target.write_bytes(signed.getvalue())
    return ToolOutcome(
        output_files=(str(target),),
        data={
            "field_name": field_name,
            "visible": visible_box is not None,
            "self_signed": self_signed,
            "signer": _subject(signer),
        },
        warnings=tuple(warnings),
    )


def _choose_signer(
    pkcs12_file: str | None,
    pkcs12_password: str | None,
    self_signed: bool,
    signer_name: str | None,
) -> SimpleSigner:
    if self_signed and pkcs12_file:
        msg = "Pass either pkcs12_file or self_signed=true, not both"
        raise PdfToolError(msg)
    if self_signed:
        return self_signed_signer(signer_name or "PaddlePDF Self-Signed")
    if not pkcs12_file:
        msg = (
            "A signing certificate is required: pass pkcs12_file (+ pkcs12_password) "
            "or self_signed=true for an untrusted test signature"
        )
        raise PdfToolError(msg)
    certificate = input_path(pkcs12_file, suffixes=(".p12", ".pfx"))
    return load_pkcs12_signer(certificate, pkcs12_password)


def _subject(signer: SimpleSigner) -> str:
    certificate = signer.signing_cert
    if certificate is None:
        return ""
    return cast("str", certificate.subject.human_friendly)


def _field_spec(
    field_name: str, visible_box: tuple[float, float, float, float] | None, page: int
) -> fields.SigFieldSpec | None:
    if visible_box is None:
        return None
    x1, y1, x2, y2 = (round(value) for value in visible_box)
    if x2 <= x1 or y2 <= y1:
        msg = "visible_box needs x2 > x1 and y2 > y1"
        raise PdfToolError(msg)
    return fields.SigFieldSpec(
        sig_field_name=field_name, on_page=page - 1, box=(x1, y1, x2, y2)
    )


def _unlock(writer: IncrementalPdfFileWriter, password: str | None, path: Path) -> None:
    if not writer.prev.encrypted:
        return
    result = writer.encrypt(password or "")
    if result.status == AuthStatus.FAILED:
        msg = f"Wrong or missing password for {path}"
        raise PdfToolError(msg)


def _check_page(
    writer: IncrementalPdfFileWriter,
    page: int,
    visible_box: tuple[float, float, float, float] | None,
) -> None:
    count = cast("object", writer.root["/Pages"]["/Count"])
    pages = count if isinstance(count, int) else 0
    if visible_box is not None and page > pages:
        msg = f"Page {page} is outside the document (1-{pages})"
        raise PdfToolError(msg)

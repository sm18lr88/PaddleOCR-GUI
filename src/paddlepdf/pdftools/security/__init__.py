"""Security tools: encryption, permissions, redaction, sanitizing, PII scan, hashing."""

from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.security.encryption import (
    pdf_change_permissions,
    pdf_decrypt,
    pdf_encrypt,
)
from paddlepdf.pdftools.security.hashing import pdf_hash
from paddlepdf.pdftools.security.pii import document_pii_scan
from paddlepdf.pdftools.security.redaction import pdf_redact
from paddlepdf.pdftools.security.sanitize import pdf_sanitize

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="pdf_encrypt",
        description=(
            "Encrypt a PDF with AES-256 so user_password is needed to open it; "
            "owner_password defaults to user_password. Writes output_file."
        ),
        handler=pdf_encrypt,
    ),
    ToolSpec(
        name="pdf_decrypt",
        description=(
            "Remove encryption from a PDF using its user or owner password and "
            "write an unencrypted output_file."
        ),
        handler=pdf_decrypt,
    ),
    ToolSpec(
        name="pdf_change_permissions",
        description=(
            "Re-encrypt a PDF (AES-256) with allow_printing/copying/modifying/"
            "annotations/form_filling/accessibility flags; omitted flags stay allowed."
        ),
        handler=pdf_change_permissions,
    ),
    ToolSpec(
        name="pdf_redact",
        description=(
            "Truly redact search_text matches and/or explicit page regions: affected "
            "pages are rebuilt as images with black boxes, so the text is gone."
        ),
        handler=pdf_redact,
    ),
    ToolSpec(
        name="pdf_sanitize",
        description=(
            "Strip metadata, JavaScript/auto actions, external (Launch/URI) actions, "
            "attachments, thumbnails, and private data; data lists what was removed."
        ),
        handler=pdf_sanitize,
    ),
    ToolSpec(
        name="document_pii_scan",
        description=(
            "Scan PDF text for SSNs, credit cards, emails, phones, and IBANs; data "
            "holds masked findings per page, optionally saved as JSON to output_file."
        ),
        handler=document_pii_scan,
    ),
    ToolSpec(
        name="pdf_hash",
        description=(
            "Compute file integrity digests (SHA-256 by default) of a PDF; data.hash "
            "holds the first algorithm's hex digest."
        ),
        handler=pdf_hash,
    ),
)

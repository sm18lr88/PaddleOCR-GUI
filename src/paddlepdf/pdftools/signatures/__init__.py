from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.signatures.remove import pdf_remove_signatures
from paddlepdf.pdftools.signatures.sign import pdf_sign
from paddlepdf.pdftools.signatures.validate import pdf_validate_signatures

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="pdf_sign",
        description=(
            "Digitally sign a PDF (CMS/PAdES, incremental update) with a PKCS#12 "
            "pkcs12_file + pkcs12_password, or self_signed=true for an untrusted test "
            "certificate; optional field_name, reason, location, visible_box/page. "
            "Writes the signed PDF to output_file."
        ),
        handler=pdf_sign,
    ),
    ToolSpec(
        name="pdf_validate_signatures",
        description=(
            "Verify every digital signature in input_file: integrity, cryptographic "
            "validity, byte coverage, later modifications, and trust against optional "
            "trust_roots PEM files; optional baseline_file compares pages to the "
            "unsigned original. Returns the report in data (and output_file JSON)."
        ),
        handler=pdf_validate_signatures,
    ),
    ToolSpec(
        name="pdf_remove_signatures",
        description=(
            "Strip digital signatures from input_file: signature values, signature "
            "fields and widgets (unless remove_empty_signature_fields=false), "
            "SigFlags, and DocMDP/DSS locks. Writes output_file and returns the "
            "removed counts."
        ),
        handler=pdf_remove_signatures,
    ),
)

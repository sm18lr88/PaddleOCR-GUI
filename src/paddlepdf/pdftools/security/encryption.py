"""Password encryption, decryption, and permission changes (AES-256, revision 6)."""

import secrets
from typing import Annotated

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.security._params import InputFile, InputPassword, OutputFile

_REVISION = 6
_ENCRYPTION_DATA: dict[str, JsonValue] = {"algorithm": "AES-256", "revision": _REVISION}

Allow = Annotated[
    bool | None,
    Field(description="Allow this action; omitted means allowed."),
]


def _permissions_data(allow: pikepdf.Permissions) -> dict[str, JsonValue]:
    return {
        "printing": allow.print_lowres and allow.print_highres,
        "copying": allow.extract,
        "modifying": allow.modify_other and allow.modify_assembly,
        "annotations": allow.modify_annotation,
        "form_filling": allow.modify_form,
        "accessibility": allow.accessibility,
    }


def _write_encrypted(
    source_file: str,
    output_file: str,
    password: str | None,
    encryption: pikepdf.Encryption,
) -> str:
    source = input_path(source_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        pdf.save(target, encryption=encryption)
    return str(target)


def pdf_encrypt(
    input_file: InputFile,
    output_file: OutputFile,
    user_password: Annotated[
        str, Field(description="Password required to open the output PDF.")
    ],
    owner_password: Annotated[
        str | None,
        Field(description="Owner password; defaults to user_password."),
    ] = None,
    password: InputPassword = None,
) -> ToolOutcome:
    if not user_password and not owner_password:
        msg = "Provide a non-empty user_password or owner_password to encrypt"
        raise PdfToolError(msg)
    allow = pikepdf.Permissions(modify_assembly=True)
    encryption = pikepdf.Encryption(
        user=user_password,
        owner=owner_password or user_password,
        R=_REVISION,
        aes=True,
        allow=allow,
    )
    written = _write_encrypted(input_file, output_file, password, encryption)
    data: dict[str, JsonValue] = {
        **_ENCRYPTION_DATA,
        "permissions": _permissions_data(allow),
    }
    return ToolOutcome(output_files=(written,), data=data)


def pdf_decrypt(
    input_file: InputFile,
    output_file: OutputFile,
    password: Annotated[
        str | None,
        Field(description="User or owner password of the encrypted input PDF."),
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        was_encrypted = pdf.is_encrypted
        written = save_pdf(pdf, target)
    warnings = () if was_encrypted else ("Input PDF was not encrypted; wrote a copy",)
    return ToolOutcome(
        output_files=(written,),
        data={"was_encrypted": was_encrypted},
        warnings=warnings,
    )


def pdf_change_permissions(
    input_file: InputFile,
    output_file: OutputFile,
    allow_printing: Allow = None,
    allow_copying: Allow = None,
    allow_modifying: Allow = None,
    allow_annotations: Allow = None,
    allow_form_filling: Allow = None,
    allow_accessibility: Allow = None,
    user_password: Annotated[
        str | None,
        Field(description="Password required to open the output; omit for none."),
    ] = None,
    owner_password: Annotated[
        str | None,
        Field(
            description=(
                "Password that lifts the restrictions; defaults to user_password, "
                "else a random one returned in data.generated_owner_password."
            )
        ),
    ] = None,
    password: InputPassword = None,
) -> ToolOutcome:
    allow = pikepdf.Permissions(
        accessibility=allow_accessibility is not False,
        extract=allow_copying is not False,
        modify_annotation=allow_annotations is not False,
        modify_assembly=allow_modifying is not False,
        modify_form=allow_form_filling is not False,
        modify_other=allow_modifying is not False,
        print_lowres=allow_printing is not False,
        print_highres=allow_printing is not False,
    )
    owner = owner_password or user_password or secrets.token_urlsafe(24)
    encryption = pikepdf.Encryption(
        user=user_password or "", owner=owner, R=_REVISION, aes=True, allow=allow
    )
    written = _write_encrypted(input_file, output_file, password, encryption)
    data: dict[str, JsonValue] = {
        **_ENCRYPTION_DATA,
        "permissions": _permissions_data(allow),
    }
    warnings: tuple[str, ...] = ()
    if not (owner_password or user_password):
        data["generated_owner_password"] = owner
        warnings = (
            "Generated an owner password (data.generated_owner_password); keep it",
        )
    return ToolOutcome(output_files=(written,), data=data, warnings=warnings)

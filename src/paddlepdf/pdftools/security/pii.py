"""Regex PII scan over pdfium page text, ported from PaperPilot ``pii.rs``."""

import json
import re
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Annotated, Final

from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.security._params import InputFile, InputPassword

_SSN: Final = re.compile(r"\b(\d{3})-(\d{2})-(\d{4})\b")
_CARD: Final = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_EMAIL: Final = re.compile(r"\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b")
_PHONE: Final = re.compile(
    r"\b(\+?1?[-.\s]?)?(\()?\d{3}(\))?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_IBAN: Final = re.compile(r"\b[A-Z]{2}[0-9]{2}(?:[ ]?[a-zA-Z0-9]){11,28}\b")
_CONTEXT_CHARS: Final = 20
_CARD_DIGITS: Final = range(13, 20)
_PHONE_MIN_DIGITS: Final = 10
_IBAN_MASK_MIN: Final = 8
_LUHN_FOLD: Final = 9

type _Masker = Callable[[re.Match[str]], str | None]


def _luhn(digits: str) -> bool:
    if len(digits) not in _CARD_DIGITS:
        return False
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char) * (2 if position % 2 else 1)
        total += value - _LUHN_FOLD if value > _LUHN_FOLD else value
    return total % 10 == 0


def _digits(text: str) -> str:
    return "".join(char for char in text if char.isascii() and char.isdigit())


def _mask_ssn(match: re.Match[str]) -> str:
    return f"XXX-XX-{match.group(3)}"


def _mask_card(match: re.Match[str]) -> str | None:
    digits = _digits(match.group(0))
    return f"**** **** **** {digits[-4:]}" if _luhn(digits) else None


def _mask_email(match: re.Match[str]) -> str:
    user, domain = match.group(1), match.group(2)
    masked = f"{user[0]}***{user[-1]}" if len(user) > 1 else "***"
    return f"{masked}@{domain}"


def _mask_phone(match: re.Match[str]) -> str | None:
    if _SSN.search(match.group(0)):
        return None
    digits = _digits(match.group(0))
    return f"(***) ***-{digits[-4:]}" if len(digits) >= _PHONE_MIN_DIGITS else None


def _mask_iban(match: re.Match[str]) -> str:
    value = match.group(0)
    if len(value) < _IBAN_MASK_MIN:
        return "****"
    return f"{value[:2]}** **** **** **** **{value[-4:]}"


_DETECTORS: Final[dict[str, tuple[re.Pattern[str], _Masker, float]]] = {
    "ssn": (_SSN, _mask_ssn, 0.99),
    "credit_card": (_CARD, _mask_card, 0.95),
    "email": (_EMAIL, _mask_email, 0.98),
    "phone": (_PHONE, _mask_phone, 0.85),
    "iban": (_IBAN, _mask_iban, 0.80),
}


def _context(text: str, match: re.Match[str]) -> str:
    start = max(match.start() - _CONTEXT_CHARS, 0)
    snippet = text[start : match.end() + _CONTEXT_CHARS]
    return snippet.replace("\r", " ").replace("\n", " ")


def _findings(
    texts: list[str], categories: list[str]
) -> Iterator[dict[str, JsonValue]]:
    for number, text in enumerate(texts, start=1):
        if not text.strip():
            continue
        for category in categories:
            pattern, mask, confidence = _DETECTORS[category]
            for match in pattern.finditer(text):
                masked = mask(match)
                if masked is None:
                    continue
                yield {
                    "category": category,
                    "value_masked": masked,
                    "page": number,
                    "confidence": confidence,
                    "context_snippet": _context(text, match),
                }


def document_pii_scan(
    input_file: InputFile,
    output_file: Annotated[
        str | None, Field(description="Optional path for a JSON copy of the report.")
    ] = None,
    scan_ssn: Annotated[
        bool, Field(description="Detect US social security numbers.")
    ] = True,
    scan_credit_cards: Annotated[
        bool, Field(description="Detect Luhn-valid card numbers.")
    ] = True,
    scan_emails: Annotated[bool, Field(description="Detect email addresses.")] = True,
    scan_phones: Annotated[bool, Field(description="Detect phone numbers.")] = True,
    scan_iban: Annotated[
        bool, Field(description="Detect IBAN-like account numbers.")
    ] = True,
    password: InputPassword = None,
) -> ToolOutcome:
    enabled = {
        "ssn": scan_ssn,
        "credit_card": scan_credit_cards,
        "email": scan_emails,
        "phone": scan_phones,
        "iban": scan_iban,
    }
    source = input_path(input_file)
    findings = list(
        _findings(
            page_texts(source, password), [name for name, on in enabled.items() if on]
        )
    )
    by_category = Counter(str(finding["category"]) for finding in findings)
    report: dict[str, JsonValue] = {
        "total_findings": len(findings),
        "findings_by_category": dict(by_category),
        "findings": list(findings),
    }
    outputs: tuple[str, ...] = ()
    if output_file:
        target = output_path(output_file, source)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        outputs = (str(target),)
    return ToolOutcome(output_files=outputs, data=report)

"""Signer credentials: PKCS#12 loading and throwaway self-signed certificates."""

import datetime
from pathlib import Path
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pyhanko.sign.signers import SimpleSigner

from paddlepdf.pdftools.contract import PdfToolError

_SELF_SIGNED_DAYS: Final = 30
_RSA_BITS: Final = 2048
_SELF_SIGNED_PASSPHRASE: Final = b"paddlepdf-self-signed"


def load_pkcs12_signer(path: Path, password: str | None) -> SimpleSigner:
    passphrase = password.encode() if password else None
    msg = f"Cannot open PKCS#12 file {path}: wrong password or invalid file"
    try:
        return SimpleSigner.load_pkcs12_data(
            path.read_bytes(), other_certs=[], passphrase=passphrase
        )
    except ValueError as error:
        raise PdfToolError(msg) from error


def self_signed_pkcs12(common_name: str, passphrase: bytes) -> bytes:
    """Return a PKCS#12 blob holding a fresh RSA key and self-signed certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=_RSA_BITS)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=_SELF_SIGNED_DAYS))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        common_name.encode(),
        key,
        certificate,
        None,
        serialization.BestAvailableEncryption(passphrase),
    )


def self_signed_signer(common_name: str) -> SimpleSigner:
    blob = self_signed_pkcs12(common_name, _SELF_SIGNED_PASSPHRASE)
    return SimpleSigner.load_pkcs12_data(
        blob, other_certs=[], passphrase=_SELF_SIGNED_PASSPHRASE
    )

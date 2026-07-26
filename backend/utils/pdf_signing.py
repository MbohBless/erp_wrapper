"""Cryptographic PDF signing (PAdES) for generated reports.

A self-signed signing certificate is provisioned once into the persistent
``/app/data/signing`` volume and reused. Reports are signed with an embedded
PAdES (PDF Advanced Electronic Signature), so any later tampering invalidates
the signature. The certificate is self-signed, so verifiers (e.g. Adobe Reader)
show a valid signature from an "unknown" issuer until the cert is trusted.
"""

from __future__ import annotations

import datetime as _dt
import os
import threading
from functools import lru_cache
from io import BytesIO

_SIGNING_DIR = os.environ.get("REPORT_SIGNING_DIR", "/app/data/signing")
_KEY_PATH = os.path.join(_SIGNING_DIR, "signing-key.pem")
_CERT_PATH = os.path.join(_SIGNING_DIR, "signing-cert.pem")
_lock = threading.Lock()


def _generate_credentials(org_name: str) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name[:64] or "EquiMed"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{org_name[:48] or 'EquiMed'} Reporting"),
        ]
    )
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(minutes=5))
        .not_valid_after(now + _dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,  # non-repudiation
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

    os.makedirs(_SIGNING_DIR, exist_ok=True)
    with open(_KEY_PATH, "wb") as fh:
        fh.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with open(_CERT_PATH, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))


def ensure_credentials(org_name: str = "EquiMed") -> None:
    if os.path.exists(_KEY_PATH) and os.path.exists(_CERT_PATH):
        return
    with _lock:
        if not (os.path.exists(_KEY_PATH) and os.path.exists(_CERT_PATH)):
            _generate_credentials(org_name)


@lru_cache(maxsize=1)
def _load_signer():
    from pyhanko.sign import signers

    return signers.SimpleSigner.load(
        _KEY_PATH, _CERT_PATH, ca_chain_files=(), key_passphrase=None
    )


def sign_pdf(pdf_bytes: bytes, *, reason: str, location: str, org_name: str = "EquiMed") -> bytes:
    """Return ``pdf_bytes`` with an embedded PAdES signature."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigSeedSubFilter

    ensure_credentials(org_name)
    signer = _load_signer()

    writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
    meta = signers.PdfSignatureMetadata(
        field_name="EquiMedSignature",
        reason=reason,
        location=location,
        subfilter=SigSeedSubFilter.PADES,
    )
    out = signers.sign_pdf(writer, meta, signer=signer)
    return out.getvalue()

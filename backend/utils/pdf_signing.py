"""Cryptographic PDF signing (PAdES) for generated reports.

Reports carry an embedded PAdES signature, so any later tampering invalidates
it. The certificate is self-signed, so verifiers (e.g. Adobe Reader) show a
valid signature from an "unknown" issuer until the cert is trusted.

**Signing identity is per organisation, not per process.** The signature says
who produced the document, so it has to be *that* tenant's name. Credentials
are therefore stored under a directory derived from the signing identity:

    <signing dir>/<tenant>/<slug>-<hash of org name>/{signing-key,signing-cert}.pem

Two consequences that are the point of the design rather than side effects:

* **Tenants never share a signing identity.** A single shared keypair (which is
  what this module used to do) would sign every workspace's reports with the
  first workspace's organisation name — a cross-tenant identity leak on the
  SaaS plane, and simply the wrong name on a rebranded single-tenant install.
* **Renaming the company mints a new certificate.** The old key stays on disk,
  so documents signed under the previous name still verify. Reusing the old key
  under a new name would make the signature claim something untrue.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
import threading
from functools import lru_cache
from io import BytesIO

_SIGNING_ROOT = os.environ.get("REPORT_SIGNING_DIR", "/app/data/signing")
_lock = threading.Lock()

_FALLBACK_ORG = "Reporting"


def _slug(value: str, max_len: int = 40) -> str:
    """Filesystem-safe fragment of an organisation name."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").lower()
    return (cleaned[:max_len] or "org")


def _identity_dir(org_name: str, tenant_id: str) -> str:
    """Where this (tenant, organisation) pair's keypair lives.

    The org-name hash is what makes a rename produce a fresh certificate
    instead of silently reusing one that names the old company.
    """
    digest = hashlib.sha256((org_name or _FALLBACK_ORG).encode("utf-8")).hexdigest()[:12]
    return os.path.join(_SIGNING_ROOT, _slug(tenant_id, 64), f"{_slug(org_name)}-{digest}")


def _paths(org_name: str, tenant_id: str) -> tuple[str, str]:
    directory = _identity_dir(org_name, tenant_id)
    return (
        os.path.join(directory, "signing-key.pem"),
        os.path.join(directory, "signing-cert.pem"),
    )


def signature_field_name(org_name: str) -> str:
    """Name of the signature field embedded in the PDF.

    Visible in a PDF viewer's signature panel, so it must not be a hardcoded
    product name in a white-labelled product.
    """
    base = re.sub(r"[^A-Za-z0-9]+", "", org_name or "") or "Report"
    return f"{base[:40]}Signature"


def _generate_credentials(org_name: str, key_path: str, cert_path: str) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    org = (org_name or _FALLBACK_ORG)[:64]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{org[:48]} Reporting"),
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

    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "wb") as fh:
        fh.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with open(cert_path, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))
    os.chmod(key_path, 0o600)


def ensure_credentials(org_name: str = _FALLBACK_ORG, tenant_id: str = "default") -> tuple[str, str]:
    """Return this identity's (key, cert) paths, creating them if absent."""
    key_path, cert_path = _paths(org_name, tenant_id)
    if os.path.exists(key_path) and os.path.exists(cert_path):
        return key_path, cert_path
    with _lock:
        if not (os.path.exists(key_path) and os.path.exists(cert_path)):
            _generate_credentials(org_name, key_path, cert_path)
    return key_path, cert_path


@lru_cache(maxsize=32)
def _load_signer(key_path: str, cert_path: str):
    """Cached per identity — a single-entry cache would hand one tenant's
    signer to the next request from a different tenant."""
    from pyhanko.sign import signers

    return signers.SimpleSigner.load(
        key_path, cert_path, ca_chain_files=(), key_passphrase=None
    )


def sign_pdf(
    pdf_bytes: bytes,
    *,
    reason: str,
    location: str,
    org_name: str = _FALLBACK_ORG,
    tenant_id: str = "default",
) -> bytes:
    """Return ``pdf_bytes`` with an embedded PAdES signature."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigSeedSubFilter

    key_path, cert_path = ensure_credentials(org_name, tenant_id)
    signer = _load_signer(key_path, cert_path)

    writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
    meta = signers.PdfSignatureMetadata(
        field_name=signature_field_name(org_name),
        reason=reason,
        location=location,
        subfilter=SigSeedSubFilter.PADES,
    )
    out = signers.sign_pdf(writer, meta, signer=signer)
    return out.getvalue()

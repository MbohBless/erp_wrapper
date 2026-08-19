"""Signing identity is per organisation, never shared.

The signature asserts *who produced* a document. A process-wide keypair — which
this module previously used — would sign every workspace's reports with
whichever organisation happened to generate the first PDF. On the SaaS plane
that is a cross-tenant identity leak; on a rebranded single-tenant install it
simply signs with the wrong company name.
"""

import os
import tempfile

import pytest

import utils.pdf_signing as ps


@pytest.fixture(autouse=True)
def isolated_signing_root(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(ps, "_SIGNING_ROOT", tmp)
        ps._load_signer.cache_clear()
        yield tmp
        ps._load_signer.cache_clear()


def _subject(cert_path: str) -> str:
    from cryptography import x509

    with open(cert_path, "rb") as fh:
        return x509.load_pem_x509_certificate(fh.read()).subject.rfc4514_string()


def test_certificate_carries_the_organisation_name():
    _, cert = ps.ensure_credentials("Quality Biomedicals", "default")
    assert "Quality Biomedicals" in _subject(cert)


def test_two_tenants_never_share_a_keypair():
    a_key, a_cert = ps.ensure_credentials("Quality Biomedicals", "qbm")
    b_key, b_cert = ps.ensure_credentials("Northwind Medical", "northwind")

    assert a_key != b_key and a_cert != b_cert
    assert "Quality Biomedicals" in _subject(a_cert)
    assert "Northwind Medical" in _subject(b_cert)
    # Different private keys, not just different files pointing at one identity.
    assert open(a_key).read() != open(b_key).read()


def test_same_tenant_and_name_reuses_its_keypair():
    """Signing identity must be stable, or every report looks like a new signer."""
    first = ps.ensure_credentials("Quality Biomedicals", "qbm")
    second = ps.ensure_credentials("Quality Biomedicals", "qbm")
    assert first == second


def test_renaming_the_company_mints_a_new_certificate():
    """Reusing the old key under a new name would make the signature claim
    something untrue; the old key stays so old documents still verify."""
    old_key, old_cert = ps.ensure_credentials("Old Name Ltd", "qbm")
    new_key, new_cert = ps.ensure_credentials("Quality Biomedicals", "qbm")

    assert new_cert != old_cert
    assert os.path.exists(old_cert), "documents signed under the old name must still verify"
    assert "Old Name Ltd" in _subject(old_cert)
    assert "Quality Biomedicals" in _subject(new_cert)


def test_signature_field_name_follows_the_brand():
    """Visible in a PDF viewer's signature panel — never a hardcoded product."""
    assert ps.signature_field_name("Quality Biomedicals") == "QualityBiomedicalsSignature"
    assert ps.signature_field_name("") == "ReportSignature"
    # Punctuation and spacing must not produce an invalid field name.
    assert ps.signature_field_name("Acme & Co. (Cameroon)") == "AcmeCoCameroonSignature"


def test_blank_organisation_still_produces_a_usable_identity():
    key, cert = ps.ensure_credentials("", "default")
    assert os.path.exists(key) and os.path.exists(cert)
    assert "Reporting" in _subject(cert)

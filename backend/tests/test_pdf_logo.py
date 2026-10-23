"""The branded letterhead actually reaches the page.

This is the one place the application hands untrusted bytes to an image decoder:
a tenant's logo arrives as a `data:image/...` base64 URI, and
`pdf_report._logo_reader` passes it to ReportLab's `ImageReader`, which decodes
it through Pillow. That makes Pillow's version a thing this project has to care
about — CVE-2026-112403 (JPEG decoder heap corruption) sits on this path.

It also makes an *upgrade* dangerous in a quiet way. Both halves swallow
everything:

    try:  return ImageReader(BytesIO(raw))
    except Exception:  return None          # _logo_reader

    try:  c.drawImage(logo, ...)
    except Exception:  pass                 # _draw_letterhead

So a Pillow release that ReportLab cannot drive does not raise, does not log,
and does not fail a test. It silently produces PDFs with no logo on them, and
the first report of it is a client asking why their letterhead disappeared.

These tests decode a real image rather than asserting on a string, so they fail
if the decoder stops working. Run them against any Pillow or ReportLab bump.
"""

import base64
from io import BytesIO

import pytest

from utils.pdf_report import Column, ReportDoc, render_report_pdf

PROFILE = {
    "legal_name": "Quality BioMedicals Sarl",
    "display_name": "Quality BioMedicals",
    "address": "Douala, Cameroon",
    "accent": "#2E7D32",
}

DOC = ReportDoc(
    title="Outstanding Receivables",
    subtitle="as at 23 October 2026",
    columns=[Column("Customer"), Column("Amount", align="right")],
    rows=[["CHU Yaoundé", "1,250,000"], ["Clinique du Littoral", "480,000"]],
    total_label="Total",
    total_value="1,730,000",
)


def _png_data_url(size=(64, 64), colour=(46, 125, 50)) -> str:
    """A real PNG, encoded the way branding stores one."""
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", size, colour).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _jpeg_data_url(size=(64, 64)) -> str:
    """JPEG specifically: it is a different decoder, and the one the current
    Pillow advisory concerns."""
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _image_count(pdf: bytes) -> int:
    """How many image XObjects ReportLab wrote into the document."""
    return pdf.count(b"/Subtype /Image") + pdf.count(b"/Subtype/Image")


@pytest.mark.parametrize(
    "data_url_factory, label", [(_png_data_url, "PNG"), (_jpeg_data_url, "JPEG")]
)
def test_a_logo_is_decoded_and_embedded(data_url_factory, label):
    with_logo = render_report_pdf(
        {**PROFILE, "logo_data_url": data_url_factory()}, DOC
    )
    without = render_report_pdf(PROFILE, DOC)

    assert with_logo.startswith(b"%PDF"), f"{label}: not a PDF"
    assert _image_count(without) == 0, "the control document already has an image"
    assert _image_count(with_logo) >= 1, (
        f"{label} logo never reached the page — ImageReader or Pillow refused it, "
        "and both call sites swallow the exception"
    )
    assert len(with_logo) > len(without), f"{label}: logo added no bytes"


def test_a_corrupt_logo_is_dropped_rather_than_raising():
    """The swallowing is deliberate for *bad input* — a tenant with a broken
    logo still gets their report. It is only dangerous when it hides a decoder
    that has stopped working altogether, which the test above is for."""
    junk = "data:image/png;base64," + base64.b64encode(b"not a png at all").decode()
    pdf = render_report_pdf({**PROFILE, "logo_data_url": junk}, DOC)
    assert pdf.startswith(b"%PDF")
    assert _image_count(pdf) == 0


def test_the_report_body_survives_whatever_the_logo_does():
    """A letterhead failure must never cost the figures."""
    pdf = render_report_pdf({**PROFILE, "logo_data_url": _png_data_url()}, DOC)
    assert b"Outstanding Receivables" in pdf or b"Receivables" in pdf
    assert len(pdf) > 1500

"""The ONE predefined certificate design (landscape A4).

All layout values (colours, fonts, positions) live here, so changing the look
of the certificate means editing only this file.
`draw_certificate` raises ValueError if the text cannot fit on the page.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
CENTER_X = PAGE_WIDTH / 2

NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#B8860B")
PAPER = colors.HexColor("#FFFDF5")
GREY = colors.HexColor("#555555")

TITLE_FONT = "Times-Bold"
BODY_FONT = "Times-Roman"
NAME_FONT = "Times-BoldItalic"
EVENT_FONT = "Times-Bold"

MAX_TEXT_WIDTH = PAGE_WIDTH - 200  # keeps text away from the borders
MAX_EVENT_LINES = 3


def _draw_centered(pdf: Canvas, text: str, y: float, font: str, size: float, color) -> None:
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    pdf.drawCentredString(CENTER_X, y, text)


def _draw_spaced_centered(
    pdf: Canvas, text: str, y: float, font: str, size: float, color, spacing: float
) -> None:
    """Centered text with extra space between letters (looks elegant for titles)."""
    width = stringWidth(text, font, size) + spacing * (len(text) - 1)
    text_object = pdf.beginText(CENTER_X - width / 2, y)
    text_object.setFont(font, size)
    text_object.setFillColor(color)
    text_object.setCharSpace(spacing)
    text_object.textOut(text)
    text_object.setCharSpace(0)  # reset, otherwise the spacing leaks into later text
    pdf.drawText(text_object)


def _fit_font_size(text: str, font: str, start_size: int, min_size: int) -> int:
    """Shrink the font until the text fits the available width."""
    size = start_size
    while size > min_size and stringWidth(text, font, size) > MAX_TEXT_WIDTH:
        size -= 1
    if stringWidth(text, font, size) > MAX_TEXT_WIDTH:
        raise ValueError("Recipient name is too long to fit on the certificate")
    return size


def _draw_background_and_borders(pdf: Canvas) -> None:
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(4)
    pdf.rect(25, 25, PAGE_WIDTH - 50, PAGE_HEIGHT - 50, stroke=1, fill=0)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)
    pdf.rect(38, 38, PAGE_WIDTH - 76, PAGE_HEIGHT - 76, stroke=1, fill=0)


def draw_certificate(pdf: Canvas, recipient_name: str, event_name: str, date_text: str) -> None:
    """Draw the complete certificate on the current page."""
    _draw_background_and_borders(pdf)

    _draw_spaced_centered(pdf, "CERTIFICATE", PAGE_HEIGHT - 125, TITLE_FONT, 46, NAVY, 6)
    _draw_spaced_centered(pdf, "OF COMPLETION", PAGE_HEIGHT - 160, BODY_FONT, 20, GOLD, 5)

    _draw_centered(pdf, "This is to certify that", PAGE_HEIGHT - 215, BODY_FONT, 18, GREY)

    name_size = _fit_font_size(recipient_name, NAME_FONT, 38, 14)
    _draw_centered(pdf, recipient_name, PAGE_HEIGHT - 265, NAME_FONT, name_size, NAVY)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.line(CENTER_X - 220, PAGE_HEIGHT - 278, CENTER_X + 220, PAGE_HEIGHT - 278)

    _draw_centered(pdf, "has successfully completed", PAGE_HEIGHT - 315, BODY_FONT, 18, GREY)

    event_lines = simpleSplit(event_name, EVENT_FONT, 24, MAX_TEXT_WIDTH)
    if len(event_lines) > MAX_EVENT_LINES:
        raise ValueError("Event name is too long to fit on the certificate")
    for index, line in enumerate(event_lines):
        _draw_centered(pdf, line, PAGE_HEIGHT - 355 - index * 30, EVENT_FONT, 24, NAVY)

    _draw_centered(pdf, date_text, 125, BODY_FONT, 18, NAVY)
    pdf.setStrokeColor(GREY)
    pdf.setLineWidth(0.8)
    pdf.line(CENTER_X - 70, 117, CENTER_X + 70, 117)
    _draw_centered(pdf, "Date", 102, BODY_FONT, 12, GREY)

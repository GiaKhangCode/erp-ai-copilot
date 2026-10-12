import io
import pytest
import docx

from app.rag.parser import (
    parse_document,
    parse_text,
    parse_docx,
    parse_pdf,
    normalize_text,
)


MINIMAL_VALID_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 44 >> stream
BT
/F1 12 Tf
100 100 Td
(Chinh sach bao hanh ERP) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000240 00000 n 
0000000334 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
415
%%EOF
"""


def test_normalize_text():
    raw = "  Dong 1   co    nhieu cach. \n\n\n\n\nDong 2 co tab\t\tvaf unicode \xa0 khoang trong.   "
    clean = normalize_text(raw)
    assert "Dong 1 co nhieu cach." in clean
    assert "\n\n" in clean
    assert "\n\n\n" not in clean
    assert "\xa0" not in clean


def test_parse_plain_text():
    content = b"Chinh sach giao hang ERP 2026.\nDon hang tren 5 trieu mien phi van chuyen."
    parsed = parse_document(content, "giao_hang.txt", mime_type="text/plain")

    assert parsed.filename == "giao_hang.txt"
    assert parsed.mime_type == "text/plain"
    assert parsed.total_pages == 1
    assert len(parsed.sections) == 1
    assert "5 trieu" in parsed.full_text


def test_parse_markdown_headings():
    md_content = b"""# Chinh sach chung
Noi dung gioi thieu chinh sach ban hang cong ty ERP.

## 1. Pham vi ap dung
Ap dung cho toan bo khach hang tren lanh tho Viet Nam.

## 2. Quy trinh doi tra
Khach hang duoc doi tra trong vong 7 ngay neu san pham loi.
"""
    parsed = parse_document(md_content, "policy.md", mime_type="text/markdown")

    assert parsed.filename == "policy.md"
    assert len(parsed.sections) >= 3
    assert any("Chinh sach chung" in s.text for s in parsed.sections)
    assert any("Quy trinh doi tra" in s.text for s in parsed.sections)


def test_parse_docx_with_table():
    # Build in-memory DOCX with heading, paragraph and table
    doc = docx.Document()
    doc.add_heading("Bang Gia San Pham 2026", level=1)
    doc.add_paragraph("Bang gia ap dung tu ngay 01/01/2026 cho den khi co thong bao moi.")

    table = doc.add_table(rows=3, cols=3)
    table.cell(0, 0).text = "Ma SKU"
    table.cell(0, 1).text = "Ten san pham"
    table.cell(0, 2).text = "Gia niem yet"

    table.cell(1, 0).text = "SKU-001"
    table.cell(1, 1).text = "Ban lam viec go"
    table.cell(1, 2).text = "1,500,000 VND"

    table.cell(2, 0).text = "SKU-002"
    table.cell(2, 1).text = "Ghe xoay van phong"
    table.cell(2, 2).text = "850,000 VND"

    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    parsed = parse_document(
        docx_bytes,
        "bang_gia.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert parsed.filename == "bang_gia.docx"
    assert len(parsed.sections) >= 2
    # Table should be parsed into Markdown format
    table_section = next((s for s in parsed.sections if s.section_type == "table"), None)
    assert table_section is not None
    assert "| Ma SKU | Ten san pham | Gia niem yet |" in table_section.text
    assert "| SKU-001 | Ban lam viec go | 1,500,000 VND |" in table_section.text


def test_parse_pdf():
    parsed = parse_document(MINIMAL_VALID_PDF, "quy_dinh.pdf", mime_type="application/pdf")

    assert parsed.filename == "quy_dinh.pdf"
    assert parsed.mime_type == "application/pdf"
    assert parsed.total_pages == 1
    assert len(parsed.sections) == 1
    assert parsed.sections[0].page_number == 1
    assert "Chinh sach bao hanh ERP" in parsed.sections[0].text


def test_parse_empty_or_blank():
    with pytest.raises(ValueError, match="empty"):
        parse_document(b"", "empty.txt")

    with pytest.raises(ValueError, match="No extractable text"):
        parse_document(b"   \n\n\t  ", "blank.txt")

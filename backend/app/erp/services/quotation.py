"""
Quotation PDF Generation Service using ReportLab.
Generates corporate-standard Sales Quotations (Proforma Invoice) with Vietnamese Unicode support.
"""
import io
import os
import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.erp.services.order import SalesOrderService
from app.erp.services.customer import CustomerService

# Register Unicode fonts for Vietnamese if available
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

for ttf_path, bold_path in [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]:
    if os.path.exists(ttf_path):
        try:
            pdfmetrics.registerFont(TTFont("CustomVN", ttf_path))
            FONT_REGULAR = "CustomVN"
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("CustomVN-Bold", bold_path))
                FONT_BOLD = "CustomVN-Bold"
            else:
                FONT_BOLD = "CustomVN"
            break
        except Exception:
            pass


def format_currency(amount: Optional[Decimal]) -> str:
    if amount is None:
        return "0 đ"
    return f"{int(amount):,} đ".replace(",", ".")


class QuotationService:
    @classmethod
    async def generate_pdf(
        cls,
        session: AsyncSession,
        order_id: uuid.UUID,
    ) -> bytes:
        """Sinh file PDF Báo giá kinh doanh tiêu chuẩn từ đơn hàng."""
        order = await SalesOrderService.get_order_by_id(session, order_id)
        if not order:
            raise NotFoundException("SalesOrder", str(order_id))

        customer = order.customer

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1E3A8A"), # Dark navy blue
            alignment=1, # Center
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            alignment=1,
            spaceAfter=12,
        )
        company_name_style = ParagraphStyle(
            "CompanyName",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0F172A"),
        )
        company_info_style = ParagraphStyle(
            "CompanyInfo",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#475569"),
        )
        heading_section_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#1E40AF"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "BodyTextVN",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1E293B"),
        )
        body_bold_style = ParagraphStyle(
            "BodyBoldVN",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=1,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )
        table_cell_right_style = ParagraphStyle(
            "TableCellRight",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
            alignment=2, # Right
        )
        table_cell_center_style = ParagraphStyle(
            "TableCellCenter",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
            alignment=1, # Center
        )

        story = []

        # 1. Header: Company Info & Meta
        company_col = [
            Paragraph("CÔNG TY CỔ PHẦN CÔNG NGHỆ ERP AI COPILOT", company_name_style),
            Spacer(1, 2 * mm),
            Paragraph("Địa chỉ: Tầng 12, Tòa nhà Công Nghệ Cao, Cầu Giấy, Hà Nội", company_info_style),
            Paragraph("Mã số thuế: 0109888999 | Hotline: 1900 6868", company_info_style),
            Paragraph("Email: sales@erpcopilot.vn | Website: erpcopilot.vn", company_info_style),
        ]

        meta_col = [
            Paragraph(f"<b>Số báo giá:</b> QUO-{order.order_number}", company_info_style),
            Paragraph(f"<b>Ngày lập:</b> {order.created_at.strftime('%d/%m/%Y')}", company_info_style),
            Paragraph(f"<b>Hiệu lực:</b> 15 ngày kể từ ngày lập", company_info_style),
            Paragraph(f"<b>Trạng thái:</b> {order.status.upper()}", company_info_style),
        ]

        header_table = Table(
            [[company_col, meta_col]],
            colWidths=[115 * mm, 65 * mm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)

        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=10))

        # 2. Quotation Title
        story.append(Paragraph("BÁO GIÁ KINH DOANH", title_style))
        story.append(Paragraph("(Sales Quotation & Proforma Invoice)", subtitle_style))

        # 3. Customer Info Section
        story.append(Paragraph("I. THÔNG TIN KHÁCH HÀNG & BÊN NHẬN HÀNG", heading_section_style))
        cust_phone = getattr(customer, "phone", None) or "Chưa cập nhật"
        cust_address = getattr(customer, "address", None) or "Theo hợp đồng kinh tế"
        cust_email = customer.email or "Chưa cập nhật"

        cust_info_data = [
            [
                Paragraph("<b>Tên khách hàng/Doanh nghiệp:</b>", body_style),
                Paragraph(f"<b>{customer.name}</b>", body_bold_style),
                Paragraph("<b>Mã khách hàng:</b>", body_style),
                Paragraph(customer.code, body_style),
            ],
            [
                Paragraph("<b>Địa chỉ:</b>", body_style),
                Paragraph(cust_address, body_style),
                Paragraph("<b>Số điện thoại:</b>", body_style),
                Paragraph(cust_phone, body_style),
            ],
            [
                Paragraph("<b>Email:</b>", body_style),
                Paragraph(cust_email, body_style),
                Paragraph("<b>Người liên hệ:</b>", body_style),
                Paragraph("Đại diện Mua Hàng", body_style),
            ],
        ]
        cust_table = Table(cust_info_data, colWidths=[42 * mm, 68 * mm, 32 * mm, 38 * mm])
        cust_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ]))
        story.append(cust_table)
        story.append(Spacer(1, 5 * mm))

        # 4. Itemized Quotation Table
        story.append(Paragraph("II. CHI TIẾT DANH MỤC HÀNG HÓA & ĐƠN GIÁ", heading_section_style))

        items_table_data = [
            [
                Paragraph("STT", table_header_style),
                Paragraph("Mã SKU", table_header_style),
                Paragraph("Tên hàng hóa / Quy cách", table_header_style),
                Paragraph("ĐVT", table_header_style),
                Paragraph("SL", table_header_style),
                Paragraph("Đơn giá (VNĐ)", table_header_style),
                Paragraph("Thành tiền (VNĐ)", table_header_style),
            ]
        ]

        total_qty = 0
        for idx, item in enumerate(order.items, start=1):
            sku = item.product.sku if item.product else "N/A"
            prod_name = item.product.name if item.product else "Sản phẩm"
            qty = item.quantity
            total_qty += qty
            unit_price = item.unit_price
            line_total = item.line_total

            items_table_data.append([
                Paragraph(str(idx), table_cell_center_style),
                Paragraph(sku, table_cell_style),
                Paragraph(prod_name, table_cell_style),
                Paragraph("Chiếc", table_cell_center_style),
                Paragraph(str(qty), table_cell_center_style),
                Paragraph(format_currency(unit_price), table_cell_right_style),
                Paragraph(format_currency(line_total), table_cell_right_style),
            ])

        # Summary rows
        total_amount = order.total_amount
        vat_amount = Decimal(0) # Standard pricing includes or zero-rate VAT
        grand_total = total_amount + vat_amount

        items_table_data.append([
            Paragraph("<b>TỔNG CỘNG TIỀN HÀNG:</b>", ParagraphStyle("T1", parent=body_bold_style, alignment=2)),
            "", "", "",
            Paragraph(f"<b>{total_qty}</b>", table_cell_center_style),
            "",
            Paragraph(f"<b>{format_currency(total_amount)}</b>", ParagraphStyle("T2", parent=body_bold_style, alignment=2, textColor=colors.HexColor("#1E40AF"))),
        ])

        items_table = Table(
            items_table_data,
            colWidths=[10 * mm, 25 * mm, 60 * mm, 15 * mm, 15 * mm, 27 * mm, 28 * mm],
        )
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), # Navy Blue header
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Merge total row
            ("SPAN", (0, -1), (3, -1)),
            ("SPAN", (5, -1), (5, -1)),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFF6FF")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#2563EB")),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 4 * mm))

        # 5. Terms & Payment Info
        story.append(Paragraph("III. ĐIỀU KHOẢN KINH DOANH & PHƯƠNG THỨC THANH TOÁN", heading_section_style))
        terms_text = """
        • <b>Thời gian giao hàng:</b> Trong vòng 24h - 48h kể từ khi đơn hàng được xác nhận hoặc ký hợp đồng.<br/>
        • <b>Địa điểm giao hàng:</b> Kho bên mua hoặc thỏa thuận theo đơn hàng.<br/>
        • <b>Phương thức thanh toán:</b> Chuyển khoản ngân hàng 100% hoặc theo hạn mức tín dụng được duyệt.<br/>
        • <b>Thông tin chuyển khoản:</b><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;- Chủ tài khoản: <b>CÔNG TY CỔ PHẦN CÔNG NGHỆ ERP AI COPILOT</b><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;- Số tài khoản: <b>9999 8888 7777</b> tại <b>Ngân hàng TMCP Ngoại Thương Việt Nam (Vietcombank)</b> - CN Hà Nội.<br/>
        &nbsp;&nbsp;&nbsp;&nbsp;- Cú pháp: <i>Thanh toan don hang {order_number}</i>
        """.format(order_number=order.order_number)

        terms_box = Table(
            [[Paragraph(terms_text, body_style)]],
            colWidths=[180 * mm],
        )
        terms_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(terms_box)
        story.append(Spacer(1, 7 * mm))

        # 6. Signature Section
        sig_data = [
            [
                Paragraph("<b>ĐẠI DIỆN KHÁCH HÀNG</b><br/><i>(Ký, ghi rõ họ tên & đóng dấu)</i>", ParagraphStyle("S1", parent=body_style, alignment=1)),
                Paragraph("<b>ĐẠI DIỆN BÊN BÁN HÀNG</b><br/><i>(Ký, ghi rõ họ tên & đóng dấu)</i>", ParagraphStyle("S2", parent=body_style, alignment=1)),
            ],
            [
                Spacer(1, 20 * mm),
                Spacer(1, 20 * mm),
            ],
            [
                Paragraph("Xác nhận đặt hàng", ParagraphStyle("S3", parent=company_info_style, alignment=1)),
                Paragraph("Bộ phận Kinh Doanh / Giám Đốc Bán Hàng", ParagraphStyle("S4", parent=company_info_style, alignment=1)),
            ],
        ]
        sig_table = Table(sig_data, colWidths=[90 * mm, 90 * mm])
        sig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(sig_table)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

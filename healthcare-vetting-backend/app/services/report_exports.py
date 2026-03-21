"""
PDF Report Export Service
Generate financial reports, compliance summaries, and agency reports.
"""
import io
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from app.database import get_db


class ReportService:
    """Generate PDF reports for various purposes."""

    @staticmethod
    def generate_financial_report(period: str = "all", date_from: str = None,
                                   date_to: str = None) -> bytes:
        """Generate a financial report PDF."""
        with get_db() as db:
            # Get invoices
            query = "SELECT * FROM invoices WHERE 1=1"
            params = []
            if date_from:
                query += " AND created_at >= ?"
                params.append(date_from)
            if date_to:
                query += " AND created_at <= ?"
                params.append(date_to)
            query += " ORDER BY created_at DESC"
            invoices = db.execute(query, params).fetchall()

            # Get agencies
            agencies = db.execute("SELECT * FROM agencies").fetchall()
            agency_map = {dict(a)["id"]: dict(a) for a in agencies}

        total_revenue = sum(dict(i).get("sell_amount", 0) for i in invoices)
        total_cost = sum(dict(i).get("cost_amount", 0) for i in invoices)
        margin = total_revenue - total_cost

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=15*mm, rightMargin=15*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                      fontSize=18, textColor=colors.HexColor('#1e3a5f'))
        heading_style = ParagraphStyle('Heading2a', parent=styles['Heading2'],
                                        textColor=colors.HexColor('#1e3a5f'))
        normal_style = styles['Normal']
        small_style = ParagraphStyle('Small', parent=normal_style, fontSize=8,
                                      textColor=colors.grey)

        elements = []
        elements.append(Paragraph("HealthVet AI - Financial Report", title_style))
        elements.append(Spacer(1, 3*mm))
        period_label = period.upper() if period != "custom" else f"{date_from or 'Start'} to {date_to or 'Now'}"
        elements.append(Paragraph(f"Period: {period_label}", normal_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}",
            small_style,
        ))
        elements.append(Spacer(1, 10*mm))

        # Summary
        elements.append(Paragraph("Financial Summary", heading_style))
        summary_data = [
            ["Total Revenue:", f"\u00a3{total_revenue:,.2f}"],
            ["Total Cost:", f"\u00a3{total_cost:,.2f}"],
            ["Gross Margin:", f"\u00a3{margin:,.2f}"],
            ["Margin %:", f"{(margin/total_revenue*100):.1f}%" if total_revenue > 0 else "0%"],
            ["Total Invoices:", str(len(invoices))],
            ["Paid:", str(sum(1 for i in invoices if dict(i).get("status") == "paid"))],
            ["Pending:", str(sum(1 for i in invoices if dict(i).get("status") == "pending"))],
        ]
        t = Table(summary_data, colWidths=[40*mm, 60*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        # Revenue by agency
        agency_revenue = {}
        for inv in invoices:
            i = dict(inv)
            aid = i.get("agency_id", "unknown")
            if aid not in agency_revenue:
                agency_revenue[aid] = {"revenue": 0, "cost": 0, "count": 0}
            agency_revenue[aid]["revenue"] += i.get("sell_amount", 0)
            agency_revenue[aid]["cost"] += i.get("cost_amount", 0)
            agency_revenue[aid]["count"] += 1

        if agency_revenue:
            elements.append(Paragraph("Revenue by Agency", heading_style))
            elements.append(Spacer(1, 3*mm))
            agency_data = [["Agency", "Invoices", "Revenue", "Cost", "Margin"]]
            for aid, data in agency_revenue.items():
                aname = agency_map.get(aid, {}).get("name", "Unknown")
                m = data["revenue"] - data["cost"]
                agency_data.append([
                    aname,
                    str(data["count"]),
                    f"\u00a3{data['revenue']:,.2f}",
                    f"\u00a3{data['cost']:,.2f}",
                    f"\u00a3{m:,.2f}",
                ])
            t = Table(agency_data, colWidths=[50*mm, 25*mm, 30*mm, 30*mm, 30*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)

        # Invoice detail
        if invoices:
            elements.append(PageBreak())
            elements.append(Paragraph("Invoice Detail", heading_style))
            elements.append(Spacer(1, 3*mm))
            inv_data = [["ID", "Agency", "Type", "Amount", "Status", "Date"]]
            for inv in invoices:
                i = dict(inv)
                aname = agency_map.get(i.get("agency_id", ""), {}).get("name", "N/A")
                inv_data.append([
                    i.get("id", "")[:8],
                    aname[:20],
                    i.get("check_type", "N/A"),
                    f"\u00a3{i.get('sell_amount', 0):,.2f}",
                    i.get("status", "N/A").upper(),
                    i.get("created_at", "N/A")[:10] if i.get("created_at") else "N/A",
                ])
            t = Table(inv_data, colWidths=[20*mm, 35*mm, 30*mm, 25*mm, 20*mm, 25*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(t)

        elements.append(Spacer(1, 15*mm))
        elements.append(HRFlowable(width="100%", color=colors.HexColor('#1e3a5f')))
        elements.append(Paragraph(
            f"Generated by HealthVet AI on {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}.",
            small_style,
        ))

        doc.build(elements)
        return buffer.getvalue()

    @staticmethod
    def generate_compliance_summary(agency_id: str = None) -> bytes:
        """Generate compliance summary PDF."""
        with get_db() as db:
            if agency_id:
                candidates = db.execute(
                    """SELECT c.* FROM candidates c
                       JOIN agency_candidates ac ON c.id = ac.candidate_id
                       WHERE ac.agency_id=?""",
                    (agency_id,),
                ).fetchall()
            else:
                candidates = db.execute("SELECT * FROM candidates").fetchall()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=15*mm, rightMargin=15*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                      fontSize=18, textColor=colors.HexColor('#1e3a5f'))
        heading_style = ParagraphStyle('Heading2a', parent=styles['Heading2'],
                                        textColor=colors.HexColor('#1e3a5f'))
        normal_style = styles['Normal']
        small_style = ParagraphStyle('Small', parent=normal_style, fontSize=8,
                                      textColor=colors.grey)

        elements = []
        elements.append(Paragraph("HealthVet AI - Compliance Summary", title_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%d %B %Y')}",
            small_style,
        ))
        elements.append(Spacer(1, 10*mm))

        total = len(candidates)
        compliant = sum(1 for c in candidates if dict(c).get("compliance_status") == "compliant")
        pending = sum(1 for c in candidates if dict(c).get("compliance_status") in ("in_progress", "pending_review"))
        flagged = sum(1 for c in candidates if dict(c).get("compliance_status") == "incomplete")

        summary_data = [
            ["Total Candidates:", str(total)],
            ["Compliant:", str(compliant)],
            ["Pending:", str(pending)],
            ["Incomplete:", str(flagged)],
            ["Compliance Rate:", f"{(compliant/total*100):.1f}%" if total > 0 else "0%"],
        ]
        t = Table(summary_data, colWidths=[40*mm, 40*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        if candidates:
            elements.append(Paragraph("Candidate Detail", heading_style))
            cand_data = [["Name", "Profession", "Score", "Status"]]
            for cand in candidates:
                cd = dict(cand)
                cand_data.append([
                    f"{cd.get('first_name', '')} {cd.get('last_name', '')}",
                    cd.get("profession", "N/A"),
                    f"{cd.get('compliance_score', 0):.0f}%",
                    cd.get("compliance_status", "incomplete").upper(),
                ])
            t = Table(cand_data, colWidths=[50*mm, 40*mm, 25*mm, 40*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)

        elements.append(Spacer(1, 15*mm))
        elements.append(HRFlowable(width="100%", color=colors.HexColor('#1e3a5f')))
        elements.append(Paragraph(
            f"Generated by HealthVet AI on {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}.",
            small_style,
        ))

        doc.build(elements)
        return buffer.getvalue()

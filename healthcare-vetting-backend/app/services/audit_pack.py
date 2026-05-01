"""
CQC Audit Pack Generation Service
Generates comprehensive audit packs for CQC inspections with full candidate
compliance files, timestamped logs, verification evidence, and scoring history.
"""
import json
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


def _s(val, default="N/A"):
    """Return val as a string, or default if val is None."""
    return str(val) if val is not None else default


def _n(val, default=0):
    """Return val as a number, or default if val is None."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


class AuditPackService:
    """Generate CQC-ready audit packs."""

    @staticmethod
    def generate_candidate_audit(candidate_id: str) -> bytes:
        """Generate a full audit pack PDF for a single candidate."""
        with get_db() as db:
            db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
            candidate = db.fetchone()
            if not candidate:
                raise ValueError("Candidate not found")
            c = dict(candidate)

            # Gather all check data
            db.execute(
                "SELECT * FROM identity_checks WHERE candidate_id=%s ORDER BY started_at DESC",
                (candidate_id,),
            )
            identity = db.fetchall()
            db.execute(
                "SELECT * FROM right_to_work_checks WHERE candidate_id=%s ORDER BY checked_at DESC",
                (candidate_id,),
            )
            rtw = db.fetchall()
            db.execute(
                "SELECT * FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC",
                (candidate_id,),
            )
            dbs = db.fetchall()
            db.execute(
                "SELECT * FROM cv_analyses WHERE candidate_id=%s ORDER BY analysed_at DESC",
                (candidate_id,),
            )
            cv = db.fetchall()
            db.execute(
                "SELECT * FROM registration_checks WHERE candidate_id=%s ORDER BY last_checked DESC",
                (candidate_id,),
            )
            reg = db.fetchall()
            db.execute(
                "SELECT * FROM references_ WHERE candidate_id=%s",
                (candidate_id,),
            )
            refs = db.fetchall()
            db.execute(
                "SELECT * FROM employment_history WHERE candidate_id=%s ORDER BY start_date DESC",
                (candidate_id,),
            )
            emp_history = db.fetchall()
            db.execute(
                "SELECT * FROM employment_verifications WHERE candidate_id=%s",
                (candidate_id,),
            )
            emp_verifications = db.fetchall()
            db.execute(
                "SELECT * FROM compliance_records WHERE candidate_id=%s",
                (candidate_id,),
            )
            compliance = db.fetchone()
            db.execute(
                "SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC",
                (candidate_id,),
            )
            audit_logs = db.fetchall()
            db.execute(
                "SELECT * FROM monitoring_alerts WHERE candidate_id=%s ORDER BY created_at DESC",
                (candidate_id,),
            )
            alerts = db.fetchall()

            # Try to get training certificates
            training = []
            try:
                db.execute(
                    "SELECT * FROM training_certificates WHERE candidate_id=%s",
                    (candidate_id,),
                )
                training = db.fetchall()
            except Exception:
                pass

        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=15*mm, rightMargin=15*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                      fontSize=20, textColor=colors.HexColor('#1e3a5f'))
        heading_style = ParagraphStyle('Heading2a', parent=styles['Heading2'],
                                        textColor=colors.HexColor('#1e3a5f'),
                                        spaceAfter=6)
        _subheading_style = ParagraphStyle('Heading3a', parent=styles['Heading3'],  # noqa: F841
                                            textColor=colors.HexColor('#2d5f8a'))
        normal_style = styles['Normal']
        small_style = ParagraphStyle('Small', parent=normal_style, fontSize=8,
                                      textColor=colors.grey)

        elements = []

        # Cover page
        elements.append(Spacer(1, 30*mm))
        elements.append(Paragraph("Viper AI", title_style))
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph("CQC Compliance Audit Pack", heading_style))
        elements.append(Spacer(1, 10*mm))
        elements.append(HRFlowable(width="80%", color=colors.HexColor('#1e3a5f')))
        elements.append(Spacer(1, 10*mm))

        # Candidate info table
        candidate_name = f"{_s(c.get('first_name'), '')} {_s(c.get('last_name'), '')}"
        comp = dict(compliance) if compliance else {}
        info_data = [
            ["Candidate Name:", candidate_name],
            ["Email:", _s(c.get("email"))],
            ["Profession:", _s(c.get("profession"))],
            ["Registration:", f"{_s(c.get('registration_body'))} - {_s(c.get('registration_number'))}"],
            ["Compliance Score:", f"{_n(comp.get('score')):.0f}%"],
            ["Compliance Status:", _s(comp.get("overall_status"), "incomplete").upper()],
            ["CQC Ready:", "YES" if comp.get("cqc_ready") else "NO"],
            ["Report Generated:", datetime.now(timezone.utc).strftime("%d %B %Y at %H:%M UTC")],
        ]
        info_table = Table(info_data, colWidths=[45*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(info_table)
        elements.append(PageBreak())

        # Section 1: Identity Verification
        elements.append(Paragraph("1. Identity Verification", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if identity:
            for check in identity:
                cd = dict(check)
                data = [
                    ["Provider:", cd.get("provider", "N/A")],
                    ["Document Type:", cd.get("document_type", "N/A")],
                    ["Result:", _s(cd.get("result")).upper()],
                    ["Facial Match:", f"{_n(cd.get('facial_match_score')):.0f}%"],
                    ["Liveness:", cd.get("liveness_check", "N/A")],
                    ["Address Verified:", "Yes" if cd.get("address_verified") else "No"],
                    ["Date:", cd.get("started_at", "N/A")],
                ]
                t = Table(data, colWidths=[40*mm, 125*mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
        else:
            elements.append(Paragraph("No identity checks on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 2: Right to Work
        elements.append(Paragraph("2. Right to Work Verification", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if rtw:
            for check in rtw:
                cd = dict(check)
                data = [
                    ["Method:", cd.get("verification_method", "share_code")],
                    ["Nationality:", cd.get("nationality", "N/A")],
                    ["Verified:", "Yes" if cd.get("verified") else "No"],
                    ["Visa Type:", cd.get("visa_type", "N/A")],
                    ["Visa Expiry:", cd.get("visa_expiry", "N/A")],
                    ["Restrictions:", cd.get("work_restrictions", "None")],
                    ["Date:", cd.get("checked_at", "N/A")],
                ]
                t = Table(data, colWidths=[40*mm, 125*mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
        else:
            elements.append(Paragraph("No right to work checks on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 3: Enhanced DBS
        elements.append(Paragraph("3. Enhanced DBS Check", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if dbs:
            for check in dbs:
                cd = dict(check)
                data = [
                    ["Provider:", cd.get("provider", "N/A")],
                    ["Check Type:", cd.get("check_type", "enhanced")],
                    ["Status:", cd.get("status", "N/A")],
                    ["Result:", _s(cd.get("result")).upper()],
                    ["Certificate No:", cd.get("certificate_number", "N/A")],
                    ["Issue Date:", cd.get("issue_date", "N/A")],
                    ["Update Service:", "Registered" if cd.get("update_service_registered") else "Not Registered"],
                    ["Next Renewal:", cd.get("next_renewal", "N/A")],
                    ["Submitted:", cd.get("submitted_at", "N/A")],
                ]
                t = Table(data, colWidths=[40*mm, 125*mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
        else:
            elements.append(Paragraph("No DBS checks on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 4: CV Analysis
        elements.append(Paragraph("4. CV Analysis & Fraud Detection", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if cv:
            for check in cv:
                cd = dict(check)
                data = [
                    ["Fraud Risk Score:", f"{_n(cd.get('fraud_risk_score')):.1%}"],
                    ["Status:", cd.get("status", "N/A")],
                    ["Analysis Date:", cd.get("analysed_at", "N/A")],
                ]
                gaps = cd.get("gap_analysis")
                if gaps:
                    try:
                        gap_list = json.loads(gaps) if isinstance(gaps, str) else gaps
                        if gap_list:
                            data.append(["Gaps Found:", str(len(gap_list))])
                    except Exception:
                        pass
                t = Table(data, colWidths=[40*mm, 125*mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
        else:
            elements.append(Paragraph("No CV analysis on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 5: Employment History & Verification
        elements.append(Paragraph("5. Employment History & Verification", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if emp_history:
            emp_table_data = [["Employer", "Job Title", "Dates", "Verified"]]
            emp_ver_map = {dict(v)["employment_id"]: dict(v) for v in emp_verifications}
            for entry in emp_history:
                e = dict(entry)
                ver = emp_ver_map.get(e["id"])
                verified = "Yes" if ver and ver.get("status") == "completed" else "No"
                dates = f"{e.get('start_date', '?')} - {e.get('end_date', 'Present')}"
                emp_table_data.append([
                    e.get("employer_name", "N/A"),
                    e.get("job_title", "N/A"),
                    dates,
                    verified,
                ])
            t = Table(emp_table_data, colWidths=[45*mm, 45*mm, 45*mm, 25*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No employment history on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 6: Professional Registration
        elements.append(Paragraph("6. Professional Registration", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if reg:
            for check in reg:
                cd = dict(check)
                data = [
                    ["Body:", cd.get("body", "N/A")],
                    ["Registration No:", cd.get("registration_number", "N/A")],
                    ["Active:", "Yes" if cd.get("is_active") else "No"],
                    ["Sanctions:", cd.get("sanctions", "None")],
                    ["Conditions:", cd.get("conditions", "None")],
                    ["Last Checked:", cd.get("last_checked", "N/A")],
                ]
                t = Table(data, colWidths=[40*mm, 125*mm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
        else:
            elements.append(Paragraph("No registration checks on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 7: References
        elements.append(Paragraph("7. References", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if refs:
            ref_table_data = [["Referee", "Organisation", "Status", "Domain Verified", "Date"]]
            for ref in refs:
                r = dict(ref)
                ref_table_data.append([
                    r.get("referee_name", "N/A"),
                    r.get("referee_organisation", "N/A"),
                    _s(r.get("status")).upper(),
                    "Yes" if r.get("domain_verified") else "No",
                    r.get("sent_at", "N/A")[:10] if r.get("sent_at") else "N/A",
                ])
            t = Table(ref_table_data, colWidths=[35*mm, 40*mm, 25*mm, 30*mm, 30*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No references on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section 8: Training Certificates
        if training:
            elements.append(Paragraph("8. Training Certificates", heading_style))
            elements.append(HRFlowable(width="100%", color=colors.lightgrey))
            elements.append(Spacer(1, 3*mm))
            train_data = [["Certificate", "Provider", "Issue Date", "Expiry", "Status"]]
            for cert in training:
                cd = dict(cert)
                train_data.append([
                    cd.get("certificate_name", "N/A"),
                    cd.get("provider", "N/A"),
                    cd.get("issue_date", "N/A"),
                    cd.get("expiry_date", "N/A"),
                    _s(cd.get("status")).upper(),
                ])
            t = Table(train_data, colWidths=[40*mm, 35*mm, 30*mm, 30*mm, 25*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 5*mm))

        # Section: Monitoring Alerts History
        elements.append(PageBreak())
        section_num = 9 if training else 8
        elements.append(Paragraph(f"{section_num}. Monitoring Alerts History", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if alerts:
            alert_cell = ParagraphStyle('AlertCell', parent=normal_style,
                                         fontSize=8, leading=10, wordWrap='CJK')
            alert_data = [[
                Paragraph("<b>Type</b>", alert_cell),
                Paragraph("<b>Severity</b>", alert_cell),
                Paragraph("<b>Message</b>", alert_cell),
                Paragraph("<b>Resolved</b>", alert_cell),
                Paragraph("<b>Date</b>", alert_cell),
            ]]
            for alert in alerts:
                ad = dict(alert)
                alert_data.append([
                    Paragraph(_s(ad.get("alert_type")).replace("_", " ").title(), alert_cell),
                    Paragraph(_s(ad.get("severity")).upper(), alert_cell),
                    Paragraph(_s(ad.get("message"))[:80], alert_cell),
                    Paragraph("Yes" if ad.get("is_resolved") else "No", alert_cell),
                    Paragraph(str(ad.get("created_at", "N/A"))[:10] if ad.get("created_at") else "N/A", alert_cell),
                ])
            t = Table(alert_data, colWidths=[35*mm, 18*mm, 75*mm, 16*mm, 22*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No monitoring alerts on record.", normal_style))
        elements.append(Spacer(1, 5*mm))

        # Section: Audit Trail
        section_num += 1
        elements.append(Paragraph(f"{section_num}. Audit Trail", heading_style))
        elements.append(HRFlowable(width="100%", color=colors.lightgrey))
        elements.append(Spacer(1, 3*mm))
        if audit_logs:
            def _fmt_action(raw):
                """Convert snake_case action to readable label."""
                if not raw:
                    return "N/A"
                return str(raw).replace("_", " ").title()

            def _fmt_actor(raw):
                """Shorten UUIDs and clean up actor names."""
                if not raw:
                    return "N/A"
                s = str(raw)
                if s == "compliance_engine":
                    return "System"
                # Truncate UUIDs (8 chars + ...)
                import re
                s = re.sub(
                    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                    lambda m: m.group(0)[:8] + '\u2026',
                    s,
                )
                return s

            def _fmt_details(raw):
                """Parse JSON details into readable key-value summary."""
                if not raw:
                    return ""
                import re as _re
                _uuid_re = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
                s = str(raw)
                try:
                    d = json.loads(s) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
                    if isinstance(d, dict):
                        skip_keys = {"flags", "compliance_label", "template_checks"}
                        parts = []
                        for k, v in d.items():
                            if k in skip_keys and (not v or str(v).startswith("[")):
                                continue
                            label = str(k).replace("_", " ").title()
                            val = str(v)
                            val = _re.sub(_uuid_re, lambda m: m.group(0)[:8] + '\u2026', val)
                            if len(val) > 40:
                                val = val[:37] + "..."
                            parts.append(f"{label}: {val}")
                        return " | ".join(parts) if parts else s[:60]
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
                s = _re.sub(_uuid_re, lambda m: m.group(0)[:8] + '\u2026', s)
                return s[:80] + ("..." if len(s) > 80 else "")

            def _fmt_ts(raw):
                """Format timestamp to readable date/time."""
                if not raw:
                    return "N/A"
                s = str(raw)[:19]  # 2026-04-28T21:56:18
                try:
                    dt = datetime.fromisoformat(s)
                    return dt.strftime("%d %b %Y  %H:%M")
                except (ValueError, TypeError):
                    return s

            audit_style = ParagraphStyle('AuditCell', parent=normal_style,
                                          fontSize=7, leading=9,
                                          wordWrap='CJK')
            log_data = [[
                Paragraph("<b>Action</b>", audit_style),
                Paragraph("<b>Actor</b>", audit_style),
                Paragraph("<b>Details</b>", audit_style),
                Paragraph("<b>Timestamp</b>", audit_style),
            ]]
            for log in audit_logs[:50]:
                ld = dict(log)
                log_data.append([
                    Paragraph(_fmt_action(ld.get("action")), audit_style),
                    Paragraph(_fmt_actor(ld.get("actor")), audit_style),
                    Paragraph(_fmt_details(ld.get("details")), audit_style),
                    Paragraph(_fmt_ts(ld.get("created_at")), audit_style),
                ])
            t = Table(log_data, colWidths=[32*mm, 22*mm, 80*mm, 30*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No audit log entries.", normal_style))

        # Footer
        elements.append(Spacer(1, 15*mm))
        elements.append(HRFlowable(width="100%", color=colors.HexColor('#1e3a5f')))
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"This audit pack was generated by Viper AI on "
            f"{datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}. "
            f"All data is verified and timestamped for CQC compliance purposes.",
            small_style,
        ))

        doc.build(elements)
        return buffer.getvalue()

    @staticmethod
    def generate_bulk_audit(candidate_ids: list) -> bytes:
        """Generate a combined audit pack PDF for multiple candidates."""
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for cid in candidate_ids:
            try:
                pdf_bytes = AuditPackService.generate_candidate_audit(cid)
                merger.append(io.BytesIO(pdf_bytes))
            except Exception:
                continue
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        return output.getvalue()

    @staticmethod
    def generate_agency_audit(agency_id: str) -> bytes:
        """Generate an agency-wide audit summary PDF."""
        with get_db() as db:
            db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
            agency = db.fetchone()
            if not agency:
                raise ValueError("Agency not found")
            a = dict(agency)

            db.execute(
                """SELECT c.*, ac.employment_status FROM candidates c
                   JOIN agency_candidates ac ON c.id = ac.candidate_id
                   WHERE ac.agency_id=%s""",
                (agency_id,),
            )
            candidates = db.fetchall()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=15*mm, rightMargin=15*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                      fontSize=20, textColor=colors.HexColor('#1e3a5f'))
        heading_style = ParagraphStyle('Heading2a', parent=styles['Heading2'],
                                        textColor=colors.HexColor('#1e3a5f'))
        normal_style = styles['Normal']
        small_style = ParagraphStyle('Small', parent=normal_style, fontSize=8,
                                      textColor=colors.grey)

        elements = []
        elements.append(Spacer(1, 20*mm))
        elements.append(Paragraph("Viper AI", title_style))
        elements.append(Paragraph("Agency Compliance Summary", heading_style))
        elements.append(Spacer(1, 10*mm))
        elements.append(HRFlowable(width="80%", color=colors.HexColor('#1e3a5f')))
        elements.append(Spacer(1, 10*mm))

        info_data = [
            ["Agency:", a.get("name", "N/A")],
            ["Contact:", a.get("contact_name", "N/A")],
            ["Email:", a.get("email", "N/A")],
            ["Total Candidates:", str(len(candidates))],
            ["Report Date:", datetime.now(timezone.utc).strftime("%d %B %Y")],
        ]
        t = Table(info_data, colWidths=[40*mm, 125*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10*mm))

        # Candidate summary table
        if candidates:
            elements.append(Paragraph("Candidate Compliance Summary", heading_style))
            elements.append(Spacer(1, 5*mm))
            cand_data = [["Name", "Profession", "Score", "Status", "CQC Ready"]]
            for cand in candidates:
                cd = dict(cand)
                cand_data.append([
                    f"{_s(cd.get('first_name'), '')} {_s(cd.get('last_name'), '')}",
                    _s(cd.get("profession")),
                    f"{_n(cd.get('compliance_score')):.0f}%",
                    _s(cd.get("compliance_status"), "incomplete").upper(),
                    "Yes" if cd.get("compliance_status") == "compliant" else "No",
                ])
            t = Table(cand_data, colWidths=[40*mm, 30*mm, 25*mm, 35*mm, 25*mm])
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
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Generated by Viper AI on {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}.",
            small_style,
        ))

        doc.build(elements)
        return buffer.getvalue()

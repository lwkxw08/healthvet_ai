"""
CQC Audit DOCX Export — VIPER Enterprise Template

Generates audit reports in the branded VIPER template layout matching the
provided VIPER_Enterprise_Audit_Report_sample.docx exactly.
"""
import io
from datetime import datetime, timezone
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from app.database import get_db

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "viper-logo.png"
COVER_PATH = ASSETS_DIR / "viper-cover.png"

# Brand colours
BRAND_NAVY = RGBColor(0x17, 0x36, 0x5D)
BRAND_HEADING = RGBColor(0x36, 0x5F, 0x91)
BRAND_LINK = RGBColor(0x4F, 0x81, 0xBD)


def _s(val, default="N/A"):
    return str(val) if val is not None else default


def _n(val, default=0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _set_cell_shading(cell, color_hex: str):
    """Set background shading on a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color_hex)
    shading.set(qn("w:val"), "clear")
    tcPr.append(shading)


def _set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    """Set borders on a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        if val:
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), val.get("val", "single"))
            el.set(qn("w:sz"), str(val.get("sz", 4)))
            el.set(qn("w:color"), val.get("color", "auto"))
            el.set(qn("w:space"), "0")
            borders.append(el)
    tcPr.append(borders)


def _add_styled_table(doc, headers, rows, col_widths=None):
    """Add a table with VIPER branding (header row with navy background)."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    # Header row
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        for paragraph in hdr_cells[i].paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _set_cell_shading(hdr_cells[i], "1E3A5F")

    # Data rows
    for ri, row_data in enumerate(rows):
        cells = table.rows[ri + 1].cells
        for ci, val in enumerate(row_data):
            cells[ci].text = str(val) if val is not None else "N/A"
            for paragraph in cells[ci].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
        # Alternating row shading
        if ri % 2 == 1:
            for cell in cells:
                _set_cell_shading(cell, "F0F4F8")

    # Set column widths if provided
    if col_widths:
        for ri, row in enumerate(table.rows):
            for ci, width in enumerate(col_widths):
                if ci < len(row.cells):
                    row.cells[ci].width = Cm(width)

    # Light grid borders
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "CCCCCC")
        el.set(qn("w:space"), "0")
        borders.append(el)
    tblPr.append(borders)

    return table


def _add_kv_table(doc, pairs):
    """Add a 2-column key/value table (like the candidate summary box)."""
    table = doc.add_table(rows=len(pairs), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, (key, val) in enumerate(pairs):
        table.rows[ri].cells[0].text = key
        table.rows[ri].cells[1].text = str(val) if val is not None else "N/A"
        for paragraph in table.rows[ri].cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(10)
        for paragraph in table.rows[ri].cells[1].paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(10)
    # Set widths
    for row in table.rows:
        row.cells[0].width = Cm(5)
        row.cells[1].width = Cm(12)
    return table


def generate_candidate_audit_docx(candidate_id: str) -> bytes:
    """Generate a VIPER-branded DOCX audit report for a candidate."""
    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise ValueError("Candidate not found")
        c = dict(candidate)

        db.execute("SELECT * FROM identity_checks WHERE candidate_id=%s ORDER BY started_at DESC", (candidate_id,))
        identity = db.fetchall()
        db.execute("SELECT * FROM right_to_work_checks WHERE candidate_id=%s ORDER BY checked_at DESC", (candidate_id,))
        rtw = db.fetchall()
        db.execute("SELECT * FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC", (candidate_id,))
        dbs = db.fetchall()
        db.execute("SELECT * FROM cv_analyses WHERE candidate_id=%s ORDER BY analysed_at DESC", (candidate_id,))
        cv = db.fetchall()
        db.execute("SELECT * FROM registration_checks WHERE candidate_id=%s ORDER BY last_checked DESC", (candidate_id,))
        reg = db.fetchall()
        db.execute("SELECT * FROM references_ WHERE candidate_id=%s", (candidate_id,))
        refs = db.fetchall()
        db.execute("SELECT * FROM employment_history WHERE candidate_id=%s ORDER BY start_date DESC", (candidate_id,))
        emp_history = db.fetchall()
        db.execute("SELECT * FROM employment_verifications WHERE candidate_id=%s", (candidate_id,))
        emp_verifications = db.fetchall()
        db.execute("SELECT * FROM compliance_records WHERE candidate_id=%s", (candidate_id,))
        compliance = db.fetchone()
        db.execute("SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC LIMIT 50", (candidate_id,))
        audit_logs = db.fetchall()
        db.execute("SELECT * FROM monitoring_alerts WHERE candidate_id=%s ORDER BY created_at DESC", (candidate_id,))
        alerts = db.fetchall()

        training = []
        try:
            db.execute("SELECT * FROM training_certificates WHERE candidate_id=%s", (candidate_id,))
            training = db.fetchall()
        except Exception:
            pass

    comp = dict(compliance) if compliance else {}
    now = datetime.now(timezone.utc)

    # Build DOCX
    doc = Document()

    # Page setup
    section = doc.sections[0]
    section.page_width = Emu(7772400)   # match template
    section.page_height = Emu(10058400)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3)
    section.right_margin = Cm(3)

    # ── COVER PAGE ──────────────────────────────────────────────
    # Logo
    if LOGO_PATH.exists():
        doc.add_picture(str(LOGO_PATH), width=Inches(2.5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Cover image
    if COVER_PATH.exists():
        doc.add_picture(str(COVER_PATH), width=Inches(5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Title
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run("\nCQC COMPLIANCE AUDIT REPORT")
    title_run.bold = True
    title_run.font.size = Pt(22)
    title_run.font.color.rgb = BRAND_NAVY

    # Subtitle
    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_para.add_run("Enterprise Compliance Report")
    sub_run.font.size = Pt(12)
    sub_run.font.color.rgb = BRAND_HEADING
    sub_para.add_run("\n")
    conf_run = sub_para.add_run("Confidential")
    conf_run.font.size = Pt(10)
    conf_run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    doc.add_page_break()

    # ── CANDIDATE SUMMARY TABLE ─────────────────────────────────
    _candidate_name = f"{_s(c.get('first_name'), '')} {_s(c.get('last_name'), '')}"
    compliance_status = _s(comp.get("overall_status"), "incomplete").upper()
    cqc_ready = "YES" if comp.get("cqc_ready") else "NO"
    risk_level = "LOW" if comp.get("cqc_ready") else "MEDIUM"
    risk_emoji = "\U0001F7E2" if risk_level == "LOW" else "\U0001F7E1"

    _add_kv_table(doc, [
        ("Candidate ID", candidate_id[:12] + "..."),
        ("Role", _s(c.get("profession"), "Healthcare Professional")),
        ("Compliance Status", compliance_status),
        ("CQC Ready", cqc_ready),
        ("Risk Level", f"{risk_level} ({risk_emoji})"),
    ])

    doc.add_paragraph()

    # ── INSPECTOR SUMMARY ───────────────────────────────────────
    summary_heading = doc.add_paragraph()
    run = summary_heading.add_run("Inspector Summary")
    run.font.size = Pt(26)
    run.font.color.rgb = BRAND_NAVY

    score = _n(comp.get("score"))
    summary_text = (
        f"Candidate is {'fully compliant with all required checks and suitable for deployment'}"
        if compliance_status == "COMPLIANT"
        else f"Candidate compliance is in progress. Current score: {score:.0f}%."
    )
    p = doc.add_paragraph()
    r = p.add_run(f"\nSummary: {summary_text}")
    r.font.size = Pt(10)

    doc.add_paragraph()

    # ── 1. IDENTITY VERIFICATION ────────────────────────────────
    h = doc.add_heading("1. Identity Verification", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if identity:
        headers = ["Provider", "Document", "Result", "Facial Match", "Liveness", "Date", "Address Verified"]
        rows = []
        for check in identity:
            cd = dict(check)
            rows.append([
                cd.get("provider", "N/A"),
                cd.get("document_type", "N/A"),
                _s(cd.get("result", "")).upper(),
                f"{_n(cd.get('facial_match_score')):.0f}%",
                cd.get("liveness_check", "N/A"),
                _s(cd.get("started_at", ""))[:10],
                "Yes" if cd.get("address_verified") else "No",
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No identity checks on record.")

    # ── 2. RIGHT TO WORK ────────────────────────────────────────
    h = doc.add_heading("2. Right to Work", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if rtw:
        headers = ["Method", "Nationality", "Verified", "Visa Type", "Date"]
        rows = []
        for check in rtw:
            cd = dict(check)
            rows.append([
                cd.get("verification_method", "share_code"),
                cd.get("nationality", "N/A"),
                "Yes" if cd.get("verified") else "No",
                cd.get("visa_type", "N/A"),
                _s(cd.get("checked_at", ""))[:10],
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No right to work checks on record.")

    # ── 3. ENHANCED DBS CHECK ───────────────────────────────────
    h = doc.add_heading("3. Enhanced DBS Check", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if dbs:
        headers = ["Provider", "Type", "Status", "Result", "Update Service", "Submitted Date"]
        rows = []
        for check in dbs:
            cd = dict(check)
            rows.append([
                cd.get("provider", "N/A"),
                cd.get("check_type", "Enhanced"),
                cd.get("status", "N/A"),
                _s(cd.get("result", "")).upper(),
                "Registered" if cd.get("update_service_registered") else "Not Registered",
                _s(cd.get("submitted_at", ""))[:10],
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No DBS checks on record.")

    # ── 4. FRAUD DETECTION ──────────────────────────────────────
    h = doc.add_heading("4. Fraud Detection", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if cv:
        headers = ["Score", "Status", "Analysis Date"]
        rows = []
        for check in cv:
            cd = dict(check)
            rows.append([
                f"{_n(cd.get('fraud_risk_score')) * 100:.0f}%",
                cd.get("status", "N/A"),
                _s(cd.get("analysed_at", ""))[:10],
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No fraud detection records.")

    # ── 5. EMPLOYMENT HISTORY ───────────────────────────────────
    h = doc.add_heading("5. Employment History", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if emp_history:
        emp_ver_map = {dict(v)["employment_id"]: dict(v) for v in emp_verifications}
        headers = ["Employer", "Role", "Dates", "Verified", "Checked Date"]
        rows = []
        for entry in emp_history:
            e = dict(entry)
            ver = emp_ver_map.get(e["id"])
            verified = "Yes" if ver and ver.get("status") in ("verified", "completed") else "No"
            dates = f"{e.get('start_date', '?')}-{e.get('end_date', 'Present')}"
            checked_date = ""
            if ver:
                checked_date = _s(ver.get("completed_at") or ver.get("created_at"), "")[:10]
            rows.append([
                e.get("employer_name", "N/A"),
                e.get("job_title", "N/A"),
                dates,
                verified,
                checked_date or "N/A",
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No employment history on record.")

    # ── 6. PROFESSIONAL REGISTRATION ────────────────────────────
    h = doc.add_heading("6. Professional Registration", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if reg:
        headers = ["Body", "Status", "Sanctions", "Last Checked"]
        rows = []
        for check in reg:
            cd = dict(check)
            rows.append([
                cd.get("body", "N/A"),
                "Active" if cd.get("is_active") else "Inactive",
                cd.get("sanctions", "None"),
                _s(cd.get("last_checked", ""))[:10],
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No registration checks on record.")

    # ── 7. REFERENCES ───────────────────────────────────────────
    h = doc.add_heading("7. References", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if refs:
        headers = ["Referee", "Organisation", "Status", "Date"]
        rows = []
        for ref in refs:
            r = dict(ref)
            rows.append([
                r.get("referee_name", "N/A"),
                r.get("referee_organisation", "N/A"),
                _s(r.get("status", "")).title(),
                _s(r.get("sent_at", ""))[:10] if r.get("sent_at") else "N/A",
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No references on record.")

    # ── 8. TRAINING CERTIFICATES ────────────────────────────────
    h = doc.add_heading("8. Training Certificates", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if training:
        headers = ["Certificate", "Issue Date", "Expiry Date", "Status"]
        rows = []
        for cert in training:
            cd = dict(cert)
            rows.append([
                cd.get("certificate_name", "N/A"),
                cd.get("issue_date", "N/A"),
                cd.get("expiry_date", "N/A"),
                _s(cd.get("status", "")).upper(),
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No training certificates on record.")

    # ── 9. MONITORING ALERTS ────────────────────────────────────
    h = doc.add_heading("9. Monitoring Alerts", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if alerts:
        headers = ["Type", "Severity", "Resolved", "Date"]
        rows = []
        for alert in alerts:
            ad = dict(alert)
            rows.append([
                _s(ad.get("alert_type", "")).replace("_", " ").title(),
                _s(ad.get("severity", "")).upper(),
                "Yes" if ad.get("is_resolved") else "No",
                _s(ad.get("created_at", ""))[:10],
            ])
        _add_styled_table(doc, headers, rows)
    else:
        doc.add_paragraph("No monitoring alerts on record.")

    # ── 10. AUDIT TRAIL ─────────────────────────────────────────
    h = doc.add_heading("10. Audit Trail", level=1)
    for run in h.runs:
        run.font.color.rgb = BRAND_HEADING

    if audit_logs:
        # Build a summary paragraph of events
        first_date = _s(dict(audit_logs[-1]).get("created_at", ""))[:7]
        last_date = _s(dict(audit_logs[0]).get("created_at", ""))[:7]
        actions = set()
        for log in audit_logs:
            action = dict(log).get("action", "")
            if action:
                actions.add(str(action).replace("_", " ").lower())

        summary = f"Multiple system events recorded between {first_date} and {last_date}"
        if actions:
            summary += f" including {', '.join(list(actions)[:5])}"
            if len(actions) > 5:
                summary += f" and {len(actions) - 5} more"
        summary += "."
        doc.add_paragraph(summary)
    else:
        doc.add_paragraph("No audit log entries.")

    # ── FOOTER ──────────────────────────────────────────────────
    doc.add_paragraph()
    footer_para = doc.add_paragraph()
    footer_run = footer_para.add_run(
        f"This audit report was generated by Viper AI on "
        f"{now.strftime('%d %B %Y at %H:%M UTC')}. "
        f"All data is verified and timestamped for CQC compliance purposes."
    )
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

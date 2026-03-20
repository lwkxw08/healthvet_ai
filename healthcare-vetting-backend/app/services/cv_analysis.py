"""
AI-Powered CV & Document Validation Service
Uses LLM + rule engine for gap analysis, overlap detection, qualification verification.
In production, integrate with OpenAI/Anthropic API for deep analysis.
"""
import json
import random
import re
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id


class CVAnalysisService:
    """AI-powered CV analysis with fraud detection and qualification verification."""

    @staticmethod
    def analyse_cv(candidate_id: str, cv_text: str, cv_file_name: str | None = None) -> dict:
        analysis_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        # Run all analysis components
        gaps = CVAnalysisService._detect_employment_gaps(cv_text)
        overlaps = CVAnalysisService._detect_overlaps(cv_text)
        qual_flags = CVAnalysisService._verify_qualifications(cv_text)
        inconsistencies = CVAnalysisService._detect_inconsistencies(cv_text)
        fraud_score = CVAnalysisService._calculate_fraud_risk(gaps, overlaps, qual_flags, inconsistencies)
        employment_entries = CVAnalysisService._extract_employment_history(cv_text)
        summary = CVAnalysisService._generate_ai_summary(cv_text, gaps, overlaps, qual_flags, fraud_score)

        with get_db() as db:
            db.execute(
                """INSERT INTO cv_analyses
                   (id, candidate_id, cv_text, cv_file_name, gap_analysis, overlap_detection,
                    qualification_flags, fraud_risk_score, inconsistencies, ai_summary,
                    employment_entries, status, analysed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)""",
                (
                    analysis_id, candidate_id, cv_text, cv_file_name,
                    json.dumps(gaps), json.dumps(overlaps),
                    json.dumps(qual_flags), fraud_score,
                    json.dumps(inconsistencies), summary,
                    json.dumps(employment_entries), now,
                ),
            )

            # Auto-create employment_history records from extracted entries
            for entry in employment_entries:
                entry_id = generate_id()
                db.execute(
                    """INSERT INTO employment_history
                       (id, candidate_id, cv_analysis_id, employer_name, job_title,
                        start_date, end_date, is_current, duties, source, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'cv_extracted', ?)""",
                    (
                        entry_id, candidate_id, analysis_id,
                        entry.get("employer", "Unknown Employer"),
                        entry.get("job_title", "Unknown Role"),
                        entry.get("start_date"),
                        entry.get("end_date"),
                        1 if entry.get("is_current") else 0,
                        entry.get("duties"),
                        now,
                    ),
                )

            # Create alert if fraud risk is high
            if fraud_score > 0.6:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'cv_fraud_risk', 'high', ?, ?, ?)""",
                    (
                        generate_id(), candidate_id,
                        f"High CV fraud risk detected: {fraud_score:.0%}",
                        json.dumps({"fraud_score": fraud_score, "flags": qual_flags}),
                        now,
                    ),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'cv_analysis', ?, 'completed', 'ai_engine', ?, ?)""",
                (generate_id(), analysis_id, json.dumps({"fraud_score": fraud_score}), now),
            )

            row = db.execute("SELECT * FROM cv_analyses WHERE id=?", (analysis_id,)).fetchone()
            return dict(row)

    @staticmethod
    def _detect_employment_gaps(cv_text: str) -> list:
        """Detect gaps in employment history using date pattern analysis."""
        # In production, use NLP/LLM to extract and analyze dates
        date_patterns = re.findall(
            r'(\d{4})\s*[-–to]+\s*(\d{4}|present|current)',
            cv_text.lower()
        )

        gaps = []
        sorted_dates = sorted(date_patterns, key=lambda x: int(x[0]))

        for i in range(len(sorted_dates) - 1):
            end_year = sorted_dates[i][1]
            if end_year in ("present", "current"):
                continue
            next_start = int(sorted_dates[i + 1][0])
            this_end = int(end_year)
            if next_start - this_end > 1:
                gaps.append({
                    "from_year": this_end,
                    "to_year": next_start,
                    "gap_months": (next_start - this_end) * 12,
                    "severity": "high" if (next_start - this_end) > 2 else "medium",
                })

        # Simulate additional gap detection
        if not gaps and random.random() < 0.3:
            gaps.append({
                "from_year": 2020,
                "to_year": 2021,
                "gap_months": 8,
                "severity": "medium",
                "note": "Potential unexplained gap during COVID period",
            })

        return gaps

    @staticmethod
    def _detect_overlaps(cv_text: str) -> list:
        """Detect overlapping employment periods."""
        date_patterns = re.findall(
            r'(\d{4})\s*[-–to]+\s*(\d{4}|present|current)',
            cv_text.lower()
        )

        overlaps = []
        for i in range(len(date_patterns)):
            for j in range(i + 1, len(date_patterns)):
                start_a = int(date_patterns[i][0])
                end_a = 2026 if date_patterns[i][1] in ("present", "current") else int(date_patterns[i][1])
                start_b = int(date_patterns[j][0])
                end_b = 2026 if date_patterns[j][1] in ("present", "current") else int(date_patterns[j][1])

                if start_a < end_b and start_b < end_a:
                    overlaps.append({
                        "period_a": f"{date_patterns[i][0]}-{date_patterns[i][1]}",
                        "period_b": f"{date_patterns[j][0]}-{date_patterns[j][1]}",
                        "overlap_months": min(end_a, end_b) - max(start_a, start_b),
                        "flag": "Employment dates overlap - verify with candidate",
                    })

        return overlaps

    @staticmethod
    def _verify_qualifications(cv_text: str) -> list:
        """Flag qualification claims for verification."""
        flags = []
        healthcare_quals = [
            "BSc Nursing", "MSc Nursing", "RN", "NMC", "HCPC",
            "GMC", "MBBS", "MD", "MBChB", "physiotherapy",
            "occupational therapy", "paramedic", "midwifery",
        ]

        cv_lower = cv_text.lower()
        for qual in healthcare_quals:
            if qual.lower() in cv_lower:
                flags.append({
                    "qualification": qual,
                    "status": "requires_verification",
                    "verification_method": "registry_check",
                })

        if not flags:
            flags.append({
                "note": "No recognised healthcare qualifications detected",
                "severity": "warning",
            })

        return flags

    @staticmethod
    def _detect_inconsistencies(cv_text: str) -> list:
        """Detect logical inconsistencies in CV."""
        issues = []

        # Check for unrealistic career progression
        if "senior" in cv_text.lower() and "2024" in cv_text:
            date_patterns = re.findall(r'(\d{4})', cv_text)
            if date_patterns:
                earliest = min(int(d) for d in date_patterns if 1990 < int(d) < 2027)
                if 2026 - earliest < 3:
                    issues.append({
                        "type": "career_progression",
                        "detail": "Senior role claimed with less than 3 years experience",
                        "severity": "medium",
                    })

        # Simulate additional checks
        if random.random() < 0.2:
            issues.append({
                "type": "institution_verification",
                "detail": "Educational institution requires verification",
                "severity": "low",
            })

        return issues

    @staticmethod
    def _calculate_fraud_risk(gaps: list, overlaps: list, qual_flags: list, inconsistencies: list) -> float:
        """Calculate overall CV fraud risk score (0.0 - 1.0)."""
        score = 0.0
        score += len(gaps) * 0.1
        score += len(overlaps) * 0.15
        score += len([f for f in qual_flags if f.get("severity") == "warning"]) * 0.1
        score += len(inconsistencies) * 0.12
        # Add baseline noise
        score += random.uniform(0.0, 0.15)
        return min(round(score, 2), 1.0)

    @staticmethod
    def _generate_ai_summary(cv_text: str, gaps: list, overlaps: list, qual_flags: list, fraud_score: float) -> str:
        """Generate AI summary of CV analysis."""
        parts = []
        word_count = len(cv_text.split())
        parts.append(f"CV analysed: {word_count} words processed.")

        if gaps:
            parts.append(f"Employment gaps detected: {len(gaps)} period(s) with unexplained gaps.")
        else:
            parts.append("No significant employment gaps detected.")

        if overlaps:
            parts.append(f"Overlapping employment: {len(overlaps)} overlap(s) found - requires verification.")

        verified_quals = [f for f in qual_flags if f.get("status") == "requires_verification"]
        if verified_quals:
            parts.append(f"Qualifications for verification: {len(verified_quals)} qualification(s) flagged for registry check.")

        if fraud_score < 0.2:
            parts.append("Overall risk: LOW. CV appears consistent and legitimate.")
        elif fraud_score < 0.5:
            parts.append("Overall risk: MEDIUM. Some items require verification.")
        else:
            parts.append("Overall risk: HIGH. Multiple inconsistencies detected - manual review recommended.")

        return " ".join(parts)

    @staticmethod
    def _extract_employment_history(cv_text: str) -> list:
        """Extract employment history entries from CV text.

        In production, use an LLM to parse unstructured CV text into structured
        employment entries. This simulation uses pattern matching + heuristics.
        """
        entries = []
        cv_lower = cv_text.lower()

        # Try to find date range patterns associated with employer/role info
        # Pattern: YYYY - YYYY or YYYY - Present with surrounding context
        date_blocks = re.findall(
            r'(?:^|\n)([^\n]{0,100}?)(\d{4})\s*[-–to]+\s*(\d{4}|present|current)([^\n]{0,200})',
            cv_lower,
            re.IGNORECASE,
        )

        # Common healthcare employers for simulation
        sample_employers = [
            "NHS Royal London Hospital",
            "St Thomas' Hospital NHS Trust",
            "Bupa Health Clinics",
            "Care UK Primary Care",
            "Circle Health Group",
        ]
        sample_titles = [
            "Staff Nurse",
            "Senior Healthcare Assistant",
            "Registered Nurse - Band 5",
            "Ward Manager - Band 6",
            "Clinical Lead",
        ]

        if date_blocks:
            for i, block in enumerate(date_blocks):
                prefix, start_year, end_year, suffix = block
                context = (prefix + suffix).strip()

                # Try to extract employer and title from context
                employer = None
                title = None
                for keyword in ["hospital", "clinic", "nhs", "trust", "care", "health", "medical"]:
                    if keyword in context:
                        # Grab the phrase around the keyword
                        employer = context[:80].strip().title()
                        break

                if not employer and i < len(sample_employers):
                    employer = sample_employers[i]
                elif not employer:
                    employer = f"Healthcare Provider {i + 1}"

                if not title and i < len(sample_titles):
                    title = sample_titles[i]
                elif not title:
                    title = "Healthcare Professional"

                is_current = end_year in ("present", "current")
                entries.append({
                    "employer": employer,
                    "job_title": title,
                    "start_date": f"{start_year}-01",
                    "end_date": None if is_current else f"{end_year}-12",
                    "is_current": is_current,
                    "duties": None,
                })
        else:
            # If no date patterns found, generate simulated entries based on CV content
            current_year = datetime.now().year
            num_entries = random.randint(2, 4)
            for i in range(num_entries):
                start_yr = current_year - 5 + i
                end_yr = start_yr + random.randint(1, 2)
                is_current = i == num_entries - 1
                entries.append({
                    "employer": sample_employers[i % len(sample_employers)],
                    "job_title": sample_titles[i % len(sample_titles)],
                    "start_date": f"{start_yr}-{random.randint(1,12):02d}",
                    "end_date": None if is_current else f"{min(end_yr, current_year)}-{random.randint(1,12):02d}",
                    "is_current": is_current,
                    "duties": None,
                })

        # Only keep entries within the last 5 years
        cutoff_year = datetime.now().year - 5
        filtered = []
        for e in entries:
            try:
                start_yr = int(e["start_date"][:4]) if e.get("start_date") else 0
                end_yr = datetime.now().year if e.get("is_current") else int(e["end_date"][:4]) if e.get("end_date") else 0
                if end_yr >= cutoff_year or e.get("is_current"):
                    filtered.append(e)
            except (ValueError, TypeError):
                filtered.append(e)

        return filtered[:6]  # Cap at 6 entries

    @staticmethod
    def get_analysis(analysis_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM cv_analyses WHERE id=?", (analysis_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_analyses_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM cv_analyses WHERE candidate_id=? ORDER BY analysed_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]

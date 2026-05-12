"""
Compliance Engine - The Core
Rule-based compliance scoring with industry-configurable templates and audit logs.
"""
import json
import logging
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Rule-based compliance evaluation engine with industry template support."""

    # Default rules (Healthcare CQC) — used as fallback when no template is assigned
    DEFAULT_RULES = {
        "identity_verified": {"weight": 13, "required": True},
        "right_to_work_valid": {"weight": 13, "required": True},
        "dbs_valid": {"weight": 17, "required": True},
        "cv_validated": {"weight": 5, "required": False},
        "employment_verified": {"weight": 13, "required": True},
        "registration_active": {"weight": 9, "required": True},
        "references_verified": {"weight": 13, "required": True, "min_count": 2},
        "training_compliant": {"weight": 12, "required": True},
    }

    @staticmethod
    def _get_template_for_candidate(db, candidate_id: str) -> tuple:
        """Get the industry template for a candidate based on their agency assignment.
        Resolution chain: sub-account template → agency template → default template → hardcoded defaults.
        Returns (rules_dict, template_config, compliance_label, compliance_threshold)."""
        # Find the agency (and possibly sub-account) this candidate belongs to
        db.execute(
            "SELECT agency_id, invited_by_sub_account_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1",
            (candidate_id,),
        )
        agency_link = db.fetchone()

        if not agency_link:
            return ComplianceEngine.DEFAULT_RULES, {}, "CQC Ready", 95.0

        agency_link_data = dict(agency_link)
        template_id = None

        # 1. Check if the inviting sub-account has a specific industry template
        sub_account_id = agency_link_data.get("invited_by_sub_account_id")
        if sub_account_id:
            db.execute(
                "SELECT industry_template_id FROM agency_sub_accounts WHERE id=%s AND is_active=1",
                (sub_account_id,),
            )
            sub_acc = db.fetchone()
            if sub_acc and dict(sub_acc).get("industry_template_id"):
                template_id = dict(sub_acc)["industry_template_id"]

        # 2. Fall back to agency-level template
        if not template_id:
            db.execute(
                "SELECT industry_template_id FROM agencies WHERE id=%s",
                (agency_link_data["agency_id"],),
            )
            agency = db.fetchone()
            if agency and dict(agency).get("industry_template_id"):
                template_id = dict(agency)["industry_template_id"]

        # 3. Fall back to default template
        if not template_id:
            db.execute(
                "SELECT * FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
            )
            default_tmpl = db.fetchone()
            if not default_tmpl:
                return ComplianceEngine.DEFAULT_RULES, {}, "CQC Ready", 95.0
            template_id = dict(default_tmpl)["id"]
            template_data = dict(default_tmpl)
        else:
            template_data = None

        # Load the template
        if template_data is None:
            db.execute(
                "SELECT * FROM industry_templates WHERE id=%s AND is_active=1",
                (template_id,),
            )
            template_row = db.fetchone()
            if not template_row:
                return ComplianceEngine.DEFAULT_RULES, {}, "CQC Ready", 95.0
            template_data = dict(template_row)

        # Load checks for this template
        db.execute(
            "SELECT * FROM industry_template_checks WHERE template_id=%s AND is_enabled=1 ORDER BY sort_order ASC",
            (template_id,),
        )
        checks = db.fetchall()

        if not checks:
            return ComplianceEngine.DEFAULT_RULES, {}, "CQC Ready", 95.0

        rules = {}
        template_config = {}
        for c in checks:
            cd = dict(c)
            config = {}
            try:
                config = json.loads(cd["config"]) if cd["config"] else {}
            except (json.JSONDecodeError, TypeError):
                config = {}

            rules[cd["check_key"]] = {
                "weight": cd["weight"],
                "required": bool(cd["is_required"]),
                "label": cd["check_label"],
                **config,
            }
            template_config[cd["check_key"]] = config

        compliance_label = template_data.get("compliance_label", "Compliant")
        compliance_threshold = template_data.get("compliance_threshold", 95.0)

        return rules, template_config, compliance_label, compliance_threshold

    @staticmethod
    def evaluate_candidate(candidate_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Load template-specific rules
            rules, template_config, compliance_label, compliance_threshold = \
                ComplianceEngine._get_template_for_candidate(db, candidate_id)

            # Gather all check results
            db.execute(
                "SELECT * FROM identity_checks WHERE candidate_id=%s ORDER BY started_at DESC LIMIT 1",
                (candidate_id,),
            )
            identity = db.fetchone()

            db.execute(
                "SELECT * FROM right_to_work_checks WHERE candidate_id=%s ORDER BY checked_at DESC LIMIT 1",
                (candidate_id,),
            )
            rtw = db.fetchone()

            db.execute(
                "SELECT * FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC LIMIT 1",
                (candidate_id,),
            )
            dbs = db.fetchone()

            db.execute(
                "SELECT * FROM registration_checks WHERE candidate_id=%s ORDER BY last_checked DESC LIMIT 1",
                (candidate_id,),
            )
            reg = db.fetchone()

            db.execute(
                "SELECT * FROM references_ WHERE candidate_id=%s AND status='completed'",
                (candidate_id,),
            )
            refs = db.fetchall()

            db.execute(
                "SELECT * FROM cv_analyses WHERE candidate_id=%s ORDER BY analysed_at DESC LIMIT 1",
                (candidate_id,),
            )
            cv = db.fetchone()

            # Evaluate each rule based on template
            checks = {}
            audit_entries = []
            flags = []

            # Identity verification
            if "identity_verified" in rules:
                id_pass = identity and dict(identity).get("result") == "clear"
                checks["identity_verified"] = id_pass
                audit_entries.append({
                    "check": "identity_verification",
                    "result": "passed" if id_pass else "failed",
                    "timestamp": now,
                    "details": dict(identity)["result"] if identity else "not_submitted",
                })
                if not id_pass:
                    flags.append("Identity verification incomplete or failed")

            # Right to Work
            if "right_to_work_valid" in rules:
                rtw_config = template_config.get("right_to_work_valid", {})
                requires_imposter = rtw_config.get("requires_imposter_check", True)

                rtw_check_pass = rtw and dict(rtw).get("verified") == 1
                if requires_imposter:
                    db.execute(
                        "SELECT * FROM imposter_declarations WHERE candidate_id=%s ORDER BY created_at DESC LIMIT 1",
                        (candidate_id,),
                    )
                    imposter_decl = db.fetchone()
                    imposter_pass = imposter_decl is not None
                    rtw_pass = rtw_check_pass and imposter_pass
                else:
                    imposter_pass = True
                    imposter_decl = None
                    rtw_pass = rtw_check_pass

                checks["right_to_work_valid"] = rtw_pass
                rtw_details = dict(rtw)["result"] if rtw else "not_submitted"
                if rtw_check_pass and not imposter_pass:
                    rtw_details = "rtw_verified_awaiting_imposter_check"
                audit_entries.append({
                    "check": "right_to_work",
                    "result": "passed" if rtw_pass else "failed",
                    "timestamp": now,
                    "details": rtw_details,
                    "rtw_check_verified": rtw_check_pass,
                    "imposter_declaration_submitted": imposter_pass,
                    "imposter_declared_by": dict(imposter_decl)["declared_by_email"] if imposter_decl else None,
                    "imposter_declared_at": dict(imposter_decl)["created_at"] if imposter_decl else None,
                })
                if not rtw_pass:
                    if not rtw_check_pass:
                        flags.append("Right to Work verification incomplete or invalid")
                    if requires_imposter and not imposter_pass:
                        flags.append("Imposter check declaration not submitted by agency")

            # DBS Check — handle all possible DBS template keys
            # Templates may use: dbs_valid, dbs_enhanced, dbs_basic, dbs_standard, dbs_enhanced_barred
            DBS_TEMPLATE_KEYS = ("dbs_valid", "dbs_enhanced", "dbs_basic", "dbs_standard", "dbs_enhanced_barred")
            dbs_check_key = None
            for _dbs_key in DBS_TEMPLATE_KEYS:
                if _dbs_key in rules:
                    dbs_check_key = _dbs_key
                    break

            if dbs_check_key:
                dbs_config = template_config.get(dbs_check_key, {})
                dbs_level = dbs_config.get("level", "enhanced_barred")

                if dbs_level == "none":
                    checks[dbs_check_key] = True
                    audit_entries.append({
                        "check": "dbs_check", "result": "passed",
                        "timestamp": now, "details": "not_required_for_industry",
                    })
                else:
                    dbs_pass = dbs and dict(dbs).get("result") == "clear"
                    checks[dbs_check_key] = dbs_pass
                    audit_entries.append({
                        "check": "dbs_check",
                        "result": "passed" if dbs_pass else "failed",
                        "timestamp": now,
                        "details": dict(dbs)["result"] if dbs else "not_submitted",
                        "required_level": dbs_level,
                    })
                    if not dbs_pass:
                        dbs_result = dict(dbs)["result"] if dbs else "not_submitted"
                        if dbs_result == "has_information":
                            flags.append("DBS check returned information - requires review")
                        elif dbs_result == "flagged":
                            flags.append("DBS check flagged - DO NOT CLEAR")
                        else:
                            flags.append(f"DBS check incomplete (required: {dbs_level})")

            # Registration
            if "registration_active" in rules:
                reg_pass = reg and dict(reg).get("is_active") == 1
                checks["registration_active"] = reg_pass
                reg_result = dict(reg)["result"] if reg else "not_submitted"
                reg_config = template_config.get("registration_active", {})
                bodies = reg_config.get("bodies", [])
                audit_entries.append({
                    "check": "registration",
                    "result": "passed" if reg_pass else "failed",
                    "timestamp": now,
                    "details": reg_result,
                    "accepted_bodies": bodies,
                })
                if not reg_pass:
                    body_str = ", ".join(bodies) if bodies else "professional body"
                    flags.append(f"Professional registration not active ({body_str})")

            # References
            if "references_verified" in rules:
                ref_config = template_config.get("references_verified", {})
                min_refs = ref_config.get("min_count", rules.get("references_verified", {}).get("min_count", 2))
                completed_refs = len(refs)
                refs_pass = completed_refs >= min_refs
                checks["references_verified"] = refs_pass
                audit_entries.append({
                    "check": "references",
                    "result": "passed" if refs_pass else "failed",
                    "timestamp": now,
                    "details": f"{completed_refs} of {min_refs} required references completed",
                })
                if not refs_pass:
                    flags.append(f"References: {completed_refs}/{min_refs} completed")

            # CV Validation
            if "cv_validated" in rules:
                cv_pass = cv and dict(cv).get("fraud_risk_score", 1.0) < 0.5
                checks["cv_validated"] = cv_pass
                audit_entries.append({
                    "check": "cv_validation",
                    "result": "passed" if cv_pass else "failed",
                    "timestamp": now,
                    "details": f"Fraud risk: {dict(cv)['fraud_risk_score']}" if cv else "not_submitted",
                })
                if not cv_pass and cv:
                    flags.append(f"CV fraud risk score: {dict(cv)['fraud_risk_score']}")

            # Training Compliance — uses the training_courses catalogue for
            # matching (course_id first, then normalised name + aliases) and
            # respects the per-industry `training_policy`:
            #   - "pass_fail"       (default): all mandatory courses must be valid
            #   - "informational"   : certs recorded but don't block compliance
            if "training_compliant" in rules:
                from app.services.training_catalogue import build_matcher

                training_config = template_config.get("training_compliant", {})
                policy = training_config.get("policy", "pass_fail")
                if policy not in {"pass_fail", "informational"}:
                    policy = "pass_fail"

                # Resolve the industry template id for this candidate.
                # Wrapped in a SAVEPOINT so that if any query raises (e.g.
                # schema drift, missing column) we can rollback JUST this
                # sub-block without aborting the rest of the evaluation.
                template_id_for_courses = None
                _sp_ok = False
                try:
                    db.execute("SAVEPOINT sp_tpl_resolve")
                    _sp_ok = True
                    db.execute(
                        "SELECT agency_id, sub_account_id FROM agency_candidates "
                        "WHERE candidate_id=%s ORDER BY created_at DESC LIMIT 1",
                        (candidate_id,),
                    )
                    ac_row = db.fetchone()
                    if ac_row:
                        ac_d = dict(ac_row)
                        if ac_d.get("sub_account_id"):
                            db.execute(
                                "SELECT industry_template_id FROM agency_sub_accounts WHERE id=%s AND is_active=1",
                                (ac_d["sub_account_id"],),
                            )
                            sub_r = db.fetchone()
                            if sub_r and dict(sub_r).get("industry_template_id"):
                                template_id_for_courses = dict(sub_r)["industry_template_id"]
                        if not template_id_for_courses and ac_d.get("agency_id"):
                            db.execute(
                                "SELECT industry_template_id FROM agencies WHERE id=%s",
                                (ac_d["agency_id"],),
                            )
                            ag_r = db.fetchone()
                            if ag_r and dict(ag_r).get("industry_template_id"):
                                template_id_for_courses = dict(ag_r)["industry_template_id"]
                    if not template_id_for_courses:
                        db.execute(
                            "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
                        )
                        dr = db.fetchone()
                        if dr:
                            template_id_for_courses = dict(dr)["id"]
                    db.execute("RELEASE SAVEPOINT sp_tpl_resolve")
                except Exception:
                    if _sp_ok:
                        try:
                            db.execute("ROLLBACK TO SAVEPOINT sp_tpl_resolve")
                            db.execute("RELEASE SAVEPOINT sp_tpl_resolve")
                        except Exception:
                            pass
                    template_id_for_courses = None

                matcher = build_matcher(template_id_for_courses) if template_id_for_courses else {"courses": [], "by_id": {}, "by_name_norm": {}}

                mandatory_courses = [c for c in matcher["courses"] if c.get("is_mandatory")]
                # Legacy fallback: if no catalogue entries but template config
                # still lists certificate names, treat them as mandatory.
                if not mandatory_courses:
                    legacy_names = training_config.get("certificates", [])
                    mandatory_courses = [
                        {"id": None, "name": n, "aliases": [], "is_mandatory": True}
                        for n in legacy_names
                    ]

                training_certs = []
                _sp2_ok = False
                try:
                    db.execute("SAVEPOINT sp_training_certs")
                    _sp2_ok = True
                    db.execute(
                        "SELECT * FROM training_certificates WHERE candidate_id=%s",
                        (candidate_id,),
                    )
                    training_certs = [dict(c) for c in db.fetchall()]
                    db.execute("RELEASE SAVEPOINT sp_training_certs")
                except Exception:
                    if _sp2_ok:
                        try:
                            db.execute("ROLLBACK TO SAVEPOINT sp_training_certs")
                            db.execute("RELEASE SAVEPOINT sp_training_certs")
                        except Exception:
                            pass
                    training_certs = []

                # Index certs by resolved course id AND by normalised name so
                # we can check every mandatory course against the candidate's
                # submissions.
                from app.services.training_catalogue import resolve_cert_to_course, _normalise

                certs_by_course_id: dict[str, dict] = {}
                certs_by_name_norm: dict[str, dict] = {}
                for cert in training_certs:
                    matched = resolve_cert_to_course(cert, matcher) if matcher["by_id"] or matcher["by_name_norm"] else None
                    if matched and matched.get("id"):
                        certs_by_course_id[matched["id"]] = cert
                    n = _normalise(cert.get("certificate_name") or "")
                    if n:
                        certs_by_name_norm[n] = cert

                mandatory_valid = 0
                mandatory_expired = 0
                mandatory_missing: list[str] = []
                total_mandatory = len(mandatory_courses)

                for course in mandatory_courses:
                    cert = None
                    cid = course.get("id")
                    if cid and cid in certs_by_course_id:
                        cert = certs_by_course_id[cid]
                    else:
                        n = _normalise(course.get("name") or "")
                        if n and n in certs_by_name_norm:
                            cert = certs_by_name_norm[n]
                        if not cert:
                            for alias in course.get("aliases", []):
                                an = _normalise(alias)
                                if an and an in certs_by_name_norm:
                                    cert = certs_by_name_norm[an]
                                    break
                    if cert and cert.get("status") == "valid":
                        mandatory_valid += 1
                    elif cert and cert.get("status") == "expired":
                        mandatory_expired += 1
                    else:
                        mandatory_missing.append(course["name"])

                if total_mandatory == 0:
                    # No mandatory courses defined: training is automatically passing
                    training_pass = True
                elif len(training_certs) == 0:
                    training_pass = False
                else:
                    training_pass = mandatory_valid == total_mandatory

                # Informational policy: record but don't block overall compliance
                if policy == "informational":
                    checks["training_compliant"] = True
                    audit_result = "informational"
                else:
                    checks["training_compliant"] = training_pass
                    audit_result = "passed" if training_pass else "failed"

                if total_mandatory > 0 and len(training_certs) > 0:
                    detail = f"{mandatory_valid}/{total_mandatory} mandatory certificates valid"
                elif total_mandatory == 0:
                    detail = f"No mandatory courses configured — {len(training_certs)} certificate(s) on file"
                else:
                    detail = "No training certificates provided"

                audit_entries.append({
                    "check": "training_compliance",
                    "result": audit_result,
                    "policy": policy,
                    "timestamp": now,
                    "details": detail,
                })
                if not training_pass and policy == "pass_fail":
                    if len(training_certs) == 0 and total_mandatory > 0:
                        flags.append("Training: no training certificates provided by candidate")
                    else:
                        if mandatory_expired > 0:
                            flags.append(f"Training: {mandatory_expired} mandatory certificate(s) expired")
                        if mandatory_missing:
                            flags.append(
                                f"Training: missing {', '.join(mandatory_missing[:3])}"
                                f"{'...' if len(mandatory_missing) > 3 else ''}"
                            )
                elif policy == "informational" and (mandatory_expired > 0 or mandatory_missing):
                    # Surface as an advisory note but don't fail
                    advisory_bits = []
                    if mandatory_valid < total_mandatory:
                        advisory_bits.append(
                            f"{mandatory_valid}/{total_mandatory} mandatory courses valid"
                        )
                    if mandatory_expired > 0:
                        advisory_bits.append(f"{mandatory_expired} expired")
                    if advisory_bits:
                        flags.append("Training (informational): " + "; ".join(advisory_bits))

            # Employment Verification
            if "employment_verified" in rules:
                db.execute(
                    "SELECT * FROM employment_verifications WHERE candidate_id=%s AND status IN ('completed', 'verified')",
                    (candidate_id,),
                )
                emp_verifications = db.fetchall()
                db.execute(
                    "SELECT COUNT(*) as cnt FROM employment_history WHERE candidate_id=%s",
                    (candidate_id,),
                )
                emp_entries = db.fetchone()
                total_entries = dict(emp_entries)["cnt"] if emp_entries else 0
                verified_count = len(emp_verifications)
                emp_pass = total_entries > 0 and verified_count > 0
                checks["employment_verified"] = emp_pass
                audit_entries.append({
                    "check": "employment_verification",
                    "result": "passed" if emp_pass else "failed",
                    "timestamp": now,
                    "details": f"{verified_count} of {total_entries} employment entries verified",
                })
                if not emp_pass:
                    if total_entries == 0:
                        flags.append("No employment history entries added")
                    else:
                        flags.append(f"Employment: {verified_count}/{total_entries} verified")

            # Calculate compliance score (only from enabled checks in the template)
            score = 0.0
            total_weight = 0.0
            for check_name, passed in checks.items():
                if check_name in rules:
                    total_weight += rules[check_name]["weight"]
                    if passed:
                        score += rules[check_name]["weight"]

            # Normalise score to 0-100 if total weight != 100
            if total_weight > 0 and total_weight != 100:
                score = (score / total_weight) * 100

            # Round score to 1 decimal place
            score = round(score, 1)

            # Determine overall status using template threshold
            required_checks = [k for k, v in rules.items() if v.get("required", False)]
            all_required_pass = all(checks.get(c, False) for c in required_checks)

            if all_required_pass and score >= compliance_threshold:
                overall_status = "compliant"
            elif score >= 60:
                overall_status = "pending_review"
            elif any(checks.values()):
                overall_status = "in_progress"
            else:
                overall_status = "incomplete"

            cqc_ready = overall_status == "compliant"

            # Upsert compliance record
            db.execute(
                "SELECT id FROM compliance_records WHERE candidate_id=%s",
                (candidate_id,),
            )
            existing = db.fetchone()

            if existing:
                db.execute(
                    """UPDATE compliance_records SET
                       overall_status=%s, score=%s, identity_verified=%s,
                       right_to_work_valid=%s, dbs_valid=%s, registration_active=%s,
                       references_verified=%s, cv_validated=%s, employment_verified=%s,
                       training_compliant=%s,
                       flags=%s, audit_log=%s, last_evaluated=%s, cqc_ready=%s
                       WHERE candidate_id=%s""",
                    (
                        overall_status, score,
                        1 if checks.get("identity_verified") else 0,
                        1 if checks.get("right_to_work_valid") else 0,
                        1 if any(checks.get(k) for k in DBS_TEMPLATE_KEYS) else 0,
                        1 if checks.get("registration_active") else 0,
                        1 if checks.get("references_verified") else 0,
                        1 if checks.get("cv_validated") else 0,
                        1 if checks.get("employment_verified") else 0,
                        1 if checks.get("training_compliant") else 0,
                        json.dumps(flags),
                        json.dumps(audit_entries),
                        now,
                        1 if cqc_ready else 0,
                        candidate_id,
                    ),
                )
            else:
                db.execute(
                    """INSERT INTO compliance_records
                       (id, candidate_id, overall_status, score, identity_verified,
                        right_to_work_valid, dbs_valid, registration_active,
                        references_verified, cv_validated, employment_verified,
                        training_compliant,
                        flags, audit_log, last_evaluated, cqc_ready)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        generate_id(), candidate_id, overall_status, score,
                        1 if checks.get("identity_verified") else 0,
                        1 if checks.get("right_to_work_valid") else 0,
                        1 if any(checks.get(k) for k in DBS_TEMPLATE_KEYS) else 0,
                        1 if checks.get("registration_active") else 0,
                        1 if checks.get("references_verified") else 0,
                        1 if checks.get("cv_validated") else 0,
                        1 if checks.get("employment_verified") else 0,
                        1 if checks.get("training_compliant") else 0,
                        json.dumps(flags),
                        json.dumps(audit_entries),
                        now,
                        1 if cqc_ready else 0,
                    ),
                )

            # Check previous status to detect transition to compliant
            db.execute(
                "SELECT compliance_status, email, first_name, last_name FROM candidates WHERE id=%s",
                (candidate_id,),
            )
            cand_row = db.fetchone()
            prev_status = dict(cand_row).get("compliance_status") if cand_row else None
            cand_data = dict(cand_row) if cand_row else {}

            # Update candidate's compliance status
            db.execute(
                "UPDATE candidates SET compliance_score=%s, compliance_status=%s, updated_at=%s WHERE id=%s",
                (score, overall_status, now, candidate_id),
            )

            # Send vetting-complete emails when status transitions to compliant
            if overall_status == "compliant" and prev_status != "compliant":
                try:
                    from app.services.email_service import EmailService
                    cand_name = f"{cand_data.get('first_name', '')} {cand_data.get('last_name', '')}".strip() or "Candidate"
                    cand_email = cand_data.get("email", "")

                    # Get the agency(s) linked to this candidate
                    db.execute(
                        """SELECT a.email, a.name FROM agencies a
                           JOIN agency_candidates ac ON a.id = ac.agency_id
                           WHERE ac.candidate_id=%s""",
                        (candidate_id,),
                    )
                    agencies = [dict(r) for r in db.fetchall()]

                    agency_name = agencies[0]["name"] if agencies else "Your Agency"

                    # Email the candidate
                    if cand_email:
                        EmailService.send_vetting_complete_candidate(
                            cand_email, cand_name, agency_name, score,
                        )

                    # Email each linked agency
                    for ag in agencies:
                        if ag.get("email"):
                            EmailService.send_vetting_complete_agency(
                                ag["email"], ag["name"], cand_name, cand_email, score,
                            )

                    # In-app notifications
                    db.execute(
                        """INSERT INTO in_app_notifications
                           (id, user_id, user_type, title, message, notification_type, created_at)
                           VALUES (%s, %s, 'candidate', %s, %s, 'vetting_complete', %s)""",
                        (generate_id(), candidate_id,
                         "Vetting Complete",
                         "Your compliance vetting has been completed successfully. All checks are verified.",
                         now),
                    )
                    for ag in agencies:
                        db.execute(
                            """SELECT id FROM agencies WHERE email=%s""",
                            (ag["email"],),
                        )
                        ag_row = db.fetchone()
                        if ag_row:
                            db.execute(
                                """INSERT INTO in_app_notifications
                                   (id, user_id, user_type, title, message, notification_type, created_at)
                                   VALUES (%s, %s, 'agency', %s, %s, 'vetting_complete', %s)""",
                                (generate_id(), dict(ag_row)["id"],
                                 f"Vetting Complete — {cand_name}",
                                 f"All compliance checks for {cand_name} are now verified. Score: {score}%.",
                                 now),
                            )
                except Exception as e:
                    logger.warning("Failed to send vetting-complete emails for %s: %s", candidate_id, e)

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'compliance', %s, 'evaluated', 'compliance_engine', %s, %s)""",
                (
                    generate_id(), candidate_id,
                    json.dumps({
                        "score": score, "status": overall_status, "flags": len(flags),
                        "compliance_label": compliance_label, "threshold": compliance_threshold,
                        "template_checks": list(rules.keys()),
                    }),
                    now,
                ),
            )

            db.execute(
                "SELECT * FROM compliance_records WHERE candidate_id=%s",
                (candidate_id,),
            )
            row = db.fetchone()
            result = dict(row)
            result["compliance_label"] = compliance_label
            result["compliance_threshold"] = compliance_threshold
            result["template_checks"] = list(rules.keys())
            return result

    @staticmethod
    def get_compliance(candidate_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "SELECT * FROM compliance_records WHERE candidate_id=%s",
                (candidate_id,),
            )
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_audit_log(candidate_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

"""
Professional Registration Scrapers (HTTP-based)
Queries NMC, GMC, HCPC, GPhC public registers using HTTP requests + BeautifulSoup.
No Selenium/Chrome dependency - works on Railway and other headless servers.
"""
import json
import re
import time
import logging
import traceback
import random
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Shared session with realistic headers
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
})


def _random_delay(min_s=0.5, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))


def _make_result(body, registration_number, source):
    """Create a standard result dict."""
    return {
        "body": body,
        "registration_number": registration_number,
        "scrape_source": source,
        "registrant_name": "",
        "registration_status": "unknown",
        "expiry_date": "",
        "sanctions": [],
        "conditions": [],
        "raw_data": {},
        "success": False,
        "error": None,
    }


# -- NMC Register Scraper (HTTP) --

def scrape_nmc_register(registration_number: str) -> dict:
    """Query the NMC (Nursing and Midwifery Council) public register via HTTP."""
    result = _make_result("NMC", registration_number, "nmc_http")
    try:
        logger.info(f"NMC HTTP scrape for PIN: {registration_number}")

        query_url = "https://www.nmc.org.uk/registration/search-the-register/?query=" + registration_number
        _random_delay()
        resp = _SESSION.get(query_url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()

        result_elements = soup.select(
            ".search-results .result, .register-result, .search-result-item, "
            "table tbody tr, .card, .registrant-card, article"
        )
        pin_upper = registration_number.upper().strip()

        if result_elements:
            for el in result_elements:
                el_text = el.get_text()
                if pin_upper in el_text.upper() or len(result_elements) == 1:
                    name_el = el.select_one("h2, h3, .name, strong, a")
                    if name_el:
                        result["registrant_name"] = name_el.get_text(strip=True)
                    el_lower = el_text.lower()
                    status_map = {
                        "registered": "active",
                        "effective": "active",
                        "not currently practising": "not_practising",
                        "lapsed": "lapsed",
                        "removed": "removed",
                        "suspended": "suspended",
                        "struck off": "struck_off",
                        "caution": "caution",
                    }
                    for keyword, status in status_map.items():
                        if keyword in el_lower:
                            result["registration_status"] = status
                            break
                    date_match = re.search(
                        r'(?:expir|renewal|valid until)[\s:]*(\d{1,2}[\s/\-]\w+[\s/\-]\d{2,4})',
                        el_text, re.IGNORECASE,
                    )
                    if date_match:
                        result["expiry_date"] = date_match.group(1).strip()
                    sanction_keywords = [
                        "sanction", "conditions of practice", "suspension",
                        "striking off", "caution order", "interim order",
                    ]
                    for sk in sanction_keywords:
                        if sk in el_lower:
                            result["sanctions"].append({
                                "type": sk.replace(" ", "_"),
                                "detail": "Found in register entry",
                            })
                    result["raw_data"]["matched_text"] = el_text[:500]
                    result["success"] = True
                    break

        if not result["success"] and pin_upper in page_text.upper():
            result["success"] = True
            result["raw_data"]["page_contains_pin"] = True
            if "registered" in page_text.lower() or "effective" in page_text.lower():
                result["registration_status"] = "active"

        if not result["success"]:
            result["error"] = "No results found for NMC PIN: " + registration_number
    except requests.RequestException as e:
        result["error"] = "HTTP error: " + str(e)
        logger.error(f"NMC HTTP scrape error: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NMC scrape error: {e}")
    return result


# -- GMC Register Scraper (HTTP) --

def scrape_gmc_register(registration_number: str) -> dict:
    """Query the GMC (General Medical Council) register via HTTP."""
    result = _make_result("GMC", registration_number, "gmc_http")
    try:
        search_url = (
            "https://www.gmc-uk.org/registration-and-licensing/the-medical-register"
            "?query=" + registration_number
        )
        logger.info(f"GMC HTTP scrape for ref: {registration_number}")
        _random_delay()
        resp = _SESSION.get(search_url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()
        page_lower = page_text.lower()

        name_el = soup.select_one(
            "h1.doctor-name, .doctor-details h1, h2.name, "
            ".registrant-name, .search-results h2, .search-results h3"
        )
        if name_el:
            name_text = name_el.get_text(strip=True)
            if name_text and "register" not in name_text.lower():
                result["registrant_name"] = name_text

        if "registered with a licence to practise" in page_lower:
            result["registration_status"] = "active"
        elif "registered without a licence to practise" in page_lower:
            result["registration_status"] = "registered_no_licence"
        elif "provisionally registered" in page_lower:
            result["registration_status"] = "provisional"
        elif "suspended" in page_lower and registration_number in page_text:
            result["registration_status"] = "suspended"
        elif "erased" in page_lower and registration_number in page_text:
            result["registration_status"] = "removed"

        search_results = soup.select(
            ".search-result, .doctor-result, .result-item, article"
        )
        for sr in search_results:
            sr_text = sr.get_text()
            if registration_number in sr_text:
                result["raw_data"]["search_result"] = sr_text[:500]
                if not result["registrant_name"]:
                    nc = sr.select_one("a, strong, h2, h3")
                    if nc:
                        result["registrant_name"] = nc.get_text(strip=True)
                result["success"] = True
                break

        ftp_keywords = [
            "conditions", "suspension", "undertakings", "warning", "erasure",
        ]
        for kw in ftp_keywords:
            if kw in page_lower and registration_number in page_text:
                idx = page_lower.index(kw)
                context = page_text[max(0, idx - 50):idx + 150].strip()
                result["sanctions"].append({
                    "type": "ftp_" + kw,
                    "detail": context[:300],
                })

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True
        elif registration_number in page_text:
            result["success"] = True
            result["raw_data"]["page_contains_number"] = True
        else:
            result["error"] = "No results found for GMC ref: " + registration_number
    except requests.RequestException as e:
        result["error"] = "HTTP error: " + str(e)
        logger.error(f"GMC HTTP scrape error: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"GMC scrape error: {e}")
    return result


# -- HCPC Register Scraper (HTTP) --

def scrape_hcpc_register(registration_number: str) -> dict:
    """Query the HCPC (Health and Care Professions Council) register via HTTP."""
    result = _make_result("HCPC", registration_number, "hcpc_http")
    try:
        search_url = (
            "https://www.hcpc-uk.org/check-the-register/"
            "?query=" + registration_number
        )
        logger.info(f"HCPC HTTP scrape for reg: {registration_number}")
        _random_delay()
        resp = _SESSION.get(search_url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()

        detail_rows = soup.select(
            "dl dt, dl dd, .detail-row, table tr, .info-row, .field-item"
        )
        current_label = ""
        for el in detail_rows:
            text = el.get_text(strip=True)
            tag = el.name
            classes = " ".join(el.get("class", []))
            if tag == "dt" or "label" in classes:
                current_label = text.lower()
            elif current_label:
                if "name" in current_label and not result["registrant_name"]:
                    result["registrant_name"] = text
                elif "status" in current_label or "registration" in current_label:
                    tl = text.lower()
                    if "registered" in tl:
                        result["registration_status"] = "active"
                    elif "suspended" in tl:
                        result["registration_status"] = "suspended"
                    elif "struck off" in tl:
                        result["registration_status"] = "struck_off"
                elif "expir" in current_label or "renewal" in current_label:
                    result["expiry_date"] = text
                elif "profession" in current_label:
                    result["raw_data"]["profession"] = text
                current_label = ""

        page_lower = page_text.lower()
        if result["registration_status"] == "unknown":
            if "registered" in page_lower and registration_number in page_text:
                result["registration_status"] = "active"

        sanction_keywords = [
            "conditions of practice", "suspension", "striking off", "caution",
        ]
        for sk in sanction_keywords:
            if sk in page_lower:
                result["sanctions"].append({
                    "type": sk.replace(" ", "_"),
                    "detail": "Found in HCPC register entry",
                })

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True
        elif registration_number in page_text:
            result["success"] = True
            result["raw_data"]["page_contains_number"] = True
        else:
            result["error"] = "No results found for HCPC reg: " + registration_number
    except requests.RequestException as e:
        result["error"] = "HTTP error: " + str(e)
        logger.error(f"HCPC HTTP scrape error: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"HCPC scrape error: {e}")
    return result


# -- GPhC Register Scraper (HTTP) --

def scrape_gphc_register(registration_number: str) -> dict:
    """Query the GPhC (General Pharmaceutical Council) register via HTTP."""
    result = _make_result("GPhC", registration_number, "gphc_http")
    try:
        search_url = (
            "https://www.pharmacyregulation.org/registers/pharmacist"
            "/registrationnumber/" + registration_number
        )
        logger.info(f"GPhC HTTP scrape for reg: {registration_number}")
        _random_delay()
        resp = _SESSION.get(search_url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()

        name_el = soup.select_one(
            "h1.page-title, .registrant-name, h2, .views-field-title"
        )
        if name_el:
            name_text = name_el.get_text(strip=True)
            if (name_text
                    and "register" not in name_text.lower()
                    and "search" not in name_text.lower()):
                result["registrant_name"] = name_text

        fields = soup.select(
            ".field, .views-field, dl dt, dl dd, .detail, tr td, .field-item"
        )
        for i, field in enumerate(fields):
            text = field.get_text(strip=True).lower()
            if "name" in text and i + 1 < len(fields):
                next_text = fields[i + 1].get_text(strip=True)
                if next_text and not result["registrant_name"]:
                    result["registrant_name"] = next_text
            elif "status" in text and i + 1 < len(fields):
                status_text = fields[i + 1].get_text(strip=True).lower()
                if "registered" in status_text:
                    result["registration_status"] = "active"
                elif "removed" in status_text:
                    result["registration_status"] = "removed"
                elif "suspended" in status_text:
                    result["registration_status"] = "suspended"

        page_lower = page_text.lower()
        ftp_keywords = [
            "conditions", "suspension order", "removal",
            "warning", "undertaking",
        ]
        for kw in ftp_keywords:
            if kw in page_lower:
                idx = page_lower.index(kw)
                context = page_text[max(0, idx - 50):idx + 100].strip()
                result["sanctions"].append({
                    "type": kw.replace(" ", "_"),
                    "detail": context[:300],
                })

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True
        elif registration_number in page_text:
            result["success"] = True
            result["raw_data"]["page_contains_number"] = True
        else:
            result["error"] = "No results found for GPhC reg: " + registration_number
    except requests.RequestException as e:
        result["error"] = "HTTP error: " + str(e)
        logger.error(f"GPhC HTTP scrape error: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"GPhC scrape error: {e}")
    return result


# -- Master Registration Scraper --

SCRAPER_MAP = {
    "NMC": scrape_nmc_register,
    "GMC": scrape_gmc_register,
    "HCPC": scrape_hcpc_register,
    "GPHC": scrape_gphc_register,
    "GPhC": scrape_gphc_register,
}


def scrape_registration(body: str, registration_number: str) -> dict:
    """Run the appropriate registration scraper for the given body."""
    scraper = SCRAPER_MAP.get(body.upper(), SCRAPER_MAP.get(body))
    if not scraper:
        return {
            "body": body,
            "registration_number": registration_number,
            "scrape_source": "unsupported",
            "success": False,
            "error": (
                "No scraper for body: " + body
                + ". Supported: NMC, GMC, HCPC, GPhC"
            ),
        }
    return scraper(registration_number)

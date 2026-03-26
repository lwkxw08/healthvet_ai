"""
Professional Registration Scrapers
Real headless Selenium scrapers for NMC, GMC, HCPC, GPhC public registers.
Used to verify healthcare professional registrations against live public data.
"""
import json
import re
import time
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _get_headless_driver():
    """Create a headless Chrome/Selenium driver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(5)
    return driver


def _random_delay(min_s=1.0, max_s=3.0):
    import random
    time.sleep(random.uniform(min_s, max_s))


# ── NMC Register Scraper ──────────────────────────────────────────────

def scrape_nmc_register(registration_number: str) -> dict:
    """
    Scrape the NMC (Nursing and Midwifery Council) public register.
    URL: https://www.nmc.org.uk/registration/search-the-register/
    Searches by PIN (registration number).
    """
    result = {
        "body": "NMC",
        "registration_number": registration_number,
        "scrape_source": "nmc_register",
        "registrant_name": "",
        "registration_status": "unknown",
        "expiry_date": "",
        "sanctions": [],
        "conditions": [],
        "raw_data": {},
        "success": False,
        "error": None,
    }

    driver = None
    try:
        driver = _get_headless_driver()

        # Navigate to NMC search
        url = f"https://www.nmc.org.uk/registration/search-the-register/?query={registration_number}"
        logger.info(f"Scraping NMC register for: {registration_number}")
        driver.get(url)
        _random_delay(2.0, 4.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = soup.get_text()

        # Look for search results
        # NMC shows results in a table or card format
        result_cards = soup.select(".search-results .result, .register-result, table tbody tr, .card")

        if not result_cards:
            # Try finding any element with the registration number
            if registration_number.upper() in page_text.upper():
                result["raw_data"]["page_contains_number"] = True
            else:
                result["error"] = "No results found for this registration number"
                return result

        # Parse the first matching result
        for card in result_cards:
            card_text = card.get_text()
            if registration_number.upper() in card_text.upper() or len(result_cards) == 1:
                # Extract name
                name_el = card.select_one("h2, h3, .name, td:first-child, strong")
                if name_el:
                    result["registrant_name"] = name_el.get_text(strip=True)

                # Extract status
                status_keywords = {
                    "registered": "active",
                    "active": "active",
                    "lapsed": "lapsed",
                    "removed": "removed",
                    "suspended": "suspended",
                    "struck off": "struck_off",
                    "caution": "caution",
                }
                card_text_lower = card_text.lower()
                for keyword, status in status_keywords.items():
                    if keyword in card_text_lower:
                        result["registration_status"] = status
                        break

                # Extract expiry/renewal date
                date_patterns = [
                    r'(?:expir|renewal|renew|valid until|registration expires?)[\s:]+(\d{1,2}[\s/\-]\w+[\s/\-]\d{2,4})',
                    r'(\d{1,2}\s+\w+\s+\d{4})',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, card_text, re.IGNORECASE)
                    if match:
                        result["expiry_date"] = match.group(1).strip()
                        break

                # Check for sanctions/conditions
                sanction_keywords = ["sanction", "conditions of practice", "suspension", "striking off", "caution order", "interim order"]
                for sk in sanction_keywords:
                    if sk in card_text_lower:
                        result["sanctions"].append({
                            "type": sk.replace(" ", "_"),
                            "detail": f"Found reference to '{sk}' in register entry",
                        })

                result["raw_data"]["card_text"] = card_text[:1000]
                result["success"] = True
                break

        # If we didn't find specific status, check page-level indicators
        if result["registration_status"] == "unknown" and result["success"]:
            if "registered" in page_text.lower():
                result["registration_status"] = "active"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NMC scrape error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# ── GMC Register Scraper ──────────────────────────────────────────────

def scrape_gmc_register(registration_number: str) -> dict:
    """
    Scrape the GMC (General Medical Council) public register.
    URL: https://www.gmc-uk.org/registration-and-licensing/the-medical-register
    The GMC has a structured search by GMC reference number.
    """
    result = {
        "body": "GMC",
        "registration_number": registration_number,
        "scrape_source": "gmc_register",
        "registrant_name": "",
        "registration_status": "unknown",
        "expiry_date": "",
        "sanctions": [],
        "conditions": [],
        "raw_data": {},
        "success": False,
        "error": None,
    }

    driver = None
    try:
        driver = _get_headless_driver()

        # GMC register search
        url = f"https://www.gmc-uk.org/registration-and-licensing/the-medical-register/a-]doctor-on-the-medical-register?query={registration_number}"
        logger.info(f"Scraping GMC register for: {registration_number}")
        driver.get(url)
        _random_delay(2.0, 4.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = soup.get_text()

        # GMC shows doctor details on a result page
        # Look for doctor name and registration details
        name_el = soup.select_one("h1.doctor-name, .doctor-details h1, h2.name, .registrant-name")
        if name_el:
            result["registrant_name"] = name_el.get_text(strip=True)

        # Look for registration status
        status_el = soup.select_one(".registration-status, .status, .reg-status")
        if status_el:
            status_text = status_el.get_text(strip=True).lower()
            if "registered" in status_text or "licence to practise" in status_text:
                result["registration_status"] = "active"
            elif "suspended" in status_text:
                result["registration_status"] = "suspended"
            elif "erased" in status_text or "removed" in status_text:
                result["registration_status"] = "removed"
        else:
            # Fallback: check page text
            page_lower = page_text.lower()
            if "registered with a licence to practise" in page_lower:
                result["registration_status"] = "active"
            elif "registered without a licence to practise" in page_lower:
                result["registration_status"] = "registered_no_licence"
            elif "provisionally registered" in page_lower:
                result["registration_status"] = "provisional"

        # Check for fitness to practise history
        ftp_section = soup.select_one(".fitness-to-practise, .ftp-history, #ftp")
        if ftp_section:
            ftp_text = ftp_section.get_text()
            if any(w in ftp_text.lower() for w in ["conditions", "suspension", "undertakings", "warning"]):
                result["sanctions"].append({
                    "type": "fitness_to_practise",
                    "detail": ftp_text[:500].strip(),
                })

        # Search results fallback
        search_results = soup.select(".search-result, .doctor-result, tr")
        for sr in search_results:
            sr_text = sr.get_text()
            if registration_number in sr_text:
                result["raw_data"]["search_result"] = sr_text[:500]
                if not result["registrant_name"]:
                    name_candidate = sr.select_one("a, strong, td:first-child")
                    if name_candidate:
                        result["registrant_name"] = name_candidate.get_text(strip=True)
                result["success"] = True
                break

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True

        if not result["success"]:
            # Check if page has any content about the number
            if registration_number in page_text:
                result["raw_data"]["page_contains_number"] = True
                result["success"] = True
            else:
                result["error"] = "No results found for this GMC number"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"GMC scrape error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# ── HCPC Register Scraper ──────────────────────────────────────────────

def scrape_hcpc_register(registration_number: str) -> dict:
    """
    Scrape the HCPC (Health and Care Professions Council) public register.
    URL: https://www.hcpc-uk.org/check-the-register/
    """
    result = {
        "body": "HCPC",
        "registration_number": registration_number,
        "scrape_source": "hcpc_register",
        "registrant_name": "",
        "registration_status": "unknown",
        "expiry_date": "",
        "sanctions": [],
        "conditions": [],
        "raw_data": {},
        "success": False,
        "error": None,
    }

    driver = None
    try:
        driver = _get_headless_driver()

        # HCPC online register search
        url = f"https://www.hcpc-uk.org/check-the-register/by-registration-number/?query={registration_number}"
        logger.info(f"Scraping HCPC register for: {registration_number}")
        driver.get(url)
        _random_delay(2.0, 4.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = soup.get_text()

        # HCPC shows registrant details
        # Look for name
        name_el = soup.select_one("h1, h2, .registrant-name, .name")
        if name_el:
            name_text = name_el.get_text(strip=True)
            # Filter out generic page titles
            if name_text and "check the register" not in name_text.lower() and "HCPC" not in name_text:
                result["registrant_name"] = name_text

        # Look for registration details
        detail_rows = soup.select("dl dt, dl dd, .detail-row, table tr, .info-row")
        current_label = ""
        for el in detail_rows:
            text = el.get_text(strip=True)
            if el.name == "dt" or "label" in (el.get("class") or []):
                current_label = text.lower()
            elif current_label:
                if "name" in current_label and not result["registrant_name"]:
                    result["registrant_name"] = text
                elif "status" in current_label or "registration" in current_label:
                    if "registered" in text.lower():
                        result["registration_status"] = "active"
                    elif "suspended" in text.lower():
                        result["registration_status"] = "suspended"
                    elif "struck off" in text.lower():
                        result["registration_status"] = "struck_off"
                elif "expir" in current_label or "renewal" in current_label:
                    result["expiry_date"] = text
                elif "profession" in current_label:
                    result["raw_data"]["profession"] = text
                current_label = ""

        # Check for sanctions
        sanctions_section = soup.select_one(".sanctions, .fitness-to-practise, #sanctions")
        if sanctions_section:
            sanctions_text = sanctions_section.get_text(strip=True)
            if sanctions_text and len(sanctions_text) > 10:
                result["sanctions"].append({
                    "type": "fitness_to_practise",
                    "detail": sanctions_text[:500],
                })

        # Fallback: check page text for status
        if result["registration_status"] == "unknown":
            page_lower = page_text.lower()
            if "your search returned" in page_lower and registration_number.lower() in page_lower:
                result["success"] = True
                if "registered" in page_lower:
                    result["registration_status"] = "active"

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True
        elif registration_number in page_text:
            result["success"] = True
            result["raw_data"]["page_contains_number"] = True
        else:
            result["error"] = "No results found for this HCPC number"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"HCPC scrape error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# ── GPhC Register Scraper ──────────────────────────────────────────────

def scrape_gphc_register(registration_number: str) -> dict:
    """
    Scrape the GPhC (General Pharmaceutical Council) public register.
    URL: https://www.pharmacyregulation.org/registers/pharmacist
    """
    result = {
        "body": "GPhC",
        "registration_number": registration_number,
        "scrape_source": "gphc_register",
        "registrant_name": "",
        "registration_status": "unknown",
        "expiry_date": "",
        "sanctions": [],
        "conditions": [],
        "raw_data": {},
        "success": False,
        "error": None,
    }

    driver = None
    try:
        driver = _get_headless_driver()

        # GPhC register search
        url = f"https://www.pharmacyregulation.org/registers/pharmacist/registrationnumber/{registration_number}"
        logger.info(f"Scraping GPhC register for: {registration_number}")
        driver.get(url)
        _random_delay(2.0, 4.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_text = soup.get_text()

        # Parse registrant details
        # GPhC typically shows name, registration number, status in a structured format
        name_el = soup.select_one("h1.page-title, .registrant-name, h2")
        if name_el:
            name_text = name_el.get_text(strip=True)
            if name_text and "register" not in name_text.lower() and "search" not in name_text.lower():
                result["registrant_name"] = name_text

        # Parse detail fields
        fields = soup.select(".field, .views-field, dl dt, dl dd, .detail, tr td")
        for i, field in enumerate(fields):
            text = field.get_text(strip=True).lower()
            if "registration number" in text and i + 1 < len(fields):
                pass  # Already have it
            elif "name" in text and i + 1 < len(fields):
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

        # Check for fitness to practise
        ftp_keywords = ["conditions", "suspension order", "removal", "warning", "undertaking"]
        page_lower = page_text.lower()
        for kw in ftp_keywords:
            if kw in page_lower:
                # Find context around the keyword
                idx = page_lower.index(kw)
                context = page_text[max(0, idx - 50):idx + 100].strip()
                result["sanctions"].append({
                    "type": kw.replace(" ", "_"),
                    "detail": context,
                })

        if result["registrant_name"] or result["registration_status"] != "unknown":
            result["success"] = True
        elif registration_number in page_text:
            result["success"] = True
            result["raw_data"]["page_contains_number"] = True
        else:
            result["error"] = "No results found for this GPhC number"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"GPhC scrape error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# ── Master Registration Scraper ──────────────────────────────────────

SCRAPER_MAP = {
    "NMC": scrape_nmc_register,
    "GMC": scrape_gmc_register,
    "HCPC": scrape_hcpc_register,
    "GPhC": scrape_gphc_register,
}


def scrape_registration(body: str, registration_number: str) -> dict:
    """Run the appropriate registration scraper for the given body."""
    scraper = SCRAPER_MAP.get(body.upper())
    if not scraper:
        return {
            "body": body,
            "registration_number": registration_number,
            "scrape_source": "unsupported",
            "success": False,
            "error": f"No scraper available for registration body: {body}. Supported: {', '.join(SCRAPER_MAP.keys())}",
        }
    return scraper(registration_number)

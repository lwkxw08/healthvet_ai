"""
Lead Generation Scrapers
Multi-source scraping for recruitment agency leads.
Sources: AgencyCentral (all industries), Indeed, CQC API, NHS Jobs.
Two-stage: directory scrape + agency website follow-through for contacts.
"""
import json
import re
import time
import random
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests as http_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Industry mapping for AgencyCentral URL slugs
AGENCY_CENTRAL_INDUSTRIES = {
    "health": "Health Care",
    "socialcare": "Social Care",
    "construction": "Construction",
    "education": "Education",
    "accounting": "Accounting & Finance",
    "admin": "Administration",
    "custservcallcentre": "Call Centre / Customer Service",
    "catering": "Catering & Hospitality",
    "creative": "Creative / Design",
    "driving": "Driving",
    "engineering": "Engineering",
    "food": "Food & Drink",
    "IT": "IT",
    "industrial": "Industrial",
    "manufacture": "Manufacturing / Production",
    "mediapr": "Media",
    "retail": "Retail",
    "sales": "Sales",
    "legal": "Legal",
    "science": "Science",
    "security": "Security",
    "telecomms": "Telecoms",
    "energy": "Energy & Utilities",
}


def _get_headless_driver():
    """Create a headless Chrome/Selenium driver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

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
    """Random delay to avoid rate limiting."""
    time.sleep(random.uniform(min_s, max_s))


def _extract_emails(text: str) -> list:
    """Extract email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


def _extract_phones(text: str) -> list:
    """Extract UK phone numbers from text."""
    patterns = [
        r'(?:\+44|0)\s*\d[\d\s\-]{8,12}\d',
        r'(?:\+44|0)\d{10,11}',
        r'\d{3,5}\s\d{3}\s\d{3,4}',
    ]
    phones = set()
    for p in patterns:
        for m in re.findall(p, text):
            cleaned = re.sub(r'[\s\-]', '', m)
            if len(cleaned) >= 10:
                phones.add(cleaned)
    return list(phones)


# ── AgencyCentral Scraper ──────────────────────────────────────────

_AC_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.agencycentral.co.uk/",
    "Accept": "application/json",
}


def _extract_slug_from_profile_url(profile_url: str) -> str:
    """Extract the agency slug from an AgencyCentral profile URL."""
    # URL format: /recruitment-agency/{name-slug}/{tag}
    parts = profile_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-1]  # e.g. 'uk_opencareservicesltd'
    return ""


def _fetch_agency_api_data(slug: str) -> dict:
    """Fetch agency data from AgencyCentral's internal API."""
    if not slug:
        return {}
    try:
        resp = http_requests.get(
            f"https://www.agencycentral.co.uk/api/agency/{slug}",
            headers=_AC_API_HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("agency", {})
    except Exception as e:
        logger.debug(f"API fetch failed for {slug}: {e}")
    return {}


def _enrich_lead_from_profile(driver, lead: dict) -> None:
    """
    Stage 1.5: Visit the AgencyCentral profile page and click contact
    buttons to reveal website URL, email, and phone number.
    """
    profile_url = lead.get("source_url", "")
    if not profile_url:
        return

    try:
        driver.get(profile_url)
        _random_delay(1.5, 3.0)

        # Click each contact button and check what gets revealed.
        # AgencyCentral uses React; buttons reveal content via state.
        for btn_label, field in [("Visit Website", "website"), ("Email Agency", "email"), ("Phone Number", "phone")]:
            try:
                # Click the button via JS
                clicked = driver.execute_script(f'''
                    var btns = document.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {{
                        if (btns[i].textContent.trim().includes('{btn_label}')) {{
                            btns[i].click();
                            return true;
                        }}
                    }}
                    return false;
                ''')
                if clicked:
                    _random_delay(1.0, 2.0)

                    # Check for new window/tab (Visit Website may open one)
                    if field == "website":
                        handles = driver.window_handles
                        if len(handles) > 1:
                            driver.switch_to.window(handles[-1])
                            _random_delay(1.5, 2.5)
                            current_url = driver.current_url

                            # AgencyCentral shows an interstitial page asking
                            # for your company name with a "Skip this step"
                            # link. We need to click that to reach the real
                            # agency website.
                            if "agencycentral" in current_url:
                                try:
                                    # Try clicking "Skip this step" link
                                    skip_clicked = driver.execute_script('''
                                        var links = document.querySelectorAll('a');
                                        for (var i = 0; i < links.length; i++) {
                                            var txt = links[i].textContent.trim().toLowerCase();
                                            if (txt.includes('skip this step') || txt.includes('skip')) {
                                                links[i].click();
                                                return true;
                                            }
                                        }
                                        return false;
                                    ''')
                                    if skip_clicked:
                                        _random_delay(2.0, 3.5)
                                        # After skip, check if we're on a new
                                        # non-agencycentral URL or a new tab
                                        final_handles = driver.window_handles
                                        if len(final_handles) > len(handles):
                                            # Skip opened yet another tab
                                            driver.switch_to.window(final_handles[-1])
                                            _random_delay(1.0, 2.0)
                                        final_url = driver.current_url
                                        if final_url and "agencycentral" not in final_url and final_url.startswith("http"):
                                            lead["website"] = final_url
                                            logger.info(f"Found website via Skip this step: {final_url}")
                                    else:
                                        # Try finding a direct outbound link on the interstitial
                                        isoup = BeautifulSoup(driver.page_source, "html.parser")
                                        for a_tag in isoup.select("a[href]"):
                                            href = a_tag.get("href", "")
                                            if href.startswith("http") and "agencycentral" not in href:
                                                lead["website"] = href
                                                logger.info(f"Found website via interstitial link: {href}")
                                                break
                                except Exception as skip_err:
                                    logger.debug(f"Error handling interstitial: {skip_err}")
                            elif current_url and current_url.startswith("http"):
                                # Went directly to agency website (no interstitial)
                                lead["website"] = current_url
                                logger.info(f"Found website via direct tab: {current_url}")

                            # Close extra tabs and return to main window
                            for h in driver.window_handles[1:]:
                                try:
                                    driver.switch_to.window(h)
                                    driver.close()
                                except Exception:
                                    pass
                            driver.switch_to.window(driver.window_handles[0])

                    # Check page source for revealed contact info
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    page_text = soup.get_text()

                    if field == "email" and not lead.get("email"):
                        # Look for mailto links revealed after click
                        for a in soup.select('a[href^="mailto:"]'):
                            email_val = a["href"].replace("mailto:", "").split("?")[0].strip()
                            if email_val and "@" in email_val:
                                lead["email"] = email_val
                                break
                        if not lead.get("email"):
                            emails = _extract_emails(page_text)
                            if emails:
                                lead["email"] = emails[0]

                    if field == "phone" and not lead.get("phone"):
                        for a in soup.select('a[href^="tel:"]'):
                            phone_val = a["href"].replace("tel:", "").strip()
                            if phone_val:
                                lead["phone"] = re.sub(r'[\s\-()]', '', phone_val)
                                break
                        if not lead.get("phone"):
                            phones = _extract_phones(page_text)
                            if phones:
                                lead["phone"] = phones[0]

            except Exception as e:
                logger.debug(f"Error clicking {btn_label}: {e}")
                continue

        # Also extract social links from profile page
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            social = {}
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "linkedin.com" in href:
                    social["linkedin"] = href
                elif "twitter.com" in href or "x.com" in href:
                    social["twitter"] = href
                elif "facebook.com" in href and "agencycentral" not in href:
                    social["facebook"] = href
            if social:
                lead["social_links"] = social
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Error enriching from profile {profile_url}: {e}")


def scrape_agency_central(industry_slug: str, max_pages: int = 3, follow_websites: bool = True) -> list:
    """
    Scrape AgencyCentral directory for a given industry.
    Stage 1: Extract listings from directory pages.
    Stage 1.5: Enrich each lead via AgencyCentral API + profile page button clicks.
    Stage 2: Follow through to agency's own website for full contact info.
    """
    leads = []
    base_url = f"https://www.agencycentral.co.uk/agencysearch/{industry_slug}/agencysearch.htm"
    industry_name = AGENCY_CENTRAL_INDUSTRIES.get(industry_slug, industry_slug.title())

    driver = None
    try:
        driver = _get_headless_driver()

        # ── Stage 1: Scrape directory listings ──
        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}?page={page}"
            logger.info(f"[Stage 1] Scraping AgencyCentral page {page}: {url}")

            try:
                driver.get(url)
                _random_delay(1.5, 3.0)
            except Exception as e:
                logger.warning(f"Failed to load page {page}: {e}")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Find agency listings: <li> elements that contain an <h3> with
            # a link to /recruitment-agency/...
            agency_links = soup.select('h3 a[href*="/recruitment-agency/"]')
            if not agency_links:
                logger.info(f"No more listings on page {page}")
                break

            for link in agency_links:
                try:
                    # Walk up to the containing <li>
                    li = link
                    while li and li.name != "li":
                        li = li.parent
                    if not li:
                        li = link.parent  # fallback

                    lead = _parse_agency_central_listing(li, industry_name, industry_slug)
                    if lead:
                        leads.append(lead)
                except Exception as e:
                    logger.warning(f"Error parsing listing: {e}")
                    continue

            # Check if there's a next page
            next_link = soup.select_one(f'a[href*="page={page + 1}"]')
            if not next_link:
                break

        logger.info(f"[Stage 1] Found {len(leads)} agencies from listings")

        # ── Stage 1.5: Enrich via API + profile page ──
        for i, lead in enumerate(leads):
            slug = _extract_slug_from_profile_url(lead.get("source_url", ""))
            if slug:
                # Fetch enriched data from AgencyCentral API
                api_data = _fetch_agency_api_data(slug)
                if api_data:
                    if not lead.get("description") and api_data.get("BriefDescription"):
                        lead["description"] = api_data["BriefDescription"][:500]
                    if not lead.get("description") and api_data.get("Description"):
                        lead["description"] = api_data["Description"][:500]
                _random_delay(0.3, 0.8)

            # Visit profile page to click buttons and get contact details
            logger.info(f"[Stage 1.5] Enriching {i+1}/{len(leads)}: {lead.get('name')}")
            _enrich_lead_from_profile(driver, lead)
            _random_delay(1.0, 2.0)

        # ── Stage 2: Follow through to agency's own website ──
        if follow_websites:
            enriched_count = 0
            for lead in leads:
                if lead.get("website") and (not lead.get("email") or not lead.get("phone")):
                    try:
                        logger.info(f"[Stage 2] Scraping website: {lead['website']}")
                        contacts = _scrape_agency_website(driver, lead["website"])
                        if contacts.get("emails") and not lead.get("email"):
                            lead["email"] = contacts["emails"][0]
                            lead["all_emails"] = contacts["emails"]
                        if contacts.get("phones") and not lead.get("phone"):
                            lead["phone"] = contacts["phones"][0]
                            lead["all_phones"] = contacts["phones"]
                        if contacts.get("social_links"):
                            lead.setdefault("social_links", {}).update(contacts["social_links"])
                        enriched_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to scrape website {lead['website']}: {e}")
                    _random_delay(2.0, 4.0)
            logger.info(f"[Stage 2] Enriched {enriched_count} agencies from their websites")

    except Exception as e:
        logger.error(f"AgencyCentral scraper error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return leads


def _parse_agency_central_listing(li, industry_name: str, industry_slug: str) -> Optional[dict]:
    """Parse a single AgencyCentral listing <li> element."""
    name_el = li.select_one("h3")
    if not name_el:
        return None
    name = name_el.get_text(strip=True)
    if not name:
        return None

    # Profile link
    link_el = name_el.select_one("a")
    profile_url = ""
    if link_el and link_el.get("href"):
        href = link_el["href"]
        if not href.startswith("http"):
            href = "https://www.agencycentral.co.uk" + href
        profile_url = href

    # Description — get the <p> or <span> text block
    desc = ""
    desc_el = li.select_one("p.text-base span, p.text-base")
    if desc_el:
        desc = desc_el.get_text(strip=True)[:500]
    if not desc:
        texts = li.find_all(string=True, recursive=True)
        text_content = " ".join(t.strip() for t in texts if t.strip())
        desc_parts = []
        for child in li.children:
            if hasattr(child, 'name'):
                if child.name in ('h3', 'svg', 'button', 'ul'):
                    continue
                t = child.get_text(strip=True)
                if t and len(t) > 20:
                    desc_parts.append(t)
            elif isinstance(child, str) and child.strip() and len(child.strip()) > 20:
                desc_parts.append(child.strip())
        desc = " ".join(desc_parts)[:500] if desc_parts else ""

    text_content = " ".join(t.strip() for t in li.find_all(string=True, recursive=True) if t.strip())

    # Verified
    verified = bool("Verified" in text_content)

    # Has Visit Website button
    has_website_btn = bool(li.find("button", string=re.compile(r"Visit Website", re.I)))

    # Employment types
    emp_types = ""
    for text in li.find_all(string=True, recursive=True):
        t = text.strip()
        if "Permanent" in t or "Temporary" in t or "Contract" in t:
            emp_types = t[:100]
            break

    # Office location
    location = ""
    loc_matches = re.findall(r'(?:Office Locations?|Office)\s*(.+?)(?:Geographical|Employment|Salaries|Listed|$)', text_content, re.DOTALL)
    if loc_matches:
        location = loc_matches[0].strip()[:200]
    if not location:
        postcode = re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}', text_content)
        if postcode:
            idx = text_content.index(postcode.group())
            start = max(0, idx - 100)
            location = text_content[start:idx + len(postcode.group())].strip()[-200:]

    # Coverage
    coverage = ""
    cov_matches = re.findall(r'Geographical Coverage\s*(.+?)(?:Salaries|Listed|$)', text_content, re.DOTALL)
    if cov_matches:
        coverage = cov_matches[0].strip()[:200]

    # Salary range
    salary_range = ""
    sal_matches = re.findall(r'Salaries?\s+(?:from\s+)?(.+?)(?:Listed|$)', text_content, re.DOTALL)
    if sal_matches:
        salary_range = sal_matches[0].strip()[:100]

    # Listed since
    listed_since = ""
    ls_matches = re.findall(r'Listed since:\s*(.+?)$', text_content)
    if ls_matches:
        listed_since = ls_matches[0].strip()

    # Try to extract email from mailto links
    email = ""
    phone = ""
    mailto = li.select_one('a[href^="mailto:"]')
    if mailto:
        email = mailto["href"].replace("mailto:", "").strip()
    emails_in_text = _extract_emails(text_content)
    if emails_in_text and not email:
        email = emails_in_text[0]
    phones_in_text = _extract_phones(text_content)
    if phones_in_text and not phone:
        phone = phones_in_text[0]

    return {
        "name": name,
        "description": desc,
        "industry": industry_name,
        "industry_slug": industry_slug,
        "source": "agencycentral",
        "source_url": profile_url,
        "website": "",  # populated in stage 1.5 via profile page
        "email": email,
        "phone": phone,
        "location": location,
        "coverage": coverage,
        "employment_types": emp_types,
        "salary_range": salary_range,
        "listed_since": listed_since,
        "verified": verified,
        "has_website": has_website_btn,
    }


def _scrape_agency_website(driver, url: str) -> dict:
    """Stage 2: Scrape an agency's own website for contact information."""
    result = {"emails": [], "phones": [], "social_links": {}}

    if not url or not url.startswith("http"):
        return result

    try:
        driver.get(url)
        _random_delay(2.0, 4.0)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        page_text = soup.get_text()

        # Extract from homepage
        result["emails"].extend(_extract_emails(page_text))
        result["phones"].extend(_extract_phones(page_text))

        # Check mailto links
        for a in soup.select('a[href^="mailto:"]'):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            if email and "@" in email:
                result["emails"].append(email)

        # Check tel links
        for a in soup.select('a[href^="tel:"]'):
            phone = a["href"].replace("tel:", "").strip()
            if phone:
                result["phones"].append(re.sub(r'[\s\-()]', '', phone))

        # Social media links
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "linkedin.com" in href:
                result["social_links"]["linkedin"] = href
            elif "twitter.com" in href or "x.com" in href:
                result["social_links"]["twitter"] = href
            elif "facebook.com" in href:
                result["social_links"]["facebook"] = href

        # Try contact page
        contact_links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "").lower()
            text = a.get_text(strip=True).lower()
            if any(k in href for k in ["/contact", "/about", "/get-in-touch"]) or \
               any(k in text for k in ["contact", "get in touch"]):
                full_url = href
                if not full_url.startswith("http"):
                    if full_url.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        full_url = f"{parsed.scheme}://{parsed.netloc}{full_url}"
                    else:
                        full_url = url.rstrip("/") + "/" + full_url
                contact_links.append(full_url)

        # Visit up to 2 contact pages
        for clink in contact_links[:2]:
            try:
                driver.get(clink)
                _random_delay(1.5, 3.0)
                csoup = BeautifulSoup(driver.page_source, "html.parser")
                ctext = csoup.get_text()
                result["emails"].extend(_extract_emails(ctext))
                result["phones"].extend(_extract_phones(ctext))
                for a in csoup.select('a[href^="mailto:"]'):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if email and "@" in email:
                        result["emails"].append(email)
                for a in csoup.select('a[href^="tel:"]'):
                    phone = a["href"].replace("tel:", "").strip()
                    if phone:
                        result["phones"].append(re.sub(r'[\s\-()]', '', phone))
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Error scraping agency website {url}: {e}")

    # De-duplicate and filter junk
    result["emails"] = list(set(e.lower() for e in result["emails"]
                               if "@" in e and "." in e
                               and not e.endswith(".png") and not e.endswith(".jpg")
                               and "example.com" not in e and "sentry" not in e))
    result["phones"] = list(set(result["phones"]))
    return result


# ── Indeed Scraper ──────────────────────────────────────────────────

def scrape_indeed(search_term: str = "healthcare recruitment agency", location: str = "United Kingdom", max_pages: int = 2) -> list:
    """
    Scrape Indeed for recruitment agency job postings to identify agencies.
    Extracts company names and job details as leads.
    """
    leads = []
    driver = None

    try:
        driver = _get_headless_driver()
        base_url = "https://uk.indeed.com/jobs"

        for page in range(max_pages):
            start = page * 10
            params = f"?q={search_term.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start}"
            url = base_url + params
            logger.info(f"Scraping Indeed page {page + 1}: {url}")

            try:
                driver.get(url)
                _random_delay(2.0, 4.0)
            except Exception as e:
                logger.warning(f"Failed to load Indeed page {page + 1}: {e}")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Indeed job cards
            job_cards = soup.select('div.job_seen_beacon, div.jobsearch-ResultsList > div, td.resultContent')
            if not job_cards:
                # Try alternative selectors
                job_cards = soup.select('[data-jk], .result, .tapItem')

            if not job_cards:
                logger.info(f"No job cards found on Indeed page {page + 1}")
                break

            seen_companies = set()
            for card in job_cards:
                try:
                    # Company name
                    company_el = card.select_one('[data-testid="company-name"], .companyName, .company')
                    if not company_el:
                        continue
                    company = company_el.get_text(strip=True)
                    if not company or company in seen_companies:
                        continue
                    seen_companies.add(company)

                    # Job title
                    title_el = card.select_one('[data-testid="jobTitle"], .jobTitle, .title a, h2 a')
                    title = title_el.get_text(strip=True) if title_el else ""

                    # Location
                    loc_el = card.select_one('[data-testid="text-location"], .companyLocation, .location')
                    loc = loc_el.get_text(strip=True) if loc_el else ""

                    # Salary
                    sal_el = card.select_one('.salary-snippet, .estimated-salary, [data-testid="attribute_snippet_testid"]')
                    salary = sal_el.get_text(strip=True) if sal_el else ""

                    # Description snippet
                    desc_el = card.select_one('.job-snippet, .heading6, [data-testid="job-snippet"]')
                    desc = desc_el.get_text(strip=True) if desc_el else ""

                    # Job link
                    link_el = card.select_one('a[href*="/rc/clk"], a[href*="/viewjob"], h2 a, .title a')
                    job_url = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        if not href.startswith("http"):
                            href = "https://uk.indeed.com" + href
                        job_url = href

                    leads.append({
                        "name": company,
                        "description": f"{title} - {desc}"[:500] if title else desc[:500],
                        "industry": search_term,
                        "industry_slug": search_term.lower().replace(" ", "_"),
                        "source": "indeed",
                        "source_url": job_url,
                        "website": "",
                        "email": "",
                        "phone": "",
                        "location": loc,
                        "coverage": "",
                        "employment_types": "",
                        "salary_range": salary,
                        "listed_since": "",
                        "verified": False,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Indeed card: {e}")
                    continue

            _random_delay(2.0, 5.0)

    except Exception as e:
        logger.error(f"Indeed scraper error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return leads


# ── CQC API ─────────────────────────────────────────────────────────

def scrape_cqc_api(search_type: str = "care_homes", location: str = "", max_results: int = 100) -> list:
    """
    Query the CQC public API for healthcare providers.
    Free API, no authentication required.
    """
    import requests as req

    leads = []
    base_url = "https://api.cqc.org.uk/public/v1"

    try:
        # Search providers
        params = {
            "perPage": min(max_results, 500),
            "page": 1,
        }

        # Determine type filters
        if search_type == "care_homes":
            params["careHome"] = "Y"
        elif search_type == "domiciliary":
            params["serviceType"] = "Homecare agencies"

        url = f"{base_url}/providers"
        logger.info(f"Querying CQC API: {url} with params {params}")

        resp = req.get(url, params=params, timeout=30, headers={
            "User-Agent": "HealthVetAI/1.0 (compliance platform)",
        })
        resp.raise_for_status()
        data = resp.json()

        providers = data.get("providers", [])
        logger.info(f"CQC API returned {len(providers)} providers")

        for prov in providers[:max_results]:
            provider_id = prov.get("providerId", "")
            name = prov.get("providerName", "")
            if not name:
                continue

            # Get detailed info
            detail = {}
            try:
                detail_resp = req.get(f"{base_url}/providers/{provider_id}", timeout=15, headers={
                    "User-Agent": "HealthVetAI/1.0 (compliance platform)",
                })
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                _random_delay(0.3, 0.8)  # Rate limit respect
            except Exception:
                pass

            # Parse details
            address_parts = []
            for k in ["postalAddressLine1", "postalAddressLine2", "postalAddressTownCity", "postalAddressCounty", "postalCode"]:
                val = detail.get(k) or prov.get(k, "")
                if val:
                    address_parts.append(val)
            location_str = ", ".join(address_parts)

            phone = detail.get("mainPhoneNumber") or ""
            website = detail.get("website") or ""
            email = ""

            # CQC rating
            rating = ""
            if detail.get("currentRatings"):
                overall = detail["currentRatings"].get("overall", {})
                rating = overall.get("rating", "")

            # Inspection info
            last_inspection = detail.get("lastInspection", {})
            inspection_date = last_inspection.get("date", "") if isinstance(last_inspection, dict) else ""

            # Services
            services = []
            for svc in detail.get("regulatedActivities", []):
                if isinstance(svc, dict):
                    services.append(svc.get("name", ""))

            leads.append({
                "name": name,
                "description": f"CQC registered provider. Rating: {rating}. Services: {', '.join(services[:3])}"[:500],
                "industry": "Health Care",
                "industry_slug": "health",
                "source": "cqc",
                "source_url": f"https://www.cqc.org.uk/provider/{provider_id}",
                "website": website,
                "email": email,
                "phone": phone,
                "location": location_str,
                "coverage": "",
                "employment_types": "",
                "salary_range": "",
                "listed_since": "",
                "verified": True,
                "extra": {
                    "cqc_provider_id": provider_id,
                    "cqc_rating": rating,
                    "last_inspection": inspection_date,
                    "regulated_activities": services[:5],
                },
            })

    except Exception as e:
        logger.error(f"CQC API error: {e}\n{traceback.format_exc()}")

    return leads


# ── NHS Jobs Scraper ─────────────────────────────────────────────────

def scrape_nhs_jobs(search_term: str = "recruitment", max_pages: int = 2) -> list:
    """
    Scrape NHS Jobs for healthcare recruitment agencies.
    Extracts employers posting jobs to identify potential leads.
    """
    leads = []
    driver = None

    try:
        driver = _get_headless_driver()
        base_url = "https://www.jobs.nhs.uk/candidate/search/results"

        for page in range(1, max_pages + 1):
            url = f"{base_url}?keyword={search_term.replace(' ', '+')}&page={page}"
            logger.info(f"Scraping NHS Jobs page {page}: {url}")

            try:
                driver.get(url)
                _random_delay(2.0, 4.0)
            except Exception as e:
                logger.warning(f"Failed to load NHS Jobs page {page}: {e}")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            page_text = soup.get_text()

            # NHS Jobs uses various card structures
            job_cards = soup.select('[data-test="search-result"], .nhsuk-list-panel, .vacancy-card, li.nhsuk-list-panel__item')
            if not job_cards:
                # Try broader selectors
                job_cards = soup.select('.search-result, article, .result-item')

            if not job_cards:
                logger.info(f"No results on NHS Jobs page {page}")
                break

            seen_employers = set()
            for card in job_cards:
                try:
                    card_text = card.get_text(strip=True)

                    # Employer name
                    employer_el = card.select_one('.nhsuk-body-s, .employer, [data-test="search-result-employer"]')
                    if not employer_el:
                        # Try to find org name in text
                        employer_el = card.select_one('p, span')
                    employer = employer_el.get_text(strip=True) if employer_el else ""
                    if not employer or employer in seen_employers:
                        continue
                    seen_employers.add(employer)

                    # Job title
                    title_el = card.select_one('a, h2, h3, [data-test="search-result-job-title"]')
                    title = title_el.get_text(strip=True) if title_el else ""

                    # Location
                    loc_el = card.select_one('[data-test="search-result-location"], .location')
                    loc = loc_el.get_text(strip=True) if loc_el else ""

                    # Link
                    link_el = card.select_one('a[href]')
                    job_url = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        if not href.startswith("http"):
                            href = "https://www.jobs.nhs.uk" + href
                        job_url = href

                    leads.append({
                        "name": employer,
                        "description": f"NHS employer posting: {title}"[:500],
                        "industry": "Health Care (NHS)",
                        "industry_slug": "health",
                        "source": "nhs_jobs",
                        "source_url": job_url,
                        "website": "",
                        "email": "",
                        "phone": "",
                        "location": loc,
                        "coverage": "",
                        "employment_types": "",
                        "salary_range": "",
                        "listed_since": "",
                        "verified": True,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing NHS Jobs card: {e}")
                    continue

            _random_delay(2.0, 5.0)

    except Exception as e:
        logger.error(f"NHS Jobs scraper error: {e}\n{traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return leads


# ── Master Scrape Runner ─────────────────────────────────────────────

def run_scrape_job(source: str, config: dict) -> list:
    """Run a scrape job for the specified source and config."""
    if source == "agencycentral":
        return scrape_agency_central(
            industry_slug=config.get("industry_slug", "health"),
            max_pages=config.get("max_pages", 3),
            follow_websites=config.get("follow_websites", True),
        )
    elif source == "indeed":
        return scrape_indeed(
            search_term=config.get("search_term", "healthcare recruitment agency"),
            location=config.get("location", "United Kingdom"),
            max_pages=config.get("max_pages", 2),
        )
    elif source == "cqc":
        return scrape_cqc_api(
            search_type=config.get("search_type", "care_homes"),
            location=config.get("location", ""),
            max_results=config.get("max_results", 100),
        )
    elif source == "nhs_jobs":
        return scrape_nhs_jobs(
            search_term=config.get("search_term", "recruitment"),
            max_pages=config.get("max_pages", 2),
        )
    else:
        raise ValueError(f"Unknown scrape source: {source}")

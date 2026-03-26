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

def scrape_agency_central(industry_slug: str, max_pages: int = 3, follow_websites: bool = True) -> list:
    """
    Scrape AgencyCentral directory for a given industry.
    Stage 1: Extract listings from directory pages.
    Stage 2: Follow through to agency websites for contact info.
    """
    leads = []
    base_url = f"https://www.agencycentral.co.uk/agencysearch/{industry_slug}/agencysearch.htm"
    industry_name = AGENCY_CENTRAL_INDUSTRIES.get(industry_slug, industry_slug.title())

    driver = None
    try:
        driver = _get_headless_driver()

        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}?page={page}"
            logger.info(f"Scraping AgencyCentral page {page}: {url}")

            try:
                driver.get(url)
                _random_delay(1.5, 3.0)
            except Exception as e:
                logger.warning(f"Failed to load page {page}: {e}")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            listings = soup.select("ol > li")

            if not listings:
                logger.info(f"No more listings on page {page}")
                break

            for li in listings:
                try:
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

        # Stage 2: Follow through to agency websites for contact info
        if follow_websites:
            for lead in leads:
                if lead.get("website") and (not lead.get("email") or not lead.get("phone")):
                    try:
                        contacts = _scrape_agency_website(driver, lead["website"])
                        if contacts.get("emails") and not lead.get("email"):
                            lead["email"] = contacts["emails"][0]
                            lead["all_emails"] = contacts["emails"]
                        if contacts.get("phones") and not lead.get("phone"):
                            lead["phone"] = contacts["phones"][0]
                            lead["all_phones"] = contacts["phones"]
                        if contacts.get("social_links"):
                            lead["social_links"] = contacts["social_links"]
                    except Exception as e:
                        logger.warning(f"Failed to scrape website {lead['website']}: {e}")
                    _random_delay(2.0, 4.0)

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

    # Description
    desc = ""
    texts = li.find_all(string=True, recursive=True)
    text_content = " ".join(t.strip() for t in texts if t.strip())
    # Get text after the name and before the buttons
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

    # Verified
    verified = bool(li.select_one('svg') and "Verified" in text_content)

    # Employment types
    emp_types = ""
    for text in texts:
        if "Permanent" in text or "Temporary" in text or "Contract" in text:
            emp_types = text.strip()
            break

    # Office location
    location = ""
    loc_matches = re.findall(r'(?:Office Locations?|Office)\s*(.+?)(?:Geographical|Employment|Salaries|Listed|$)', text_content, re.DOTALL)
    if loc_matches:
        location = loc_matches[0].strip()[:200]
    # Fallback: look for text with postcode pattern
    if not location:
        postcode = re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}', text_content)
        if postcode:
            # Get surrounding text
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

    # Website - look for "Visit Website" button/link
    website = ""
    website_btn = li.find("button", string=re.compile(r"Visit Website", re.I))
    if website_btn:
        # The website might be in a nearby link
        pass  # Will be extracted from profile page or website follow-through

    # Try to extract email from mailto links
    email = ""
    phone = ""
    mailto = li.select_one('a[href^="mailto:"]')
    if mailto:
        email = mailto["href"].replace("mailto:", "").strip()

    # Try to extract from visible text
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
        "website": website,
        "email": email,
        "phone": phone,
        "location": location,
        "coverage": coverage,
        "employment_types": emp_types,
        "salary_range": salary_range,
        "listed_since": listed_since,
        "verified": verified,
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

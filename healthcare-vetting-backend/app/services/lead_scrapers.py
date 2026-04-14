"""
Lead Generation Scrapers
Multi-source scraping for recruitment agency leads.
Sources: AgencyCentral (all industries), Indeed, CQC API, NHS Jobs.
Uses pure HTTP requests approach - no Selenium/Chrome dependency required.
"""
import json
import re
import time
import random
import logging
import traceback
from typing import Optional
from urllib.parse import urlparse

import requests as http_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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


def _random_delay(min_s=1.0, max_s=3.0):
    """Random delay to avoid rate limiting."""
    time.sleep(random.uniform(min_s, max_s))


def _extract_emails(text):
    """Extract email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


def _extract_phones(text):
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


_AC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_AC_API_HEADERS = {
    "User-Agent": _AC_UA,
    "Referer": "https://www.agencycentral.co.uk/",
    "Accept": "application/json",
}


def _extract_slug_from_profile_url(profile_url):
    """Extract the agency slug from an AgencyCentral profile URL."""
    parts = profile_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-1]
    return ""


def _fetch_agency_api_data(slug):
    """Fetch agency data from AgencyCentral internal API."""
    if not slug:
        return {}
    try:
        resp = http_requests.get(
            f"https://www.agencycentral.co.uk/api/agency/{slug}",
            headers=_AC_API_HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("agency", {})
    except Exception as e:
        logger.debug(f"API fetch failed for {slug}: {e}")
    return {}


def _discover_agency_urls_from_sitemap():
    """Fetch all agency profile URLs from AgencyCentral sitemap."""
    try:
        resp = http_requests.get(
            "https://www.agencycentral.co.uk/sitemap.xml",
            headers={"User-Agent": _AC_UA},
            timeout=30,
        )
        resp.raise_for_status()
        urls = re.findall(
            r'<loc>(https://www\.agencycentral\.co\.uk/recruitment-agency/[^<]+)</loc>',
            resp.text,
        )
        logger.info(f"Sitemap: found {len(urls)} agency profile URLs")
        return urls
    except Exception as e:
        logger.warning(f"Failed to fetch sitemap: {e}")
        return []


def _extract_profile_data(profile_url):
    """
    Fetch an AgencyCentral profile page and extract agency + branch data
    from the embedded window.stores JSON object.
    """
    try:
        resp = http_requests.get(
            profile_url,
            headers={"User-Agent": _AC_UA},
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        stores_match = re.search(
            r'window\.stores\s*=\s*(\{.*?\});\s*</script>',
            resp.text, re.DOTALL,
        )
        if not stores_match:
            return None
        stores = json.loads(stores_match.group(1))
        agency_store = stores.get("agency", {})
        return {
            "agency": agency_store.get("agency", {}),
            "branches": agency_store.get("branches", []),
        }
    except Exception as e:
        logger.debug(f"Failed to extract profile from {profile_url}: {e}")
        return None


def _build_lead_from_profile(profile_url, profile_data, industry_name, industry_slug):
    """Build a fully-enriched lead dict from AgencyCentral profile data."""
    agency = profile_data.get("agency", {})
    branches = profile_data.get("branches", [])
    branch = branches[0] if branches else {}

    name = agency.get("Name", "")
    if not name:
        return None

    desc = (agency.get("BriefDescription") or agency.get("Description") or "")[:500]

    email = (
        branch.get("EmployerEmail")
        or branch.get("mailToEmployerEmail")
        or branch.get("Email")
        or ""
    )
    phone_raw = (
        branch.get("EmployerTelephone")
        or branch.get("Telephone")
        or branch.get("AssistedContactTelephone")
        or ""
    )
    phone = ""
    if phone_raw:
        phone = phone_raw.split("/")[0].strip()
        phone_clean = re.sub(r'[\s\-()]', '', phone)
        phone = phone_clean if len(phone_clean) >= 10 else phone_raw.strip()

    location_parts = [
        p for p in [
            branch.get("Location") or branch.get("Town") or "",
            branch.get("County") or "",
            branch.get("PostCode") or "",
        ] if p
    ]
    location = ", ".join(location_parts)
    full_address = (
        branch.get("FullPostalAddress")
        or branch.get("FormattedAddress")
        or ""
    ).replace("\n", ", ")

    emp_types = agency.get("RecruitmentTypesCovered", "")

    social_links = {}
    fb = branch.get("social_facebook") or agency.get("social_facebook") or ""
    if fb:
        social_links["facebook"] = (
            f"https://facebook.com/{fb}" if not fb.startswith("http") else fb
        )
    tw = branch.get("social_twitter") or agency.get("social_twitter") or ""
    if tw:
        social_links["twitter"] = (
            f"https://twitter.com/{tw}" if not tw.startswith("http") else tw
        )

    recruited_for = agency.get("WhatRecruitedFor", "")

    return {
        "name": name,
        "description": desc,
        "industry": industry_name,
        "industry_slug": industry_slug,
        "source": "agencycentral",
        "source_url": profile_url,
        "website": "",
        "email": email.strip() if email else "",
        "phone": phone,
        "location": location,
        "coverage": "",
        "employment_types": emp_types,
        "salary_range": "",
        "listed_since": "",
        "verified": False,
        "has_website": bool(
            agency.get("CandWebsite") or agency.get("EmpWebsite")
        ),
        "social_links": social_links,
        "extra": {
            "address": full_address,
            "recruited_for": recruited_for,
            "industries": agency.get("industries", ""),
            "last_activity": agency.get("last_activity_text", ""),
        },
    }


def _scrape_agency_website_requests(url):
    """Scrape an agency website for contact info using requests only."""
    result = {"emails": [], "phones": [], "social_links": {}}
    try:
        resp = http_requests.get(
            url, headers={"User-Agent": _AC_UA},
            timeout=15, allow_redirects=True,
        )
        if resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()
        result["emails"] = _extract_emails(page_text)
        result["phones"] = _extract_phones(page_text)
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            if "linkedin.com" in href:
                result["social_links"]["linkedin"] = href
            elif "twitter.com" in href or "x.com" in href:
                result["social_links"]["twitter"] = href
            elif "facebook.com" in href:
                result["social_links"]["facebook"] = href
        contact_link = None
        for a_tag in soup.select("a[href]"):
            text = a_tag.get_text(strip=True).lower()
            href = a_tag.get("href", "")
            if any(kw in text for kw in ["contact", "get in touch"]):
                if not href.startswith("http"):
                    parsed = urlparse(url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                contact_link = href
                break
        if contact_link:
            try:
                cr = http_requests.get(
                    contact_link, headers={"User-Agent": _AC_UA}, timeout=15,
                )
                if cr.status_code == 200:
                    cs = BeautifulSoup(cr.text, "html.parser")
                    ct = cs.get_text()
                    result["emails"] = list(dict.fromkeys(
                        result["emails"] + _extract_emails(ct)
                    ))
                    result["phones"] = list(dict.fromkeys(
                        result["phones"] + _extract_phones(ct)
                    ))
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Error scraping website {url}: {e}")
    return result


def scrape_agency_central(industry_slug, max_pages=3, follow_websites=True):
    """
    Scrape AgencyCentral for agencies in a given industry.
    Uses sitemap + profile page extraction (no Selenium/Chrome needed).
    max_pages controls how many agencies to fetch (~20 per page equivalent).
    """
    leads = []
    industry_name = AGENCY_CENTRAL_INDUSTRIES.get(
        industry_slug, industry_slug.title()
    )
    max_leads = max_pages * 20

    try:
        profile_urls = _discover_agency_urls_from_sitemap()
        if not profile_urls:
            logger.warning("No agency URLs found in sitemap")
            return leads

        logger.info(
            f"[Stage 1] Processing up to {len(profile_urls)} profiles "
            f"(target: {max_leads} for '{industry_name}')"
        )

        processed = 0
        for url in profile_urls:
            if len(leads) >= max_leads:
                break
            processed += 1
            logger.info(f"[Stage 2] Profile {processed}/{len(profile_urls)}: {url}")
            profile_data = _extract_profile_data(url)
            if not profile_data:
                continue
            agency_industries = (
                profile_data.get("agency", {}).get("industries", "") or ""
            ).lower()
            industry_match = (
                industry_name.lower() in agency_industries
                or industry_slug.lower() in agency_industries
            )
            if not industry_match:
                continue
            lead = _build_lead_from_profile(
                url, profile_data, industry_name, industry_slug
            )
            if lead:
                leads.append(lead)
                logger.info(
                    f"  -> Added: {lead['name']} "
                    f"(email={bool(lead.get('email'))}, "
                    f"phone={bool(lead.get('phone'))})"
                )
            _random_delay(0.5, 1.5)

        logger.info(
            f"[Done] Found {len(leads)} {industry_name} agencies "
            f"(processed {processed} profiles)"
        )

        if follow_websites:
            enriched = 0
            for lead in leads:
                needs_enrichment = (
                    (not lead.get("email") or not lead.get("phone"))
                    and lead.get("has_website")
                )
                if needs_enrichment:
                    slug = _extract_slug_from_profile_url(
                        lead.get("source_url", "")
                    )
                    if slug:
                        ac_url = (
                            "https://www.agencycentral.co.uk"
                            f"/recruitment-agency/{slug}"
                        )
                        contacts = _scrape_agency_website_requests(ac_url)
                        if contacts.get("emails") and not lead.get("email"):
                            lead["email"] = contacts["emails"][0]
                        if contacts.get("phones") and not lead.get("phone"):
                            lead["phone"] = contacts["phones"][0]
                        if contacts.get("social_links"):
                            lead.setdefault("social_links", {}).update(
                                contacts["social_links"]
                            )
                        enriched += 1
                        _random_delay(1.0, 2.0)
            if enriched:
                logger.info(f"[Stage 3] Enriched {enriched} from websites")

    except Exception as e:
        logger.error(
            f"AgencyCentral scraper error: {e}\n{traceback.format_exc()}"
        )

    return leads


def scrape_indeed(
    search_term="healthcare recruitment agency",
    location="United Kingdom",
    max_pages=2,
):
    """Scrape Indeed for recruitment agency job postings. Requests-only."""
    leads = []
    try:
        base_url = "https://uk.indeed.com/jobs"
        for page in range(max_pages):
            start = page * 10
            url = (
                f"{base_url}?q={search_term.replace(' ', '+')}"
                f"&l={location.replace(' ', '+')}&start={start}"
            )
            logger.info(f"Scraping Indeed page {page + 1}: {url}")
            try:
                resp = http_requests.get(
                    url, headers={"User-Agent": _AC_UA}, timeout=20,
                )
                resp.raise_for_status()
                page_html = resp.text
            except Exception as e:
                logger.warning(f"Failed to load Indeed page {page + 1}: {e}")
                break
            soup = BeautifulSoup(page_html, "html.parser")
            job_cards = soup.select(
                "div.job_seen_beacon, "
                "div.jobsearch-ResultsList > div, "
                "td.resultContent"
            )
            if not job_cards:
                job_cards = soup.select("[data-jk], .result, .tapItem")
            if not job_cards:
                logger.info(f"No job cards on Indeed page {page + 1}")
                break
            seen_companies = set()
            for card in job_cards:
                try:
                    company_el = card.select_one(
                        '[data-testid="company-name"], .companyName, .company'
                    )
                    if not company_el:
                        continue
                    company = company_el.get_text(strip=True)
                    if not company or company in seen_companies:
                        continue
                    seen_companies.add(company)
                    title_el = card.select_one(
                        '[data-testid="jobTitle"], .jobTitle, .title a, h2 a'
                    )
                    title = title_el.get_text(strip=True) if title_el else ""
                    loc_el = card.select_one(
                        '[data-testid="text-location"], '
                        ".companyLocation, .location"
                    )
                    loc = loc_el.get_text(strip=True) if loc_el else ""
                    sal_el = card.select_one(".salary-snippet, .estimated-salary")
                    salary = sal_el.get_text(strip=True) if sal_el else ""
                    desc_el = card.select_one(".job-snippet, .heading6")
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    link_el = card.select_one(
                        'a[href*="/rc/clk"], a[href*="/viewjob"], h2 a'
                    )
                    job_url = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        if not href.startswith("http"):
                            href = "https://uk.indeed.com" + href
                        job_url = href
                    leads.append({
                        "name": company,
                        "description": (
                            f"{title} - {desc}"[:500] if title else desc[:500]
                        ),
                        "industry": search_term,
                        "industry_slug": search_term.lower().replace(" ", "_"),
                        "source": "indeed",
                        "source_url": job_url,
                        "website": "", "email": "", "phone": "",
                        "location": loc, "coverage": "",
                        "employment_types": "", "salary_range": salary,
                        "listed_since": "", "verified": False,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Indeed card: {e}")
                    continue
            _random_delay(2.0, 5.0)
    except Exception as e:
        logger.error(f"Indeed scraper error: {e}\n{traceback.format_exc()}")
    return leads


def scrape_cqc_api(search_type="care_homes", location="", max_results=100):
    """Query the CQC public API for healthcare providers."""
    leads = []
    base_url = "https://api.cqc.org.uk/public/v1"
    try:
        params = {"perPage": min(max_results, 500), "page": 1}
        if search_type == "care_homes":
            params["careHome"] = "Y"
        elif search_type == "domiciliary":
            params["serviceType"] = "Homecare agencies"
        url = f"{base_url}/providers"
        logger.info(f"Querying CQC API: {url} with params {params}")
        cqc_ua = "ViperAI/1.0 (compliance platform)"
        resp = http_requests.get(
            url, params=params, timeout=30,
            headers={"User-Agent": cqc_ua},
        )
        resp.raise_for_status()
        data = resp.json()
        providers = data.get("providers", [])
        logger.info(f"CQC API returned {len(providers)} providers")
        for prov in providers[:max_results]:
            provider_id = prov.get("providerId", "")
            name = prov.get("providerName", "")
            if not name:
                continue
            detail = {}
            try:
                detail_resp = http_requests.get(
                    f"{base_url}/providers/{provider_id}",
                    timeout=15, headers={"User-Agent": cqc_ua},
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                _random_delay(0.3, 0.8)
            except Exception:
                pass
            address_parts = []
            for k in [
                "postalAddressLine1", "postalAddressLine2",
                "postalAddressTownCity", "postalAddressCounty", "postalCode",
            ]:
                val = detail.get(k) or prov.get(k, "")
                if val:
                    address_parts.append(val)
            location_str = ", ".join(address_parts)
            phone = detail.get("mainPhoneNumber") or ""
            website = detail.get("website") or ""
            rating = ""
            if detail.get("currentRatings"):
                overall = detail["currentRatings"].get("overall", {})
                rating = overall.get("rating", "")
            last_inspection = detail.get("lastInspection", {})
            inspection_date = (
                last_inspection.get("date", "")
                if isinstance(last_inspection, dict) else ""
            )
            services = []
            for svc in detail.get("regulatedActivities", []):
                if isinstance(svc, dict):
                    services.append(svc.get("name", ""))
            leads.append({
                "name": name,
                "description": (
                    f"CQC registered provider. Rating: {rating}. "
                    f"Services: {', '.join(services[:3])}"
                )[:500],
                "industry": "Health Care",
                "industry_slug": "health",
                "source": "cqc",
                "source_url": f"https://www.cqc.org.uk/provider/{provider_id}",
                "website": website, "email": "", "phone": phone,
                "location": location_str, "coverage": "",
                "employment_types": "", "salary_range": "",
                "listed_since": "", "verified": True,
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


def scrape_nhs_jobs(search_term="recruitment", max_pages=2):
    """Scrape NHS Jobs for healthcare recruitment agencies. Requests-only."""
    leads = []
    try:
        base_url = "https://www.jobs.nhs.uk/candidate/search/results"
        for page in range(1, max_pages + 1):
            url = (
                f"{base_url}?keyword={search_term.replace(' ', '+')}"
                f"&page={page}"
            )
            logger.info(f"Scraping NHS Jobs page {page}: {url}")
            try:
                resp = http_requests.get(
                    url, headers={"User-Agent": _AC_UA}, timeout=20,
                )
                resp.raise_for_status()
                page_html = resp.text
            except Exception as e:
                logger.warning(f"Failed to load NHS Jobs page {page}: {e}")
                break
            soup = BeautifulSoup(page_html, "html.parser")
            job_cards = soup.select(
                '[data-test="search-result"], '
                ".nhsuk-list-panel, .vacancy-card"
            )
            if not job_cards:
                job_cards = soup.select(".search-result, article, .result-item")
            if not job_cards:
                logger.info(f"No results on NHS Jobs page {page}")
                break
            seen_employers = set()
            for card in job_cards:
                try:
                    employer_el = card.select_one(
                        '.nhsuk-body-s, .employer, '
                        '[data-test="search-result-employer"]'
                    )
                    if not employer_el:
                        employer_el = card.select_one("p, span")
                    employer = (
                        employer_el.get_text(strip=True) if employer_el else ""
                    )
                    if not employer or employer in seen_employers:
                        continue
                    seen_employers.add(employer)
                    title_el = card.select_one(
                        'a, h2, h3, [data-test="search-result-job-title"]'
                    )
                    title = title_el.get_text(strip=True) if title_el else ""
                    loc_el = card.select_one(
                        '[data-test="search-result-location"], .location'
                    )
                    loc = loc_el.get_text(strip=True) if loc_el else ""
                    link_el = card.select_one("a[href]")
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
                        "website": "", "email": "", "phone": "",
                        "location": loc, "coverage": "",
                        "employment_types": "", "salary_range": "",
                        "listed_since": "", "verified": True,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing NHS Jobs card: {e}")
                    continue
            _random_delay(2.0, 5.0)
    except Exception as e:
        logger.error(f"NHS Jobs scraper error: {e}\n{traceback.format_exc()}")
    return leads


def run_scrape_job(source, config):
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

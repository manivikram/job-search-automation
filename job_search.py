"""
Job Search Automation Script
Scrapes LinkedIn, Indeed, and RemoteOK → scores with Claude AI → emails digest
Runs daily via GitHub Actions at 5 AM
"""

import os
import json
import time
import smtplib
import requests
import anthropic
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# CONFIG — edit these to match your preferences
# ─────────────────────────────────────────────
CONFIG = {
    "keywords": os.environ.get("JOB_KEYWORDS", "software engineer"),
    "location": os.environ.get("JOB_LOCATION", "Remote"),
    "min_match_score": int(os.environ.get("MIN_MATCH_SCORE", "60")),
    "your_email": os.environ.get("YOUR_EMAIL", ""),
    "gmail_app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "resume_text": os.environ.get("RESUME_TEXT", ""),  # paste resume as plain text in GitHub secret
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────

def scrape_remoteok(keywords):
    """RemoteOK has a free public JSON API — most reliable source."""
    print("🔍 Scraping RemoteOK...")
    jobs = []
    try:
        tag = keywords.strip().replace(" ", "-")
        url = f"https://remoteok.com/api?tag={tag}"
        res = requests.get(url, headers=HEADERS, timeout=15)
        data = res.json()

        # First item is metadata, skip it
        for job in data[1:21]:
            jobs.append({
                "title": job.get("position", "Unknown"),
                "company": job.get("company", "Unknown"),
                "location": job.get("location", "Remote"),
                "description": BeautifulSoup(job.get("description", ""), "html.parser").get_text()[:2000],
                "url": job.get("url", f"https://remoteok.com/remote-jobs/{job.get('id','')}"),
                "source": "RemoteOK",
                "salary": job.get("salary", ""),
            })
        print(f"   ✅ Found {len(jobs)} jobs on RemoteOK")
    except Exception as e:
        print(f"   ❌ RemoteOK error: {e}")
    return jobs


def scrape_indeed(keywords, location):
    """Scrape Indeed job listings."""
    print("🔍 Scraping Indeed...")
    jobs = []
    try:
        url = (
            f"https://www.indeed.com/jobs"
            f"?q={requests.utils.quote(keywords)}"
            f"&l={requests.utils.quote(location)}"
            f"&fromage=1"  # last 24 hours
        )
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        cards = soup.select(".job_seen_beacon") or soup.select("[data-jk]")
        for card in cards[:20]:
            title_el = card.select_one(".jobTitle span, h2.jobTitle")
            company_el = card.select_one(".companyName, [data-testid='company-name']")
            location_el = card.select_one(".companyLocation, [data-testid='text-location']")
            link_el = card.select_one("a[href*='/rc/clk'], a[id*='job_']")

            title = title_el.get_text(strip=True) if title_el else None
            if not title:
                continue

            jobs.append({
                "title": title,
                "company": company_el.get_text(strip=True) if company_el else "Unknown",
                "location": location_el.get_text(strip=True) if location_el else location,
                "description": "",  # fetched separately
                "url": "https://indeed.com" + link_el["href"] if link_el and link_el.get("href", "").startswith("/") else (link_el["href"] if link_el else ""),
                "source": "Indeed",
                "salary": "",
            })

        print(f"   ✅ Found {len(jobs)} jobs on Indeed")
    except Exception as e:
        print(f"   ❌ Indeed error: {e}")
    return jobs


def scrape_linkedin(keywords, location):
    """Scrape LinkedIn job listings."""
    print("🔍 Scraping LinkedIn...")
    jobs = []
    try:
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={requests.utils.quote(keywords)}"
            f"&location={requests.utils.quote(location)}"
            f"&f_TPR=r86400"  # last 24 hours
            f"&position=1&pageNum=0"
        )
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        cards = soup.select(".jobs-search__results-list li, .base-card")
        for card in cards[:20]:
            title_el = card.select_one(".base-search-card__title, h3.base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle, a.hidden-nested-link")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link, a[href*='linkedin.com/jobs/view']")

            title = title_el.get_text(strip=True) if title_el else None
            if not title:
                continue

            jobs.append({
                "title": title,
                "company": company_el.get_text(strip=True) if company_el else "Unknown",
                "location": location_el.get_text(strip=True) if location_el else location,
                "description": "",
                "url": link_el["href"].split("?")[0] if link_el and link_el.get("href") else "",
                "source": "LinkedIn",
                "salary": "",
            })

        print(f"   ✅ Found {len(jobs)} jobs on LinkedIn")
    except Exception as e:
        print(f"   ❌ LinkedIn error: {e}")
    return jobs


def fetch_job_description(url, source):
    """Fetch the full job description from individual job pages."""
    if not url:
        return ""
    try:
        time.sleep(2)  # be polite, avoid rate limiting
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # Try source-specific selectors first
        selectors = {
            "LinkedIn": [".description__text", ".show-more-less-html__markup"],
            "Indeed": ["#jobDescriptionText", ".jobsearch-jobDescriptionText"],
            "RemoteOK": [".description"],
        }

        for sel in selectors.get(source, []):
            el = soup.select_one(sel)
            if el:
                return el.get_text(separator=" ", strip=True)[:2500]

        # Fallback: get body text
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:2500]

    except Exception:
        return ""


def deduplicate(jobs):
    """Remove duplicate jobs by title + company."""
    seen = set()
    unique = []
    for job in jobs:
        key = f"{job['title'].lower()}|{job['company'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ─────────────────────────────────────────────
# CLAUDE AI SCORING
# ─────────────────────────────────────────────

def score_job_with_claude(job, resume_text, keywords, client):
    """Send job + resume to Claude and get a match score + analysis."""
    prompt = f"""You are an expert career advisor. Analyze this job posting against the candidate's resume and keywords.

## CANDIDATE RESUME:
{resume_text[:3500]}

## TARGET KEYWORDS:
{keywords}

## JOB POSTING:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Source: {job['source']}
Description: {job.get('description', 'Not available')[:2000]}

## YOUR TASK:
Return ONLY a valid JSON object with NO markdown, NO backticks, NO explanation:

{{
  "match_score": <integer 0-100>,
  "keyword_match": <integer 0-100>,
  "recommendation": "<Apply Now | Strong Match | Consider Applying | Low Match | Skip>",
  "match_reasons": "<2-3 sentence explanation>",
  "top_matching_skills": "<comma-separated skills that match>",
  "missing_skills": "<comma-separated important skills the candidate may lack>",
  "cover_letter_hook": "<one compelling opening sentence for a cover letter>"
}}"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()

        # Extract JSON safely
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        return json.loads(response_text[start:end])

    except Exception as e:
        print(f"   ⚠️  Claude error for {job['title']}: {e}")
        return {
            "match_score": 0,
            "keyword_match": 0,
            "recommendation": "Review Manually",
            "match_reasons": "Could not analyze.",
            "top_matching_skills": "",
            "missing_skills": "",
            "cover_letter_hook": ""
        }


# ─────────────────────────────────────────────
# EMAIL BUILDER
# ─────────────────────────────────────────────

def build_email_html(scored_jobs, total_scraped):
    """Build a beautiful HTML email digest."""
    date_str = datetime.now().strftime("%B %d, %Y")

    def score_color(score):
        if score >= 80: return "#27ae60"
        if score >= 60: return "#f39c12"
        return "#e74c3c"

    rows = ""
    for job in scored_jobs:
        color = score_color(job["match_score"])
        rows += f"""
        <tr>
          <td style="padding:14px 12px; border-bottom:1px solid #eee; vertical-align:top;">
            <a href="{job['url']}" style="font-weight:bold; font-size:15px; color:#2c3e50; text-decoration:none;">
              {job['title']}
            </a><br>
            <span style="color:#7f8c8d; font-size:13px;">
              🏢 {job['company']} &nbsp;|&nbsp; 📍 {job['location']} &nbsp;|&nbsp; 🔗 {job['source']}
            </span>
            {f'<br><span style="color:#27ae60;font-size:12px;">💰 {job["salary"]}</span>' if job.get("salary") else ""}
          </td>
          <td style="padding:14px 12px; border-bottom:1px solid #eee; text-align:center; vertical-align:top; white-space:nowrap;">
            <div style="background:{color}; color:white; padding:6px 14px; border-radius:20px; font-weight:bold; font-size:16px; display:inline-block;">
              {job['match_score']}%
            </div><br>
            <small style="color:{color}; font-weight:bold;">{job['recommendation']}</small>
          </td>
          <td style="padding:14px 12px; border-bottom:1px solid #eee; font-size:13px; vertical-align:top;">
            <p style="margin:0 0 6px 0;">{job['match_reasons']}</p>
            <p style="margin:0; color:#27ae60;">✅ <strong>Skills:</strong> {job['top_matching_skills'] or 'N/A'}</p>
            {f'<p style="margin:4px 0 0 0; color:#e74c3c;">❌ <strong>Missing:</strong> {job["missing_skills"]}</p>' if job.get("missing_skills") else ""}
          </td>
          <td style="padding:14px 12px; border-bottom:1px solid #eee; font-size:12px; color:#555; vertical-align:top; font-style:italic;">
            "{job['cover_letter_hook']}"
          </td>
        </tr>"""

    if not rows:
        rows = """<tr><td colspan="4" style="padding:30px; text-align:center; color:#999;">
            No jobs matched your minimum score today. Try lowering MIN_MATCH_SCORE.
        </td></tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif; background:#f5f6fa; margin:0; padding:20px;">
  <div style="max-width:960px; margin:0 auto; background:white; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.1);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#667eea,#764ba2); padding:35px 30px; text-align:center;">
      <h1 style="color:white; margin:0; font-size:28px;">🎯 Daily Job Match Report</h1>
      <p style="color:rgba(255,255,255,0.85); margin:10px 0 0;">{date_str} &nbsp;|&nbsp; {len(scored_jobs)} matches from {total_scraped} jobs scraped</p>
    </div>

    <!-- Table -->
    <div style="padding:20px;">
      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:#f8f9fa;">
            <th style="padding:12px; text-align:left; color:#555; font-size:13px;">JOB</th>
            <th style="padding:12px; text-align:center; color:#555; font-size:13px;">MATCH</th>
            <th style="padding:12px; text-align:left; color:#555; font-size:13px;">ANALYSIS</th>
            <th style="padding:12px; text-align:left; color:#555; font-size:13px;">COVER LETTER HOOK</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <!-- Footer -->
    <div style="padding:20px 30px; background:#f8f9fa; text-align:center; border-top:1px solid #eee;">
      <p style="color:#aaa; font-size:12px; margin:0;">
        Powered by Claude AI &nbsp;|&nbsp; Sources: LinkedIn, Indeed, RemoteOK
        &nbsp;|&nbsp; Runs daily at 5 AM via GitHub Actions
      </p>
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────

def send_email(html_body, job_count, to_email, gmail_password):
    """Send the digest email via Gmail SMTP."""
    from_email = to_email
    subject = f"🎯 {job_count} Job Matches Today — {datetime.now().strftime('%b %d, %Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, gmail_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        raise


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("🚀 Job Search Automation Starting...")
    print(f"   Keywords : {CONFIG['keywords']}")
    print(f"   Location : {CONFIG['location']}")
    print(f"   Min Score: {CONFIG['min_match_score']}%")
    print("=" * 50)

    # 1. Scrape all platforms
    all_jobs = []
    all_jobs += scrape_remoteok(CONFIG["keywords"])
    all_jobs += scrape_indeed(CONFIG["keywords"], CONFIG["location"])
    all_jobs += scrape_linkedin(CONFIG["keywords"], CONFIG["location"])

    # 2. Deduplicate
    unique_jobs = deduplicate(all_jobs)
    print(f"\n📋 Total unique jobs: {len(unique_jobs)}")

    # 3. Fetch full descriptions (for non-RemoteOK jobs)
    print("\n📄 Fetching full job descriptions...")
    for i, job in enumerate(unique_jobs):
        if job["source"] != "RemoteOK" and not job["description"]:
            print(f"   [{i+1}/{len(unique_jobs)}] {job['title']} @ {job['company']}")
            job["description"] = fetch_job_description(job["url"], job["source"])

    # 4. Score with Claude
    print("\n🤖 Scoring jobs with Claude AI...")
    client = anthropic.Anthropic(api_key=CONFIG["anthropic_api_key"])
    scored_jobs = []

    for i, job in enumerate(unique_jobs):
        print(f"   [{i+1}/{len(unique_jobs)}] Analyzing: {job['title']} @ {job['company']}")
        analysis = score_job_with_claude(job, CONFIG["resume_text"], CONFIG["keywords"], client)
        time.sleep(1)  # avoid rate limiting

        combined = {**job, **analysis}
        if combined.get("match_score", 0) >= CONFIG["min_match_score"]:
            scored_jobs.append(combined)
            print(f"   ✅ Score: {combined['match_score']}% — {combined['recommendation']}")
        else:
            print(f"   ⏭️  Score: {combined.get('match_score', 0)}% — below threshold, skipping")

    # 5. Sort by score
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    print(f"\n🎯 {len(scored_jobs)} jobs passed the threshold")

    # 6. Build & send email
    print("\n📧 Sending email digest...")
    html = build_email_html(scored_jobs, len(unique_jobs))
    send_email(html, len(scored_jobs), CONFIG["your_email"], CONFIG["gmail_app_password"])

    print("\n✅ Done! Check your inbox.")


if __name__ == "__main__":
    main()

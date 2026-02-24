# 🎯 Job Search Automation — Setup Guide
**Stack: Python + GitHub Actions + Claude AI **

---

## What You'll Have When Done
Every morning at 5 AM, GitHub's servers will automatically:
1. Scrape LinkedIn, Indeed, and RemoteOK for jobs posted in the last 24 hours
2. Score each job against your resume using Claude AI
3. Email you a beautiful HTML digest with only your best matches

**Zero cost. Zero servers. Runs forever.**

---

## Step 1 — Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in (create a free account if needed)
2. Click the **+** icon (top right) → **New repository**
3. Name it: `job-search-automation`
4. Set it to **Private** (keeps your resume safe)
5. Click **Create repository**

---

## Step 2 — Upload the Files

Upload these files to your repo in this exact structure:

```
job-search-automation/
├── .github/
│   └── workflows/
│       └── job_search.yml      ← GitHub Actions trigger
├── scripts/
│   └── job_search.py           ← Main Python script
└── requirements.txt            ← Python packages
```

**How to upload:**
1. In your new repo, click **Add file → Upload files**
2. Drag and drop all the files (keeping the folder structure)
3. Click **Commit changes**

> 💡 **Or use Git:** `git clone` your repo, copy the files in, then `git add . && git commit -m "Add job search automation" && git push`

---

## Step 3 — Get Your API Keys & Passwords

You need 3 things:

### A) Anthropic API Key (Claude AI)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / log in
3. Click **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)
5. Add $5 credit (the minimum) — this will last months at daily usage

### B) Gmail App Password
> ⚠️ This is NOT your regular Gmail password. It's a special password just for apps.

1. Go to your Google Account → [myaccount.google.com](https://myaccount.google.com)
2. Click **Security** → **2-Step Verification** (enable it if not already)
3. At the bottom of the 2-Step page, click **App passwords**
4. Select app: **Mail** | Select device: **Other** → type "Job Search Bot"
5. Click **Generate** → copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
6. Remove the spaces when saving it as a secret

### C) Your Resume as Plain Text
1. Open your resume PDF
2. Select all text → copy it
3. You'll paste this as a GitHub Secret in the next step

---

## Step 4 — Add GitHub Secrets

Secrets are encrypted environment variables — GitHub hides them from everyone, including you, after saving.

1. In your GitHub repo, click **Settings** (top menu)
2. Click **Secrets and variables → Actions** (left sidebar)
3. Click **New repository secret** for each of these:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key (`sk-ant-...`) |
| `YOUR_EMAIL` | Your Gmail address (`you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-char app password (no spaces) |
| `RESUME_TEXT` | Your full resume as plain text |
| `JOB_KEYWORDS` | e.g., `python engineer AI` |
| `JOB_LOCATION` | e.g., `Remote` or `New York, NY` |
| `MIN_MATCH_SCORE` | e.g., `65` (filter out jobs below this %) |

---

## Step 5 — Test It Manually

Don't wait until 5 AM — trigger it now:

1. In your repo, click **Actions** (top menu)
2. Click **Daily Job Search** (left sidebar)
3. Click **Run workflow → Run workflow** (green button)
4. Click the running workflow to watch logs in real time
5. In ~5–10 minutes, check your inbox! 📧

---

## Step 6 — Adjust Your Schedule (Optional)

The workflow runs at `5 0 5 * * *` = **5:00 AM UTC**.

To change the time, edit `.github/workflows/job_search.yml`:
```yaml
- cron: '0 5 * * *'   # minute hour * * *
```

Common times (UTC — subtract 5hrs for EST, 8hrs for PST):
| You want | UTC cron |
|---|---|
| 5 AM EST | `0 10 * * *` |
| 7 AM EST | `0 12 * * *` |
| 5 AM PST | `0 13 * * *` |

---

## What the Email Looks Like

You'll receive a color-coded HTML email:

| Color | Meaning |
|---|---|
| 🟢 Green badge | 80%+ match — Apply Now / Strong Match |
| 🟡 Yellow badge | 60–79% match — Consider Applying |
| (filtered out) | Below your MIN_MATCH_SCORE |

Each job card includes:
- **Match score** (0–100%) and recommendation
- **Why it matches** (AI reasoning in plain English)
- **Matching skills** from your resume
- **Missing skills** you might want to address
- **Cover letter hook** — a ready-to-use opening sentence

---

## Troubleshooting

**❌ "No jobs found"**
- LinkedIn and Indeed actively block scrapers. If this happens, RemoteOK (which has a real API) will still work reliably
- Try running again — blocks are often temporary

**❌ Email not arriving**
- Check your spam folder
- Double-check the Gmail App Password has no spaces
- Make sure 2-Step Verification is ON for your Google account

**❌ Claude API error**
- Check your API key is correct in GitHub Secrets
- Make sure you have billing set up at console.anthropic.com

**❌ Workflow not appearing in Actions tab**
- Make sure the file is at `.github/workflows/job_search.yml` (exact path matters)
- The `.github` folder must be at the root of your repo

---

## Cost Estimate

| Service | Cost |
|---|---|
| GitHub Actions | ✅ Free (2,000 min/month, workflow uses ~5 min/day) |
| RemoteOK API | ✅ Free |
| LinkedIn / Indeed scraping | ✅ Free |
| Claude API | ~$0.01–0.05 per day (analyzing ~30–60 jobs) |
| Gmail SMTP | ✅ Free |
| **Monthly total** | **~$0.30–$1.50/month** |

---

## File Structure Reference

```
job-search-automation/
│
├── .github/
│   └── workflows/
│       └── job_search.yml     # Schedules and runs the script
│
├── scripts/
│   └── job_search.py          # Main script:
│                              #   - scrape_remoteok()
│                              #   - scrape_indeed()
│                              #   - scrape_linkedin()
│                              #   - fetch_job_description()
│                              #   - score_job_with_claude()
│                              #   - build_email_html()
│                              #   - send_email()
│                              #   - main()
│
└── requirements.txt           # anthropic, requests, beautifulsoup4, lxml
```

# Freelance Lead Finder — Local Webapp

Runs entirely on your own machine (Kali Linux tested). Finds freelance/remote job
leads matching your skills, drafts AI proposals for you to review, and tracks status —
all in a local Streamlit dashboard.

## What this does NOT do
It does not auto-apply or auto-submit proposals. Upwork and similar platforms ban
accounts for automated bidding. You review every draft and send it yourself.
"No daily presence" applies to the *searching and drafting* part, not to landing/delivering work.

## Setup

```bash
cd freelance_finder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Enable AI proposal drafting (get key from console.anthropic.com)
export ANTHROPIC_API_KEY="your-key-here"
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Customize

- Edit `KEYWORDS` in `fetch_leads.py` to match the gigs you want (currently set for
  Python automation / MQL5 / trading bot / scraping work).
- Edit `YOUR_PROFILE` in `proposal_gen.py` to describe your actual background.

## Automate the fetching (optional)

To have new leads pulled in automatically even when the dashboard is closed, add a cron job:

```bash
crontab -e
# Add this line to fetch every 4 hours:
0 */4 * * * cd /path/to/freelance_finder && venv/bin/python fetch_leads.py
```

Leads will already be in the database next time you open the dashboard.

## Data sources used (all public, ToS-compliant)
- RemoteOK public API
- WeWorkRemotely public RSS feed
- Upwork public RSS search feed (no login, no scraping bot)

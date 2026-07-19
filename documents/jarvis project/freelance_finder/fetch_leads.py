"""
Fetches freelance/remote job leads from PUBLIC, ToS-friendly sources only:
- RemoteOK (public JSON API)
- WeWorkRemotely (public RSS feed)
- Upwork RSS search feed (public, keyword-based, no login/scraping)

No automated bidding/applying is done here — this only collects and stores leads.
"""
import requests
import feedparser
from db import add_lead

# Customize these keywords to match your skills
KEYWORDS = ["python automation", "trading bot", "mql5", "web scraping", "api integration"]


def fetch_remoteok():
    new_count = 0
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        jobs = r.json()[1:]  # first item is metadata
        for job in jobs:
            title = job.get("position", "")
            tags = " ".join(job.get("tags", [])).lower()
            if any(k.split()[0] in tags or k.split()[0] in title.lower() for k in KEYWORDS):
                link = job.get("url", "")
                summary = job.get("description", "")[:500]
                if add_lead("RemoteOK", title, link, summary):
                    new_count += 1
    except Exception as e:
        print(f"RemoteOK fetch error: {e}")
    return new_count


def fetch_wwr():
    new_count = 0
    try:
        feed = feedparser.parse("https://weworkremotely.com/categories/remote-programming-jobs.rss")
        for entry in feed.entries:
            title = entry.title
            if any(k.split()[0] in title.lower() for k in KEYWORDS):
                if add_lead("WeWorkRemotely", title, entry.link, entry.summary[:500]):
                    new_count += 1
    except Exception as e:
        print(f"WWR fetch error: {e}")
    return new_count


def fetch_upwork_rss():
    new_count = 0
    for kw in KEYWORDS:
        try:
            url = f"https://www.upwork.com/ab/feed/jobs/rss?q={kw.replace(' ', '+')}&sort=recency"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if add_lead("Upwork", entry.title, entry.link, entry.get("summary", "")[:500]):
                    new_count += 1
        except Exception as e:
            print(f"Upwork fetch error for '{kw}': {e}")
    return new_count


def fetch_all():
    total = 0
    total += fetch_remoteok()
    total += fetch_wwr()
    total += fetch_upwork_rss()
    return total


if __name__ == "__main__":
    from db import init_db
    init_db()
    print(f"New leads found: {fetch_all()}")

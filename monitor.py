"""Alta Via 8 rifugio booking monitor.

Runs on GitHub Actions. Sends Telegram alerts only for actionable changes:
  - a hut page adds text saying 2027 bookings are open
  - a booking engine shows bookable rooms for the trip night
  - a hut page's booking text changes (verify by hand)
  - a check fails N runs in a row
  - a dated reminder from reminders.json is due
Never books, submits forms, or pays.
"""
import hashlib, json, os, re, sys, time
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
STATE = ROOT / "state"
DEBUG = STATE / "debug"
KL, ROME = ZoneInfo("Asia/Kuala_Lumpur"), ZoneInfo("Europe/Rome")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en,it;q=0.8,de;q=0.6"}

CFG = json.loads((ROOT / "huts.json").read_text())
S = CFG["settings"]


# ---------- helpers ----------
def load(name, default):
    p = STATE / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, data):
    STATE.mkdir(exist_ok=True)
    (STATE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def telegram(text):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("[telegram skipped]", text)
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": text, "disable_web_page_preview": True},
                      timeout=20)
    except Exception as e:
        print("telegram error:", e)


def to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def fetch(url, rendered=False):
    """Plain requests -> browser impersonation -> r.jina.ai reader (renders JS)."""
    errors = []
    if not rendered:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.ok and len(r.text) > 500:
                return to_text(r.text), "direct"
            errors.append(f"direct {r.status_code}")
        except Exception as e:
            errors.append(f"direct {type(e).__name__}")
        try:
            from curl_cffi import requests as cr
            r = cr.get(url, impersonate="chrome", timeout=30)
            if r.status_code < 400 and len(r.text) > 500:
                return to_text(r.text), "browser"
            errors.append(f"browser {r.status_code}")
        except Exception as e:
            errors.append(f"browser {type(e).__name__}")
    try:
        r = requests.get("https://r.jina.ai/" + url, headers={**UA, "X-Return-Format": "text"}, timeout=60)
        if r.ok and len(r.text) > 200:
            return re.sub(r"\s+", " ", r.text), "reader"
        errors.append(f"reader {r.status_code}")
    except Exception as e:
        errors.append(f"reader {type(e).__name__}")
    raise RuntimeError("; ".join(errors))


def booking_sentences(text):
    kws = [k.lower() for k in S["keywords"]]
    out = set()
    for s in re.split(r"(?<=[.!?])\s+|\s{2,}| \| ", text):
        s = s.strip()
        if 15 <= len(s) <= 300 and any(k in s.lower() for k in kws):
            out.add(s)
    return out


def matches(patterns, text):
    return [p for p in patterns if re.search(p, text, re.I)]


def fp(items):
    return hashlib.sha1("\n".join(sorted(items)).encode()).hexdigest()[:12]


# ---------- checks ----------
def check_pages(hut, prev):
    """Fingerprint booking-related sentences on each page; flag added 2027/open text."""
    sentences, methods = set(), []
    for url in hut["pages"]:
        text, how = fetch(url)
        methods.append(how)
        sentences |= booking_sentences(text)
    old = set(prev.get("sentences", []))
    added = sorted(sentences - old) if old else []
    says_open = [s for s in sentences if matches(S["open_patterns"], s)]
    status = "PAGE SAYS 2027 OPEN - verify" if says_open else "watching"
    alerts = []
    if added:
        hot = [s for s in added if "2027" in s or matches(S["open_patterns"], s)]
        if hot:
            alerts.append(f"🟡 {hut['name']} ({hut['night'][5:]}): new booking text\n- " +
                          "\n- ".join(hot[:4]) + f"\n{hut['pages'][0]}")
    return {"status": status, "sentences": sorted(sentences), "fp": fp(sentences),
            "method": "/".join(methods), "added": len(added)}, alerts


def check_engine(hut, prev):
    """Rendered booking engine for the trip night. Also page-watch the hut site."""
    n = datetime.strptime(hut["night"], "%Y-%m-%d").date()
    url = hut["engine_url"].format(checkin=n.isoformat(), checkout=(n + timedelta(days=1)).isoformat(),
                                   guests=S["guests"])
    text, how = fetch(url, rendered=True)
    DEBUG.mkdir(parents=True, exist_ok=True)
    (DEBUG / f"{hut['id']}.txt").write_text(text[:20000])
    low = text.lower()
    none_hit = matches(S["none_patterns"], low)
    avail_hit = matches(S["available_patterns"], low)
    if none_hit:
        eng = "no rooms / not open"
    elif avail_hit and "2027" in text:
        eng = "ROOMS SHOWN - verify dorm"
    else:
        eng = "unclear - see debug"
    page_res, alerts = check_pages(hut, prev)
    res = {**page_res, "engine": eng, "engine_method": how, "status":
           eng if eng.startswith("ROOMS") else page_res["status"]}
    if eng.startswith("ROOMS"):
        last = prev.get("rooms_alert_at")
        due = not last or (datetime.utcnow() - datetime.fromisoformat(last)) > timedelta(hours=S["still_open_reminder_hours"])
        if prev.get("engine") != eng or due:
            alerts.append(f"🟢 {hut['name']} {hut['night'][8:]}/{hut['night'][5:7]}: booking engine shows rooms for 2. "
                          f"Check for dorm beds now:\n{url}")
            res["rooms_alert_at"] = datetime.utcnow().isoformat()
        else:
            res["rooms_alert_at"] = last
    return res, alerts


# ---------- reminders / status ----------
def due_reminders(sent):
    today = datetime.now(KL).date()
    out = []
    for r in json.loads((ROOT / "reminders.json").read_text()):
        if r["id"] not in sent and date.fromisoformat(r["date"]) <= today:
            out.append(r)
    return out


def write_status(results, now):
    rows = ["| Night | Hut | Role | Status | Meals | Booking | Method |", "|---|---|---|---|---|---|---|"]
    for h in CFG["huts"]:
        r = results.get(h["id"], {})
        st = r.get("status", "?")
        if r.get("fails"):
            st = f"⚠️ error x{r['fails']}: {r.get('error', '')[:60]}"
        rows.append(f"| {h['night'][8:]} Jun | {h['name']} | {h['role']} | {st} | {h['meals']} | {h['book']} | {r.get('method', '')} |")
    (ROOT / "STATUS.md").write_text(
        f"# {S['trip_name']} – status\n\nLast check: {now.astimezone(KL):%d %b %Y %H:%M} KL · "
        f"{now.astimezone(ROME):%H:%M} Italy\n\n" + "\n".join(rows) +
        "\n\n26 Jun Ortisei: not monitored (valley hotels are bookable now).\n")


def main():
    if "--test-alert" in sys.argv:
        telegram("✅ AV8 monitor test message. Telegram is set up.")
        return
    now = datetime.now(ZoneInfo("UTC"))
    if now.astimezone(ROME).date() > date.fromisoformat(S["stop_after"]):
        print("Trip window passed; nothing to do.")
        return
    state = load("huts.json", {})
    meta = load("meta.json", {"reminders_sent": []})
    alerts = []
    for hut in CFG["huts"]:
        prev = state.get(hut["id"], {})
        try:
            fn = check_engine if hut["check"] == "engine" else check_pages
            res, a = fn(hut, prev)
            res["fails"] = 0
            alerts += a
        except Exception as e:
            fails = prev.get("fails", 0) + 1
            res = {**prev, "fails": fails, "error": str(e)}
            if fails == S["error_after_runs"]:
                alerts.append(f"⚠️ {hut['name']}: check failed {fails} runs in a row ({str(e)[:120]}). Check by hand.")
        res["checked"] = now.isoformat()
        state[hut["id"]] = res
        time.sleep(1)
    for r in due_reminders(meta["reminders_sent"]):
        alerts.append(r["message"])
        meta["reminders_sent"].append(r["id"])
    for a in alerts:
        telegram(a)
    save("huts.json", state)
    save("meta.json", meta)
    with open(STATE / "history.jsonl", "a") as f:
        f.write(json.dumps({"t": now.isoformat(), "alerts": alerts}, ensure_ascii=False) + "\n")
    write_status(state, now)
    print(json.dumps({"alerts": alerts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

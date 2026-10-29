# Job-search agent engine
# File:    engine/cloud_sync.py
# Purpose: Connects the app on your computer to your own online Job Agent (cloud/): fetches postings and decisions, sends back decisions and which postings have documents. Your CV never leaves the computer.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
Settings (inputs/secrets.json): cloud_url, cloud_token (the SYNC_TOKEN you
chose when deploying). State: state/cloud_sync.json.

pull(home):
  1. GET  <url>/api/sync/export?since=...  postings, decisions, search config
  2. new postings are added to the local tracker, with their descriptions
     saved for tailoring (state/new_postings/cloud_<date>.json); postings the
     online search found closed become Expired here too (accepted ones only
     get a note)
  3. decisions: the newer one wins, in both directions
     (online decisions are applied here; decisions made here are sent)
  4. postings with documents made here are reported, so the online page
     shows "Documents made on your computer"

Only posting data and decisions travel. Nothing from inputs/candidate/,
inputs/intake/ or output/ is ever sent.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

from . import decisions as dec, tracker as tr
from .collect import http

SECRET_URL, SECRET_TOKEN = "cloud_url", "cloud_token"


def _secrets_path(home):
    return os.path.join(home.path("inputs"), "secrets.json")


def _state_path(home):
    return os.path.join(os.path.dirname(home.path("notes")), "cloud_sync.json")


def _read(p, default):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def settings(home):
    s = _read(_secrets_path(home), {}) or {}
    st = _read(_state_path(home), {}) or {}
    url = str(s.get(SECRET_URL) or "").rstrip("/")
    return {"url": url, "token": bool(s.get(SECRET_TOKEN)), "connected": bool(url and s.get(SECRET_TOKEN)),
            "last_pull": st.get("last_pull"), "error": st.get("error")}


def configure(home, url=None, token=None):
    p = _secrets_path(home)
    s = _read(p, {}) or {}
    if url is not None:
        url = url.strip().rstrip("/")
        if url and not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
            raise ValueError("the address must start with https://")
        if url:
            s[SECRET_URL] = url
        else:
            s.pop(SECRET_URL, None)
    if token == "__clear__":
        s.pop(SECRET_TOKEN, None)
    elif token:
        s[SECRET_TOKEN] = token.strip()
    _write(p, s)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return settings(home)


def connected(home):
    return settings(home)["connected"]


def _auth(home):
    s = _read(_secrets_path(home), {}) or {}
    return str(s.get(SECRET_URL) or "").rstrip("/"), {"Authorization": f"Bearer {s.get(SECRET_TOKEN) or ''}"}


def _row_from(p, run_date):
    return {
        "Date Found": p.get("found") or run_date, "Title": p.get("title") or "", "Employer": p.get("employer") or "",
        "Location": p.get("location") or "", "Category": p.get("category") or "", "Seniority Level": p.get("seniority") or "",
        "Announce Date": p.get("announced") or "", "Deadline": p.get("deadline") or "rolling",
        "Remote/Hybrid/Onsite": p.get("arrangement") or "", "Required Skills (summary)": p.get("skills") or "",
        "URL": p.get("url") or "", "Calendar Event Added (Y/N)": "N", "CV/Cover Letter Drafted (Y/N)": "N",
        "Status": p.get("status") or "New", "Notes": (p.get("notes") or "") + " | fetched from your online search",
    }


def pull(home, log=print):
    """Returns a summary dict; never raises on network problems."""
    url, hdr = _auth(home)
    st = _read(_state_path(home), {}) or {}
    if not url:
        log("online search is not connected (Settings > Online search)")
        return {"ok": False}
    since = st.get("since") or ""
    r, data = http.get_json(f"{url}/api/sync/export?since={since}", headers=hdr)
    if data is None:
        msg = "the sync token was not accepted" if r.status == 401 else (r.error or f"HTTP {r.status}")
        st["error"] = f"{datetime.now().isoformat(timespec='minutes')}: {msg}"
        _write(_state_path(home), st)
        log(f"could not fetch from {url}: {msg}")
        return {"ok": False, "error": msg}
    run_date = date.today().isoformat()
    cfg = home.search_config()
    rows = tr.read_all_rows(home.path("tracker"))
    by_key = {f"{x.get('URL') or ''}||{x.get('Title') or ''}": x for x in rows}
    by_url = {x.get("URL"): x for x in rows if x.get("URL")}

    new_rows, updates, descs = [], [], []
    for p in data.get("postings") or []:
        key = p.get("key") or f"{p.get('url')}||{p.get('title')}"
        if p.get("description"):
            descs.append({"url": p.get("url"), "title": p.get("title"), "employer": p.get("employer"),
                          "description": p["description"], "source": "online search"})
        local = by_key.get(key) or by_url.get(p.get("url"))
        if local is None:
            new_rows.append(_row_from(p, run_date))
        elif p.get("status") == "Expired" and tr.status_bucket(local.get("Status")) == "active":
            row = dict(local)
            if str(local.get("Status") or "").startswith("Approved"):
                note = f"{run_date}: the online check found it closed, kept because accepted"
                if note not in str(local.get("Notes") or ""):
                    row["Notes"] = f'{local.get("Notes") or ""} | {note}'.strip(" |")
                    updates.append(row)
            else:
                row["Status"] = "Expired"
                row["Notes"] = f'{local.get("Notes") or ""} | {run_date}: expired (online check)'.strip(" |")
                updates.append(row)
    if descs:
        os.makedirs(home.path("new_postings"), exist_ok=True)
        p = os.path.join(home.path("new_postings"), f"cloud_{run_date}.json")
        old = (_read(p, {}) or {}).get("kept_candidates", [])
        seen = {d["url"] for d in descs}
        _write(p, {"kept_candidates": [o for o in old if o.get("url") not in seen] + descs})
    if new_rows or updates:
        tr.update(home.path("tracker"), new_rows + updates, seniority_cfg=cfg.get("seniority"),
                  act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))

    # decisions: the newer one wins
    local_dec = _read(home.path("decisions"), {}) or {}
    remote_dec = data.get("decisions") or {}
    merged, to_send = dict(local_dec), {}
    for k, d in remote_dec.items():
        if str(d.get("ts") or "") > str((local_dec.get(k) or {}).get("ts") or ""):
            merged[k] = {x: d.get(x) for x in ("decision", "reasons", "note", "ts") if d.get(x) not in (None, "")}
    for k, d in local_dec.items():
        if d.get("decision") in ("accepted", "rejected") and str(d.get("ts") or "") > str((remote_dec.get(k) or {}).get("ts") or ""):
            to_send[k] = d
    if merged != local_dec:
        _write(home.path("decisions"), merged)
    applied = dec.apply(home, seniority_cfg=cfg.get("seniority")) if merged else {"applied": 0}
    sent = 0
    if to_send:
        r2, res = http.post_json(f"{url}/api/sync/decisions", {"decisions": to_send}, headers=hdr)
        sent = (res or {}).get("applied", 0)
    drafted = [f"{x.get('URL') or ''}||{x.get('Title') or ''}" for x in tr.read_all_rows(home.path("tracker"))
               if str(x.get("CV/Cover Letter Drafted (Y/N)") or "").upper() == "Y"]
    if drafted:
        http.post_json(f"{url}/api/sync/drafted", {"keys": drafted}, headers=hdr)
    _write(os.path.join(os.path.dirname(home.path("notes")), "cloud_config.json"), data.get("config") or {})
    now = data.get("now") or datetime.now(timezone.utc).isoformat()
    st.update({"last_pull": datetime.now().isoformat(timespec="minutes"), "error": None,
               "since": (datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")})
    _write(_state_path(home), st)
    summary = {"ok": True, "new": len(new_rows), "expired": len(updates), "decisions_applied": applied.get("applied", 0), "decisions_sent": sent}
    log(f"online search: {summary['new']} new posting(s), {summary['expired']} closed, "
        f"{summary['decisions_applied']} decision(s) applied here, {sent} sent online")
    return summary


def start_search(home):
    """Asks the online Job Agent to start a search now (it runs there; fetch later)."""
    url, hdr = _auth(home)
    r, res = http.post_json(f"{url}/api/sync/run", {}, headers=hdr)
    return bool(res and res.get("ok")), (res or {}).get("message") or r.error or f"HTTP {r.status}"

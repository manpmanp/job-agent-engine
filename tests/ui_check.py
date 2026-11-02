#!/usr/bin/env python3
# Job-search agent engine
# File:    tests/ui_check.py
# Purpose: Opens the app's page in a real browser engine on this system (Chromium, Edge, Firefox or WebKit/Safari) and checks that every screen shows and works the same, at desktop and phone width, light and dark.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.8
# Date:    2026-11-02

"""
    python tests/ui_check.py --browser webkit --out ui-macOS-webkit.json [--shots DIR]

Starts Job Agent from this folder on a copy of the fictional demo folder and
checks, in the given browser: the search band, the side list with its
counts, the job cards (monogram, deadline box, Accept and Reject), the
accepted job with its file tiles, the profile form, Settings with the
writing style, no page errors, no sideways scrolling at desktop and phone
width, and a dark page in dark mode. The result file holds only what must
be equal everywhere (tests/platform_compare.py compares them); the font the
system uses is reported under "info" and not compared.
"""
import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", required=True, help="chromium, msedge, firefox or webkit")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", default="")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    demo = os.path.join(ROOT, "docs", "demo", "home")
    if not os.path.isdir(demo):
        subprocess.run([sys.executable, "-m", "engine.cli", "demo"], cwd=ROOT, check=True, capture_output=True)
    home = os.path.join(tempfile.mkdtemp(prefix="jae-ui-"), "home")
    shutil.copytree(demo, home)
    port = free_port()
    log = open(os.path.join(os.path.dirname(home), "app.log"), "w")
    proc = subprocess.Popen([sys.executable, "-m", "engine.cli", "--home", home, "app", "--no-browser", "--keep-running", "--port", str(port)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=2).read()
            break
        except Exception:
            time.sleep(0.5)
    out = {"system": platform.system(), "mode": a.browser, "checks": {}, "info": {}}
    c = out["checks"]
    errors = []
    shots = a.shots
    if shots:
        os.makedirs(shots, exist_ok=True)

    def snap(page, name):
        if shots:
            page.screenshot(path=os.path.join(shots, f"{platform.system()}-{a.browser}-{name}.png"), full_page=False)

    def overflow(page):
        return page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")

    try:
        with sync_playwright() as p:
            kind = "chromium" if a.browser in ("chromium", "msedge", "chrome") else a.browser
            opts = {"channel": a.browser} if a.browser in ("msedge", "chrome") else {}
            browser = getattr(p, kind).launch(**opts)
            out["info"]["engine_version"] = browser.version

            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(base + "/")
            page.wait_for_selector(".post", timeout=20000)
            c["search_band"] = page.is_visible(".searchbar #sb-what") and page.is_visible("#btn-search")
            c["search_words_shown"] = bool(page.input_value("#sb-what"))
            c["guide_steps"] = page.locator("#guide .g-steps li").count()
            c["guide_current_step"] = page.get_attribute("#guide .g-steps li.now", "data-g")
            c["rail_items"] = page.eval_on_selector_all("#filters .chip", "bs => bs.filter(b => getComputedStyle(b).display !== 'none').length")
            c["to_decide_count"] = page.text_content("#n-undecided")
            c["cards"] = page.locator(".post").count()
            c["cards_with_monogram_and_deadline"] = page.eval_on_selector_all(".post", "ps => ps.filter(p => p.querySelector('.mono') && p.querySelector('.due')).length")
            c["accept_buttons"] = page.locator("button.yes").count()
            c["desktop_no_sideways_scroll"] = not overflow(page)
            out["info"]["font"] = page.evaluate("getComputedStyle(document.body).fontFamily")
            snap(page, "jobs")
            page.click('#filters .chip[data-f="accepted"]')
            page.wait_for_timeout(500)
            c["accepted_file_tiles"] = page.locator(".file").count()
            snap(page, "accepted")
            page.click('#filters .chip[data-f="unmatched"]')
            page.wait_for_timeout(300)
            c["not_matched_view"] = page.locator("#plist .card").count() > 0
            page.click('#nav button[data-v="setup"]')
            page.wait_for_timeout(1500)
            frame = page.frame_locator("#form")
            c["profile_form"] = frame.locator("textarea").count() > 0
            page.click('#nav button[data-v="settings"]')
            page.wait_for_timeout(500)
            c["settings_menu_items"] = page.eval_on_selector_all(".subnav.side button", "bs => bs.filter(b => getComputedStyle(b).display !== 'none').length")
            page.click('.subnav.side button[data-s="style"]')
            page.wait_for_selector("#ty-chips .chip", timeout=10000)
            c["writing_types"] = page.locator("#ty-chips .chip").count()
            page.click('.subnav.side button[data-s="sites"]')
            page.wait_for_selector("#countries .chip", timeout=10000)
            c["countries"] = page.locator("#countries .chip").count()
            snap(page, "settings")
            page.close()

            phone = browser.new_page(viewport={"width": 390, "height": 844})
            phone.on("pageerror", lambda e: errors.append(str(e)))
            phone.goto(base + "/")
            phone.wait_for_selector(".post", timeout=20000)
            c["phone_no_sideways_scroll"] = not overflow(phone)
            c["phone_search_button"] = phone.is_visible("#btn-search")
            snap(phone, "phone")
            phone.close()

            ctx = browser.new_context(color_scheme="dark", viewport={"width": 1200, "height": 900})
            dark = ctx.new_page()
            dark.on("pageerror", lambda e: errors.append(str(e)))
            dark.goto(base + "/")
            dark.wait_for_selector(".post", timeout=20000)
            bg = dark.evaluate("getComputedStyle(document.body).backgroundColor")
            nums = [int(x) for x in re.findall(r"\d+", bg)[:3]]
            c["dark_page_is_dark"] = bool(nums) and sum(nums) / 3 < 60
            snap(dark, "dark")
            ctx.close()
            browser.close()
    finally:
        proc.kill()
        log.close()
    c["page_errors"] = len(errors)
    if errors:
        out["info"]["errors"] = errors[:10]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))
    ok = (not errors and c.get("cards") and c.get("desktop_no_sideways_scroll") and c.get("phone_no_sideways_scroll")
          and c.get("dark_page_is_dark") and c.get("profile_form"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

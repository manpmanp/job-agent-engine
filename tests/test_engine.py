# Job-search agent engine
# File:    tests/test_engine.py
# Purpose: Offline tests: collectors against recorded API formats, matching, verification, offline behaviour, tracker safety.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.2.0
# Date:    2026-10-28

"""Run with:  ./run.sh test

No network is used: engine.collect.http.transport is replaced by a router
that serves the files in tests/fixtures/.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from engine import home as home_mod, tracker as tr, cli          # noqa: E402
from engine.collect import http, match, sources, verify as verify_mod  # noqa: E402
import engine.collect as collect  # noqa: E402

FX = os.path.join(HERE, "fixtures")


def fx(name):
    with open(os.path.join(FX, name), "rb") as f:
        return f.read()


class Router:
    """Fake transport. routes: list of (substring, status, body or callable)."""
    def __init__(self, routes, default=(404, b"")):
        self.routes, self.default, self.calls = routes, default, []

    def __call__(self, method, url, headers, data):
        self.calls.append((method, url))
        for sub, status, body in self.routes:
            if sub in url:
                return http.Response(status, body() if callable(body) else body, None, url)
        return http.Response(self.default[0], self.default[1], None, url)


def offline(method, url, headers, data):
    return http.Response(0, b"", "URLError: network unreachable", url)


CONFIG = {
    "keywords": ["FPGA engineer", "ASIC design engineer", "embedded hardware engineer"],
    "locations": [{"name": "Västerås", "country": "SE"}, {"name": "Uppsala", "country": "SE"},
                  {"name": "Oslo", "country": "NO", "aliases": ["Bærum"]}],
    "employer_presets": [],
}
EMPLOYERS = {"mode": "extend", "employers": [
    {"name": "Example AI", "urls": ["https://jobs.ashbyhq.com/exampleai"]},
    {"name": "Example GH", "urls": ["https://boards.greenhouse.io/examplegh"]},
    {"name": "Example Lever", "urls": ["https://jobs.lever.co/examplelever"]},
    {"name": "Example WD", "urls": ["https://examplewd.wd3.myworkdayjobs.com/en-US/External"]},
    {"name": "JSONLD Corp", "urls": ["https://jsonld.example/careers"]},
    {"name": "Links Corp", "urls": ["https://links.example/careers"]},
    {"name": "Indeed Only", "urls": ["indeed:Indeed Only"]},
]}


def make_home():
    d = tempfile.mkdtemp(prefix="jae_test_")
    h = home_mod.Home(d)
    cli.main(["--home", d, "init"])
    with open(h.path("search_config"), "w") as f:
        json.dump(CONFIG, f)
    with open(h.path("employers"), "w") as f:
        json.dump(EMPLOYERS, f)
    return h


ROUTES = [
    ("jobsearch.api.jobtechdev.se/search?q=FPGA", 200, lambda: fx("jobtech_fpga.json")),
    ("jobsearch.api.jobtechdev.se/search", 200, lambda: fx("jobtech_empty.json")),
    ("jobsearch.api.jobtechdev.se/ad/90000001", 200, b'{"id": "90000001", "removed": true}'),
    ("api.ashbyhq.com/posting-api/job-board/exampleai", 200, lambda: fx("ashby_board.json")),
    ("boards-api.greenhouse.io/v1/boards/examplegh", 200, lambda: fx("greenhouse_board.json")),
    ("api.lever.co/v0/postings/examplelever", 200, lambda: fx("lever_board.json")),
    ("examplewd.wd3.myworkdayjobs.com/wday/cxs/examplewd/External/jobs", 200, lambda: fx("workday_jobs.json")),
    ("/robots.txt", 404, b""),
    ("jsonld.example/careers", 200, lambda: fx("career_jsonld.html")),
    ("links.example/careers", 200, lambda: fx("career_links.html")),
]


class TestMatching(unittest.TestCase):
    def test_keyword_core_tokens(self):
        self.assertEqual(match.keyword_tokens("FPGA engineer"), ["fpga"])
        self.assertEqual(match.match_keywords("Hardware Developer FPGA", "", ["FPGA engineer"])[1], "title")
        self.assertEqual(match.match_keywords("Digital Designer", "ASIC flow", ["ASIC design engineer"])[1], "description")
        self.assertEqual(match.match_keywords("Säljare", "FPGA", ["FPGA engineer"], exclude_terms=["säljare"])[0], [])

    def test_location_and_accents(self):
        locs = CONFIG["locations"]
        self.assertEqual(match.match_location("Vasteras", locs), "Västerås")
        self.assertEqual(match.match_location("Bærum, Norway", locs), "Oslo")
        self.assertIsNone(match.match_location("Kiruna, Sverige", locs))
        self.assertEqual(match.match_location("Remote - Sweden", locs), "remote")
        self.assertIsNone(match.match_location("Remote - USA", locs))

    def test_seniority(self):
        self.assertEqual(match.seniority("Senior FPGA Engineer"), "Senior")
        self.assertEqual(match.seniority("FPGA Engineer"), "Not stated")
        self.assertEqual(match.seniority("Graduate Digital Design Engineer"), "Graduate")

    def test_ats_detection(self):
        self.assertEqual(sources.detect_ats("https://jobs.ashbyhq.com/axelera")[0], "ashby")
        k, p = sources.detect_ats("https://axis.wd3.myworkdayjobs.com/External_Career_Site")
        self.assertEqual((k, p["tenant"], p["site"]), ("workday", "axis", "External_Career_Site"))
        self.assertEqual(sources.detect_ats("https://examplewd.wd3.myworkdayjobs.com/en-US/External")[1]["site"], "External")
        self.assertEqual(sources.detect_ats("indeed:AFRY")[0], "agent_only")
        self.assertEqual(sources.detect_ats("https://www.example.com/careers")[0], "html")


class TestCollect(unittest.TestCase):
    def setUp(self):
        http.DELAY = 0
        http.RETRY_WAIT = 0
        http._robots.clear()
        self.h = make_home()

    def tearDown(self):
        http.transport = http._urllib_transport
        shutil.rmtree(self.h.root, ignore_errors=True)

    def test_full_collect(self):
        http.transport = Router(ROUTES)
        s = collect.collect(self.h, run_date="2026-11-02")
        rows = {r["Title"]: r for r in tr.read_all_rows(self.h.path("tracker"))}
        self.assertIn("Hardware Developer FPGA", rows)                 # JobTech, Västerås
        self.assertNotIn("Senior FPGA Engineer", rows)                 # Kiruna: location filter
        self.assertNotIn("Säljare", rows)                              # description-only mention, title unrelated: dropped
        self.assertIn("Digital Design Engineer, ASIC", rows)           # Ashby, description match
        self.assertNotIn("Marketing Manager", rows)
        self.assertIn("FPGA Engineer", rows)                           # Greenhouse, Oslo
        self.assertIn("Embedded Hardware Engineer", rows)              # Lever, Vasteras
        self.assertIn("ASIC Design Engineer", rows)                    # Workday
        self.assertIn("ASIC Verification Engineer", rows)              # Workday "2 Locations" kept for checking
        self.assertIn("Hardware Engineer, FPGA", rows)                 # JSON-LD page
        self.assertIn("FPGA Developer", rows)                          # link lead
        self.assertEqual(rows["FPGA Developer"]["Status"], "Unverified")
        self.assertEqual(tr.to_date(rows["Hardware Developer FPGA"]["Announce Date"]).isoformat(), "2026-10-21")
        self.assertEqual(rows["Hardware Developer FPGA"]["Remote/Hybrid/Onsite"], "Hybrid")
        self.assertEqual(rows["ASIC Design Engineer"]["URL"],
                         "https://examplewd.wd3.myworkdayjobs.com/External/job/Sweden---Uppsala/ASIC-Design-Engineer_R-555001")
        self.assertIn("Indeed Only", s["skipped_agent_only"])
        self.assertEqual(s["errors"], [])
        # second run: nothing new, existing rows untouched
        before = tr.read_all_rows(self.h.path("tracker"))
        s2 = collect.collect(self.h, run_date="2026-11-09")
        self.assertEqual(s2["new"], 0)
        self.assertEqual(len(tr.read_all_rows(self.h.path("tracker"))), len(before))

    def test_collect_never_overwrites_decisions(self):
        http.transport = Router(ROUTES)
        collect.collect(self.h, run_date="2026-11-02")
        row = [r for r in tr.read_all_rows(self.h.path("tracker")) if r["Title"] == "FPGA Engineer"][0]
        row = dict(row, Status="Approved - ready for tailored documents")
        tr.update(self.h.path("tracker"), [row])
        collect.collect(self.h, run_date="2026-11-09")
        row2 = [r for r in tr.read_all_rows(self.h.path("tracker")) if r["Title"] == "FPGA Engineer"][0]
        self.assertTrue(row2["Status"].startswith("Approved"))

    def test_offline_completes(self):
        http.transport = offline
        s = collect.collect(self.h, run_date="2026-11-02")
        self.assertEqual(s["new"], 0)
        self.assertTrue(s["errors"])
        cli.main(["--home", self.h.root, "run", "weekly"])          # full run must not crash offline

    def test_verify(self):
        http.transport = Router(ROUTES)
        collect.collect(self.h, run_date="2026-11-02")
        routes = [("jobsearch.api.jobtechdev.se/ad/90000001", 200, b'{"removed": true}'),
                  ("/robots.txt", 404, b""),
                  ("jsonld.example/jobs/7", 200, lambda: fx("expired_jsonld.html")),
                  ("", 200, b"<html>open</html>")]
        http.transport = Router(routes)
        c = verify_mod.verify(self.h)
        rows = {r["Title"]: r for r in tr.read_all_rows(self.h.path("tracker"))}
        self.assertEqual(rows["Hardware Developer FPGA"]["Status"], "Expired")
        self.assertEqual(rows["Hardware Engineer, FPGA"]["Status"], "Expired")
        self.assertEqual(rows["FPGA Engineer"]["Status"], "New")
        self.assertGreaterEqual(c["expired"], 2)

    def test_verify_offline_changes_nothing(self):
        http.transport = Router(ROUTES)
        collect.collect(self.h, run_date="2026-11-02")
        before = tr.read_all_rows(self.h.path("tracker"))
        http.transport = offline
        verify_mod.verify(self.h)
        after = tr.read_all_rows(self.h.path("tracker"))
        self.assertEqual([r["Notes"] for r in before], [r["Notes"] for r in after])


class TestEnrich(unittest.TestCase):
    def setUp(self):
        http.DELAY = 0
        http.RETRY_WAIT = 0
        self.h = make_home()

    def tearDown(self):
        http.transport = http._urllib_transport
        os.environ.pop("ANTHROPIC_API_KEY", None)
        shutil.rmtree(self.h.root, ignore_errors=True)

    def test_off_without_key(self):
        from engine import enrich
        self.assertFalse(enrich.status(self.h)[0])
        self.assertEqual(enrich.enrich(self.h)["reviewed"], 0)

    def test_with_fake_api(self):
        from engine import enrich
        http.transport = Router(ROUTES)
        collect.collect(self.h, run_date="2026-11-02")
        with open(self.h.path("search_config")) as f:
            cfg = json.load(f)
        cfg["enrichment"] = {"enabled": True, "max_per_run": 3}
        with open(self.h.path("search_config"), "w") as f:
            json.dump(cfg, f)
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        reply = json.dumps({"content": [{"type": "text", "text": json.dumps({
            "category": "Industry - Engineering/Design", "seniority": "Experienced", "arrangement": "Hybrid",
            "skills": "VHDL, FPGA", "fit": "Mid-level FPGA design role."})}]}).encode()
        router = Router([("api.anthropic.com/v1/messages", 200, reply)])
        http.transport = router
        res = enrich.enrich(self.h)
        self.assertEqual(res["reviewed"], 3)
        self.assertTrue(any("api.anthropic.com" in u for _, u in router.calls))
        reviewed = [r for r in tr.read_all_rows(self.h.path("tracker")) if "AI-reviewed" in str(r.get("Notes"))]
        self.assertEqual(len(reviewed), 3)


if __name__ == "__main__":
    unittest.main()

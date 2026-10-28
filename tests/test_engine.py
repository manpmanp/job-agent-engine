# Job-search agent engine
# File:    tests/test_engine.py
# Purpose: Offline tests: collectors against recorded API formats, matching, verification, offline behaviour, tracker safety.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
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
        self.routes, self.default, self.calls, self.headers = routes, default, [], []

    def __call__(self, method, url, headers, data):
        self.calls.append((method, url))
        self.headers.append(dict(headers or {}))
        for sub, status, body in self.routes:
            if sub in url:
                return http.Response(status, body() if callable(body) else body, None, url)
        return http.Response(self.default[0], self.default[1], None, url)


def offline(method, url, headers, data):
    return http.Response(0, b"", "URLError: network unreachable", url)


CONFIG = {
    "keywords": ["FPGA engineer", "ASIC design engineer", "embedded hardware engineer", "ASIC verification engineer"],
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
    ("examplewd.wd3.myworkdayjobs.com/wday/cxs/examplewd/External/job/", 200,
     b'{"jobPostingInfo": {"jobDescription": "<p>RTL design in SystemVerilog, UVM testbenches.</p>", "startDate": "2026-10-25", "remoteType": "Hybrid"}}'),
    ("/robots.txt", 404, b""),
    ("jsonld.example/careers", 200, lambda: fx("career_jsonld.html")),
    ("links.example/careers", 200, lambda: fx("career_links.html")),
]


class TestMatching(unittest.TestCase):
    def test_keyword_core_tokens(self):
        self.assertEqual(match.keyword_tokens("FPGA engineer"), ["fpga"])
        self.assertEqual(match.match_keywords("Hardware Developer FPGA", "", ["FPGA engineer"])[1], "title")
        self.assertEqual(match.match_keywords("Digital Designer", "work in the ASIC design flow", ["ASIC design engineer"])[1], "description")
        self.assertIsNone(match.match_keywords("Digital Designer", "ASIC flow and design reviews", ["ASIC design engineer"])[1])
        self.assertEqual(match.match_keywords("Säljare", "FPGA", ["FPGA engineer"], exclude_terms=["säljare"])[0], [])
        # description match needs the core words as one phrase
        self.assertEqual(match.keyword_tokens("digital design engineer"), ["digital", "design"])
        self.assertEqual(match.match_keywords("Frontend Engineer", "digital products with a great design", ["digital design engineer"])[1], None)
        self.assertEqual(match.match_keywords("Hardware Engineer", "experience in digital design and RTL", ["digital design engineer"])[1], "description")

    def test_location_and_accents(self):
        locs = CONFIG["locations"]
        self.assertEqual(match.match_location("Vasteras", locs), "Västerås")
        self.assertEqual(match.match_location("Bærum, Norway", locs), "Oslo")
        self.assertIsNone(match.match_location("Kiruna, Sverige", locs))
        self.assertEqual(match.match_location("Remote - Sweden", locs), "remote")
        self.assertIsNone(match.match_location("Remote - USA", locs))

    def test_employer_suffixes(self):
        self.assertEqual(match.norm_key("Example Systems Aktiebolag", "FPGA Engineer"),
                         match.norm_key("Example Systems", "FPGA Engineer"))
        self.assertEqual(match.norm_employer("Example A/S"), match.norm_employer("Example"))

    def test_seniority(self):
        self.assertEqual(match.seniority("ASIC Design Engineering Manager"), "Manager")
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


class TestNamingAndSkills(unittest.TestCase):
    def test_basename(self):
        from engine import doc_naming as d
        self.assertEqual(d.build_basename("Example AB", "ASIC Engineer, Uppsala", "Uppsala, Uppsala, Uppsala län, Sverige",
                                          "https://arbetsformedlingen.se/platsbanken/annonser/12345678"),
                         "Example_AB_ASIC_Engineer_Uppsala_12345678")
        self.assertEqual(d.build_basename("Example AB", "FPGA Engineer", "Västerås, Sverige"), "Example_AB_FPGA_Engineer_Västerås")
        # Workday style "Country - City", city already in the title
        self.assertEqual(d.build_basename("Example AB", "SoC Architect, Lund", "Sweden - Lund",
                                          "https://x.wd3.myworkdayjobs.com/Ext/job/Sweden---Lund/SoC-Architect--Lund_R-123784"),
                         "Example_AB_SoC_Architect_Lund_R-123784")
        self.assertEqual(d.city_of("Region Skåne, Malmö"), "Malmö")
        self.assertEqual(d.city_of("Skåne län - Lund"), "Lund")

    def test_spaced_headings(self):
        from engine.profile import _join_spaced_headings
        self.assertEqual(_join_spaced_headings("PR OF ES SI ON AL  PR OF ILE"), "PROFESSIONAL PROFILE")
        self.assertEqual(_join_spaced_headings("Normal line of text"), "Normal line of text")
        for raw, want in (("PR OF ES SI ON AL PR OF ILE", "PROFESSIONAL PROFILE"), ("EDU CATION", "EDUCATION"),
                          ("TECHN ICAL S KIL LS", "TECHNICAL SKILLS"), ("RE FE R EN CES", "REFERENCES"),
                          ("AXI AHB APB", "AXI AHB APB"), ("CPF UPF", "CPF UPF")):
            self.assertEqual(_join_spaced_headings(raw), want)

    def test_stated_deadline_and_junior_note(self):
        self.assertEqual(sources.stated_deadline("Type of Employment\nPermanent\n Posting End Date\n2026-11-12 "), "2026-11-12")
        self.assertEqual(sources.stated_deadline("Sista ansökningsdag: 2026-11-30"), "2026-11-30")
        self.assertEqual(sources.stated_deadline("Founded 2001-01-01"), "")
        self.assertTrue(match.welcomes_junior("We welcome both junior and senior engineers who bring"))
        self.assertTrue(match.welcomes_junior("Vi söker juniora och seniora ingenjörer"))
        self.assertFalse(match.welcomes_junior("Senior engineer with 10 years of experience"))

    def test_jd_snapshot_html(self):
        import datetime, tempfile
        from engine import documents
        self.assertEqual(documents._date_only(datetime.datetime(2026, 10, 22)), "2026-10-22")
        self.assertEqual(documents._date_only("2026-11-13 00:00:00"), "2026-11-13")
        self.assertEqual(documents._text_to_html(" a \n b \n\n \n c "), "<p>a<br>b</p><p>c</p>")

    def test_skills_from_description(self):
        s = match.skills_summary("SystemVerilog and UVM, C and C++ on Linux. Go-to person. C-level contact.", match.default_vocabulary())
        for t in ("SystemVerilog", "UVM", "C", "C++", "Linux"):
            self.assertIn(t, s)
        self.assertNotIn("Go", s.split(", "))
        self.assertEqual(match.skills_summary("you can do it", match.default_vocabulary()), "")

    def test_template_uses_description(self):
        from engine import documents
        row = {"Title": "Verification Engineer", "Employer": "Example AB", "Required Skills (summary)": "not extracted, see posting"}
        cv, cl = documents.template_specs(row, description="You will build UVM testbenches in SystemVerilog and run regressions in Python.")
        table = [r[0] for s in cv["sections"] if s["heading"] == "Technical Skills" for r in s["table"]]
        self.assertIn("UVM", table)
        self.assertIn("SystemVerilog", table)


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
        self.assertIn("SystemVerilog", rows["ASIC Design Engineer"]["Required Skills (summary)"])  # Workday details
        self.assertEqual(rows["ASIC Design Engineer"]["Remote/Hybrid/Onsite"], "Hybrid")
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


class TestIntakeFolders(unittest.TestCase):
    def setUp(self):
        self.h = make_home()

    def tearDown(self):
        shutil.rmtree(self.h.root, ignore_errors=True)

    def test_scan_imports_once(self):
        from engine.profile import Intake
        it = Intake(self.h)
        self.assertTrue(os.path.isdir(self.h.path("intake_cv")))
        with open(os.path.join(self.h.path("intake_cv"), "cv.md"), "w") as f:
            f.write("# Test Person\nFPGA developer")
        with open(os.path.join(self.h.path("intake_cl"), "letter.rtf"), "w") as f:
            f.write("x")
        r1 = it.scan_intake_folders()
        self.assertEqual(len(r1["imported"]), 1)
        self.assertEqual(r1["unsupported"], ["cl/letter.rtf"])
        r2 = it.scan_intake_folders()
        self.assertEqual(r2["imported"], [])
        self.assertEqual(r2["skipped"], ["cv/cv.md"])
        self.assertTrue(self.h.capabilities()["tailoring_full"][0])
        listing = it.folder_listing()
        self.assertEqual(listing["cv"]["files"][0]["imported_as"], r1["imported"][0]["id"])


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


class TestExtractAndSources(unittest.TestCase):
    def setUp(self):
        http.DELAY = 0
        http.RETRY_WAIT = 0
        http._robots.clear()
        self.h = make_home()

    def tearDown(self):
        http.transport = http._urllib_transport
        shutil.rmtree(self.h.root, ignore_errors=True)

    def test_structured_posting(self):
        from engine.collect import extract
        d = extract.read_html(fx("posting_structured.html").decode(), "https://links.example/careers/fpga-developer")
        self.assertEqual(d["how"], "structured")
        self.assertEqual((d["title"], d["employer"], d["location_text"]), ("FPGA Developer", "Links Corp", "Uppsala, SE"))
        self.assertEqual((d["published"], d["deadline"]), ("2026-10-20", "2026-12-01"))
        self.assertEqual(d["salary"], "SEK 45000-60000 per month")
        self.assertEqual(d["employment_type"], "full time")
        self.assertIn("- VHDL or SystemVerilog", d["description"])      # escaped HTML read, list items kept
        self.assertTrue(d["complete"])

    def test_page_text_and_shell(self):
        from engine.collect import extract
        d = extract.read_html(fx("posting_plain.html").decode())
        self.assertEqual(d["how"], "page")
        self.assertTrue(d["complete"])
        self.assertIn("- Write C firmware", d["description"])
        for noise in ("Cookie settings", "Copyright", "ignore me", "Home"):
            self.assertNotIn(noise, d["description"])
        self.assertEqual(sources.stated_deadline(d["description"]), "2026-11-30")
        self.assertFalse(extract.read_html(fx("posting_shell.html").decode())["complete"])

    def test_robots_rules(self):
        r = http.parse_robots("User-agent: *\nDisallow: /jobs\nAllow: /jobs/view\nDisallow: /*.pdf$\n\n"
                              "User-agent: job-agent-engine\nDisallow: /private")
        self.assertEqual(r, [(False, "/private")])                    # own group replaces '*'
        r = http.parse_robots("User-agent: *\nDisallow: /jobs\nAllow: /jobs/view\nDisallow: /*.pdf$")
        self.assertFalse(http.robots_allow(r, "/jobs/1"))
        self.assertTrue(http.robots_allow(r, "/jobs/view/1"))         # longest match wins
        self.assertFalse(http.robots_allow(r, "/a.pdf"))
        self.assertTrue(http.robots_allow(r, "/a.pdf?x=1"))
        self.assertFalse(http.robots_allow("none", "/"))
        http.transport = Router([("/robots.txt", 403, b"")])
        self.assertFalse(http.robots_allowed("https://refuses.example/jobs"))  # 403 on robots.txt: not now
        self.assertFalse(http.is_public_host("127.0.0.1"))
        self.assertFalse(http.is_public_host("192.168.1.10"))

    def test_lead_is_confirmed_from_posting_page(self):
        http.transport = Router([("links.example/careers/fpga-developer", 200, lambda: fx("posting_structured.html"))] + ROUTES)
        collect.collect(self.h, run_date="2026-11-02", only="employers")
        rows = {r["Title"]: r for r in tr.read_all_rows(self.h.path("tracker"))}
        r = rows["FPGA Developer"]
        self.assertEqual(r["Status"], "New")                           # no longer an unconfirmed lead
        self.assertEqual(r["Location"], "Uppsala, SE")
        self.assertEqual(tr.to_date(r["Deadline"]).isoformat(), "2026-12-01")
        self.assertIn("structured data", r["Notes"])

    def test_aggregators(self):
        cfg = dict(CONFIG, sources={"jobtech": False, "employer_sites": False, "jsearch": True, "hn_who_is_hiring": True})
        with open(self.h.path("search_config"), "w") as f:
            json.dump(cfg, f)
        with open(os.path.join(self.h.path("inputs"), "secrets.json"), "w") as f:
            json.dump({"jsearch_api_key": "test"}, f)
        router = Router([("api.openwebninja.com/jsearch/search-v2", 200, lambda: fx("jsearch.json")),
                         ("hn.algolia.com/api/v1/search_by_date", 200, lambda: fx("hn_search.json")),
                         ("hn.algolia.com/api/v1/items/777", 200, lambda: fx("hn_thread.json"))])
        http.transport = router
        s = collect.collect(self.h, run_date="2026-11-02")
        rows = {(r["Employer"], r["Title"]): r for r in tr.read_all_rows(self.h.path("tracker"))}
        self.assertEqual(rows[("Radio AB", "FPGA Engineer")]["URL"], "https://radio.example/jobs/9")  # employer's own link
        self.assertEqual(rows[("Radio AB", "FPGA Engineer")]["Location"], "Uppsala")
        self.assertIn(("Edgechip", "FPGA Engineer"), rows)
        self.assertNotIn("Webshop", [k[0] for k in rows])               # San Francisco: location filter
        self.assertEqual(s["errors"], [])
        self.assertTrue(all("test" not in u for _m, u in router.calls))   # the key goes in a header, not the URL
        self.assertTrue(any(h.get("x-api-key") == "test" for h in router.headers))

    def test_fetch_command_adds_posting(self):
        http.transport = Router([("plain.example/jobs/1", 200, lambda: fx("posting_plain.html")), ("/robots.txt", 404, b"")])
        cli.main(["--home", self.h.root, "fetch", "https://plain.example/jobs/1", "--add", "--employer", "Plain AB",
                  "--title", "Embedded Engineer"])
        rows = [r for r in tr.read_all_rows(self.h.path("tracker")) if r["Employer"] == "Plain AB"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(tr.to_date(rows[0]["Deadline"]).isoformat(), "2026-11-30")  # stated in the text
        from engine import documents
        self.assertIn("ARM Cortex-M", documents.saved_description(self.h, "https://plain.example/jobs/1"))

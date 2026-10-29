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
        k, p = sources.detect_ats("https://exampleco.wd3.myworkdayjobs.com/External_Career_Site")
        self.assertEqual((k, p["tenant"], p["site"]), ("workday", "exampleco", "External_Career_Site"))
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
        with open(self.h.path("all_listings"), encoding="utf-8") as f:
            unm = {x["title"]: x for x in json.load(f)["listings"]}      # every job seen, with why it was left out
        self.assertEqual(unm["Senior FPGA Engineer"]["why"], "outside your places")
        self.assertEqual(unm["Marketing Manager"]["why"], "none of your keywords")
        self.assertNotIn("FPGA Engineer", unm)                         # matched ones are postings, not listed here
        self.assertEqual(s["not_matched"], len(unm))
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



class JobSitesCatalogue(unittest.TestCase):
    def test_catalogue_is_complete(self):
        with open(os.path.join(home_mod.DEFAULTS_DIR, "job_sites.json"), encoding="utf-8") as f:
            d = json.load(f)
        eu27 = "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
        for code in eu27 + ["NO", "IS", "LI", "CH", "GB", "US", "CA", "AU"]:
            self.assertIn(code, d["countries"], code)
        for code, c in d["countries"].items():
            self.assertIn(c["region"], d["regions"], code)
            self.assertTrue(c["sources"], code)
            for s in c["sites"] + d["international"] + d["academic"]["sites"]:
                self.assertIn(s["access"], d["access_types"])
                self.assertTrue(s["url"].startswith("https://"), s["url"])

if __name__ == "__main__":
    unittest.main()


class TestConventions(unittest.TestCase):
    """The same role is written differently for a US and a Swedish employer."""
    def setUp(self):
        from engine import conventions
        self.c = conventions
        self.h = make_home()

    def row(self, title, location, category="Industry - Engineering/Design", seniority=None):
        from engine.collect import match as m
        return {"Title": title, "Employer": "Example Inc", "Location": location, "Category": category,
                "Seniority Level": seniority or m.seniority(title), "URL": "https://example.com/j/1"}

    def test_market_and_type(self):
        us = self.c.for_row(self.h, self.row("Senior ASIC Design Engineer", "San Diego, CA"))
        se = self.c.for_row(self.h, self.row("ASIC Design Engineer", "Lund, Sweden"))
        self.assertEqual((us["market"], us["type"], us["group"], us["page_size"]), ("us", "senior", "industry", "Letter"))
        self.assertEqual((se["market"], se["type"], se["page_size"]), ("nordic", "mid_senior", "A4"))
        self.assertEqual(self.c.closing(us), "Sincerely,")
        self.assertEqual(self.c.closing(se), "Kind regards,")
        pd = self.c.for_row(self.h, self.row("Postdoc in computer architecture", "Gothenburg, Sweden", "Academia - Postdoc/Researcher"))
        self.assertEqual((pd["group"], pd["type"]), ("academia", "postdoc"))
        types = {t: self.c.type_of(self.row(t, "Lund, Sweden", c), None) for t, c in [
            ("PhD student in hardware design", ""), ("Assistant professor in computer engineering", ""),
            ("Biträdande universitetslektor", ""), ("Associate Professor", ""), ("Universitetslektor i elektronik", ""),
            ("Research engineer", "Academia - Research Engineer/Assistant"), ("Master thesis: FPGA", ""),
            ("Graduate FPGA Engineer", ""), ("Staff Engineer", "")]}
        self.assertEqual(list(types.values()), ["phd", "assistant_professor", "assistant_professor", "professor", "lecturer",
                                                "research_assistant", "internship", "junior", "senior"])
        self.assertEqual(self.c.for_row(self.h, self.row("Graduate FPGA Engineer", "Toronto, ON"))["market"], "canada")
        self.assertEqual(self.c.for_row(self.h, self.row("FPGA Engineer", "Remote"), {})["market"], "international")
        self.assertIn("Market: United States", self.c.as_text(us))

    def test_override_and_own_file(self):
        r = self.row("FPGA Engineer", "San Diego, CA")
        self.assertEqual(self.c.for_row(self.h, r, {"document_market": "nordic"})["market"], "us")      # detected country wins
        self.assertEqual(self.c.for_row(self.h, self.row("FPGA Engineer", "Remote"), {"document_market": "nordic"})["market"], "nordic")
        with open(self.h.path("document_conventions"), "w") as f:
            json.dump({"markets": {"us": {"letter": {"closing": "Best regards,"}}}}, f)
        conv = self.c.for_row(self.h, r)
        self.assertEqual(self.c.closing(conv), "Best regards,")
        self.assertEqual(conv["page_size"], "Letter")                     # the rest of the market stays
        self.assertEqual(self.c.style_for(self.h, conv)["page_size"], "Letter")

    def test_postdoc_and_engineer_differ(self):
        from engine import documents as d
        pd = self.c.for_row(self.h, self.row("Postdoc in computer architecture", "Lund, Sweden", "Academia - Postdoc/Researcher"))
        en = self.c.for_row(self.h, self.row("ASIC Design Engineer", "Lund, Sweden"))
        heads = lambda conv, r: [s["heading"] for s in d.template_specs(r, {}, conv=conv)[0]["sections"]]
        hp = heads(pd, self.row("Postdoc in computer architecture", "Lund, Sweden"))
        he = heads(en, self.row("ASIC Design Engineer", "Lund, Sweden"))
        self.assertLess(hp.index("Education"), hp.index("Publications"))
        self.assertNotIn("Publications", he)
        self.assertLess(he.index("Work Experience"), he.index("Education"))
        self.assertNotEqual(pd["confidence"], en["confidence"] + 10)
        self.assertIn("Confidence for this position type", self.c.as_text(pd))
        self.assertIn("Research Profile", self.c.as_text(pd))

    def test_tuning_and_per_posting_choice(self):
        data = self.c.editor_data(self.h)
        self.assertEqual(len(data["order"]["academia"]) + len(data["order"]["industry"]), 10)
        mine = dict(data["types"]["postdoc"])
        mine["sections"] = [{"heading": "Publications", "length": "full"}, {"heading": "Research Experience", "length": "detailed"},
                            {"heading": "Hobbies", "length": "off"}]
        mine["confidence"] = 9
        res = self.c.save_type(self.h, "postdoc", mine)
        self.assertEqual(res["tuned"], ["postdoc"])
        r = self.row("Postdoc in hardware", "Lund, Sweden", "Academia - Postdoc/Researcher")
        conv = self.c.for_row(self.h, r)
        self.assertEqual([s["heading"] for s in conv["sections"]][:2], ["Publications", "Research Experience"])
        self.assertEqual(conv["confidence"], 5)                               # clamped
        self.assertNotIn("Hobbies", self.c.as_text(conv).split("Left out")[0])
        self.c.save_type(self.h, "postdoc", None)
        self.assertEqual(self.c.editor_data(self.h)["tuned"], [])
        self.c.set_choice(self.h, self.c.posting_key(r), "lecturer", "us")
        conv = self.c.for_row(self.h, r)
        self.assertEqual((conv["type"], conv["market"], conv["auto"]["type"], conv["chosen"]["type"]), ("lecturer", "us", "postdoc", True))
        self.c.set_choice(self.h, self.c.posting_key(r))
        self.assertEqual(self.c.for_row(self.h, r)["type"], "postdoc")

    def test_templates_and_checks(self):
        from engine import documents as d
        us = self.c.for_row(self.h, self.row("FPGA Engineer", "Austin, TX"))
        cv, cl = d.template_specs(self.row("FPGA Engineer", "Austin, TX"), {}, conv=us)
        heads = [s["heading"] for s in cv["sections"]]
        self.assertNotIn("References", heads)                             # US: no references line
        self.assertRegex(cl["date"], r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")
        jr = self.c.for_row(self.h, self.row("Graduate FPGA Engineer", "Lund, Sweden"))
        heads = [s["heading"] for s in d.template_specs(self.row("Graduate FPGA Engineer", "Lund, Sweden"), {}, conv=jr)[0]["sections"]]
        self.assertLess(heads.index("Education"), heads.index("Work Experience"))
        ac = self.c.for_row(self.h, self.row("Postdoc in hardware", "Lund, Sweden", "Academia - Postdoc/Researcher"))
        heads = [s["heading"] for s in d.template_specs(self.row("Postdoc in hardware", "Lund, Sweden"), {}, conv=ac)[0]["sections"]]
        self.assertIn("Publications", heads)
        self.assertIn("Research Experience", heads)
        self.assertIn("References", heads)                                # academia keeps referees
        spec = {"type": "cv", "mode": "full", "banner": {"name": "Jane Example"},
                "sections": [{"heading": "Profile", "paragraphs": ["Date of birth: 1990-01-01"]}]}
        self.assertTrue(d.check_spec(spec, self.c.checks_for(self.h, us)))
        self.assertFalse(d.check_spec(spec, self.c.checks_for(self.h, jr)))  # not a rule in the Nordic market


class TestReset(unittest.TestCase):
    def test_reset_moves_to_backup_and_recreates(self):
        from engine import reset as rs
        h = make_home()
        with open(os.path.join(h.path("inputs"), "secrets.json"), "w") as f:
            json.dump({"jsearch_api_key": "k"}, f)
        with open(h.path("document_choices"), "w") as f:
            json.dump({"x||y": {"type": "phd"}}, f)
        res = rs.reset(h, ["settings", "postings"])
        self.assertTrue(os.path.isdir(res["backup"]))
        self.assertIn("inputs/search_config.json", [p.replace(os.sep, "/") for p in res["moved"]])
        with open(os.path.join(res["backup"], "inputs", "search_config.json")) as f:
            self.assertEqual(json.load(f), CONFIG)                              # the old settings are kept in the backup
        self.assertEqual(h.search_config()["keywords"], [])                    # fresh blank settings
        self.assertTrue(os.path.exists(h.path("tracker")))                     # state recreated
        self.assertFalse(os.path.exists(h.path("document_choices")))
        self.assertTrue(os.path.exists(os.path.join(h.path("inputs"), "secrets.json")))   # keys not chosen: kept
        with self.assertRaises(ValueError):
            rs.reset(h, [])


class TestNetworkLog(unittest.TestCase):
    def test_requests_are_recorded_without_secrets(self):
        from engine import netlog
        h = make_home()
        old = (http.transport, http.LOG_PATH, http.DELAY)
        http.transport = lambda m, u, hd, d: http.Response(200, b'{"ok": true}', None, u, "application/json")
        http.LOG_PATH, http.DELAY = netlog.log_path(h), 0
        try:
            http.get_json("https://api.adzuna.com/v1/api/jobs/gb/search/1?what=FPGA&where=Cambridge&app_id=ID1&app_key=SECRET9",
                          headers={"Authorization": "Bearer TOKEN7"})
            with http.sending("your profile and the posting"):
                http.post_json("https://api.anthropic.com/v1/messages", {"model": "m", "messages": []}, headers={"x-api-key": "sk-XYZ"})
            http.post_json("https://example.com/api/sync/decisions", {"decisions": {}})
        finally:
            http.transport, http.LOG_PATH, http.DELAY = old
        with open(netlog.log_path(h), encoding="utf-8") as f:
            raw = f.read()
        for secret in ("SECRET9", "ID1", "TOKEN7", "sk-XYZ"):
            self.assertNotIn(secret, raw)
        self.assertIn("what=FPGA", raw)                                         # the search terms you share are shown
        rep = netlog.report(h)
        self.assertEqual(rep["total"], 3)
        by = {g["purpose"]: g for g in rep["summary"]}
        self.assertIn("Job search: Adzuna", by)
        self.assertIn("Your online Job Agent", by)
        ai = next(x for x in rep["recent"] if x["host"] == "api.anthropic.com")
        self.assertEqual(ai["sent"], "your profile and the posting")
        self.assertGreater(ai["sent_bytes"], 0)


class TestWindowsConsole(unittest.TestCase):
    def test_child_programs_start_without_a_window_on_windows(self):
        import subprocess
        from unittest import mock
        import engine

        class FakePopen:
            def __init__(self, *a, **kw):
                self.kw = kw
        with mock.patch("os.name", "nt"), mock.patch.object(subprocess, "Popen", FakePopen):
            engine._hide_console_windows()
            self.assertEqual(subprocess.Popen(["schtasks"]).kw["creationflags"], 0x08000000)
            self.assertEqual(subprocess.Popen(["x"], creationflags=0x10).kw["creationflags"], 0x10)   # explicit flags kept


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


class TestApp(unittest.TestCase):
    """The local app's API, against a real server on a free port."""

    @classmethod
    def setUpClass(cls):
        import threading, base64  # noqa: F401
        from engine import app as app_mod
        cls.h = make_home()
        rows = [{"Date Found": "2026-11-02", "Title": "FPGA Engineer", "Employer": "Example AB", "Location": "Uppsala",
                 "Category": "Other", "Seniority Level": "Not stated", "Announce Date": "2026-10-30", "Deadline": "2026-12-01",
                 "Remote/Hybrid/Onsite": "Onsite", "Required Skills (summary)": "VHDL", "URL": "https://example.com/j/1",
                 "Calendar Event Added (Y/N)": "N", "CV/Cover Letter Drafted (Y/N)": "N", "Status": "New", "Notes": "test"}]
        tr.update(cls.h.path("tracker"), rows)
        cls.token = "testtoken"
        jobs = app_mod.Jobs()
        ref = [None]
        from http.server import ThreadingHTTPServer
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), app_mod._make_handler(cls.h, cls.token, jobs, ref))
        ref[0] = cls.httpd
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.h.root, ignore_errors=True)

    def call(self, path, body=None, token=True, host=None):
        import urllib.request, urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method="GET" if body is None else "POST",
                                     data=None if body is None else json.dumps(body).encode())
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("X-Agent-Token", self.token)
        if host:
            req.add_header("Host", host)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def j(self, *a, **k):
        code, body = self.call(*a, **k)
        return code, json.loads(body or b"{}")

    def test_guards(self):
        self.assertEqual(self.call("/api/status", token=False)[0], 403)
        self.assertEqual(self.call("/api/status", host="evil.example")[0], 403)
        code, page = self.call("/", token=False)
        self.assertEqual(code, 200)
        self.assertIn(b'"token": "testtoken"', page)                        # injected for the page itself
        self.assertEqual(self.call("/file?p=../inputs/search_config.json&t=testtoken")[0], 404)  # outside output/

    def test_status_decide_undo(self):
        code, st = self.j("/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(st["counts"]["undecided"], 1)
        key = "https://example.com/j/1||FPGA Engineer"
        self.assertEqual(self.j("/api/decision", {"key": key, "decision": "accepted"})[0], 200)
        _, p = self.j("/api/postings")
        self.assertTrue(p["postings"][0]["status"].startswith("Approved"))
        self.assertEqual(self.j("/api/decision", {"key": key, "decision": "undo"})[0], 200)
        self.assertEqual(self.j("/api/postings")[1]["postings"][0]["status"], "New")
        self.assertEqual(self.j("/api/decision", {"key": key, "decision": "rejected", "reasons": ["Seniority level mismatch"]})[0], 200)
        self.assertTrue(self.j("/api/postings")[1]["postings"][0]["status"].startswith("Rejected: Seniority"))
        self.j("/api/decision", {"key": key, "decision": "undo"})

    def test_upload_and_settings(self):
        import base64
        code, r = self.j("/api/intake/upload", {"name": "cv.txt", "kind": "cv", "data": base64.b64encode(b"Jane Example\nFPGA engineer").decode()})
        self.assertEqual(code, 200)
        self.assertEqual(self.j("/api/intake/upload", {"name": "x.exe", "data": ""})[0], 400)
        _, st = self.j("/api/status")
        self.assertEqual(len(st["awaiting_extraction"]), 1)
        _, s = self.j("/api/settings", {"secrets": {"anthropic_api_key": "sk-test"}, "sources": {"jsearch": True}})
        self.assertTrue(s["secrets"]["anthropic_api_key"])
        self.assertNotIn("sk-test", json.dumps(s))                         # keys are never sent back
        self.assertTrue(self.h.search_config()["sources"]["jsearch"])
        self.assertTrue(self.h.search_config()["sources"].get("jobtech", True))
        self.j("/api/settings", {"secrets": {"anthropic_api_key": "__clear__"}, "sources": {"jsearch": False}})

    def test_job_sites(self):
        code, cat = self.j("/api/job_sites")
        self.assertEqual(code, 200)
        self.assertIn("SE", cat["countries"])
        sel = {"countries": ["DK", "SE"], "skip": ["https://www.jobindex.dk"], "custom": [{"name": "X", "url": "https://x.example"}]}
        self.j("/api/search_config", {"job_sites": sel})
        self.assertEqual(self.h.search_config()["job_sites"], sel)
        self.j("/api/settings", {"sources": {"jobtech": False}})              # the tab's own save keeps keys and other settings
        self.assertFalse(self.h.search_config()["sources"]["jobtech"])
        self.j("/api/settings", {"sources": {"jobtech": True}})

    def test_writing_style_api(self):
        code, w = self.j("/api/writing")
        self.assertEqual(code, 200)
        self.assertIn("postdoc", w["types"])
        _, w = self.j("/api/writing", {"type": "senior", "data": {"confidence": 5, "sections": [{"heading": "Summary", "length": "short"}]}})
        self.assertIn("senior", w["tuned"])
        self.assertEqual(self.j("/api/writing", {"type": "nope", "data": {}})[0], 400)
        self.j("/api/writing", {"type": "senior", "data": None})
        self.assertEqual(self.j("/api/writing/posting", {"key": "missing||x", "type": "phd"})[0], 404)

    def test_reset_api_lists_parts(self):
        code, r = self.j("/api/reset")
        self.assertEqual([p["key"] for p in r["parts"]], ["settings", "keys", "profile", "postings", "documents"])
        self.assertEqual(self.j("/api/reset", {"parts": []})[0], 400)

    def test_listings_api(self):
        with open(self.h.path("all_listings"), "w", encoding="utf-8") as f:
            json.dump({"run_date": "2026-11-02", "listings": [{"title": "Sales", "employer": "X", "url": "https://x.example/1",
                                                                "why": "none of your keywords", "location": "", "source": "s"}]}, f)
        code, r = self.j("/api/listings")
        self.assertEqual((code, len(r["listings"]), r["listings"][0]["why"]), (200, 1, "none of your keywords"))

    def test_network_api(self):
        code, r = self.j("/api/network?days=7")
        self.assertEqual(code, 200)
        self.assertIn("summary", r)

    def test_template_job(self):
        import time
        key = "https://example.com/j/1||FPGA Engineer"
        self.j("/api/decision", {"key": key, "decision": "accepted"})
        code, r = self.j("/api/documents/template", {"key": key})
        self.assertEqual(code, 200)
        for _ in range(100):
            job = self.j("/api/job")[1]["job"]
            if job["done"]:
                break
            time.sleep(0.2)
        self.assertTrue(job["ok"], job["lines"])
        docs = self.j("/api/postings")[1]["postings"][0]["docs"]
        self.assertTrue(any(d["template"] and d["kind"] == "cv" for d in docs))
        code, data = self.call("/file?p=" + docs[0]["rel"] + "&t=testtoken", token=False)
        self.assertEqual(code, 200)
        self.assertTrue(data[:2] == b"PK" or data[:1] == b"#")          # .docx (zip) or Markdown fallback
        self.j("/api/decision", {"key": key, "decision": "undo"})

    def test_ai_answer_parsing(self):
        from engine import ai_docs
        row = {"Title": "FPGA Engineer", "Employer": "Example AB", "Location": "Uppsala", "URL": "https://example.com/j/1"}
        spec = {"banner": {"name": "Jane Example", "title": "FPGA Engineer"}, "sections": [{"heading": "Profile", "paragraphs": ["FPGA work."]}]}
        cl = {"banner": {"name": "Jane Example"}, "paragraphs": ["Dear team, ..."], "recipient": ["Example AB"]}
        bad = ai_docs.apply_tailor_answer(self.h, row, json.dumps({"cv": dict(spec, sections=[{"heading": "P", "paragraphs": ["a \u2014 b"]}]), "cl": cl}))
        self.assertTrue(bad["problems"])                                    # em dash rejected, nothing written
        self.assertEqual(bad["files"], [])
        good = ai_docs.apply_tailor_answer(self.h, row, "Here you go:\n```json\n" + json.dumps({"cv": spec, "cl": cl, "report": "ok"}) + "\n```")
        self.assertEqual(good["problems"], [])
        self.assertTrue(any(f.endswith((".docx", ".md")) for f in good["files"]))
        self.assertIn("Never invent", ai_docs.tailor_prompt(self.h, row))


class TestSharedCases(unittest.TestCase):
    """The same cases run in cloud/test/shared.test.ts against the online Worker."""

    def test_shared(self):
        with open(os.path.join(HERE, "shared", "match_cases.json"), encoding="utf-8") as f:
            c = json.load(f)
        for kw, toks in c["keyword_tokens"]:
            self.assertEqual(match.keyword_tokens(kw), toks, kw)
        for m in c["match_keywords"]:
            got = match.match_keywords(m["title"], m["description"], m["keywords"], scope=m["scope"], exclude_terms=m.get("exclude", []))[1]
            self.assertEqual(got, m["where"], m)
        for m in c["match_location"]:
            self.assertEqual(match.match_location(m["text"], m["locations"]), m["expect"], m)
        for t, want in c["seniority"]:
            self.assertEqual(match.seniority(t), want, t)
        for t, want in c["arrangement"]:
            self.assertEqual(match.arrangement(t), want, t)
        for t, want in c["stated_deadline"]:
            self.assertEqual(sources.stated_deadline(t), want, t)
        for t, want in c["welcomes_junior"]:
            self.assertEqual(match.welcomes_junior(t), want, t)
        for m in c["skills_summary"]:
            self.assertEqual(match.skills_summary(m["text"], m["vocab"]), m["expect"], m)
        for e, want in c["norm_employer"]:
            self.assertEqual(match.norm_employer(e), want, e)


class TestCloudSync(unittest.TestCase):
    """engine/cloud_sync.py against a stand-in for the online Job Agent's sync API."""

    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
        self.h = make_home()
        self.received = {}
        test = self
        export = {"now": "2026-11-02T10:00:00Z", "config": {"search_config": {"keywords": ["FPGA"]}},
                  "postings": [{"key": "https://ex.com/j/1||FPGA Engineer", "url": "https://ex.com/j/1", "title": "FPGA Engineer",
                                "employer": "Online AB", "location": "Lund", "status": "New", "deadline": "2026-12-01",
                                "description": "VHDL radios.", "found": "2026-11-02", "notes": "Source: test"},
                               {"key": "https://ex.com/j/2||RTL Designer", "url": "https://ex.com/j/2", "title": "RTL Designer",
                                "employer": "Online AB", "location": "Lund", "status": "New", "found": "2026-11-02", "notes": ""}],
                  "decisions": {"https://ex.com/j/2||RTL Designer": {"decision": "rejected", "reasons": ["Seniority level mismatch"], "ts": "2026-11-02T09:00:00"}}}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _ok(self):
                return self.headers.get("Authorization") == "Bearer tok-123"

            def do_GET(self):
                code, body = (200, export) if self._ok() else (401, {"error": "no"})
                data = json.dumps(body).encode()
                self.send_response(code); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                test.received[self.path] = json.loads(self.rfile.read(n) or b"{}")
                data = b'{"applied": 1, "ok": true}'
                self.send_response(200 if self._ok() else 401); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        http.DELAY = 0

    def tearDown(self):
        self.srv.shutdown()
        shutil.rmtree(self.h.root, ignore_errors=True)

    def test_pull_and_push(self):
        from engine import cloud_sync, documents
        with self.assertRaises(ValueError):
            cloud_sync.configure(self.h, "http://plain.example", "x")            # https only
        cloud_sync.configure(self.h, self.url, "wrong")
        self.assertFalse(cloud_sync.pull(self.h, log=lambda m: None)["ok"])     # token refused, nothing changes
        self.assertIn("token", cloud_sync.settings(self.h)["error"])
        cloud_sync.configure(self.h, self.url, "tok-123")
        s = cloud_sync.pull(self.h, log=lambda m: None)
        self.assertEqual((s["new"], s["decisions_applied"]), (2, 1))
        rows = {r["Title"]: r for r in tr.read_all_rows(self.h.path("tracker"))}
        self.assertTrue(rows["RTL Designer"]["Status"].startswith("Rejected: Seniority"))
        self.assertEqual(documents.saved_description(self.h, "https://ex.com/j/1"), "VHDL radios.")
        with open(self.h.path("decisions"), encoding="utf-8") as f:
            d = json.load(f)
        d["https://ex.com/j/1||FPGA Engineer"] = {"decision": "accepted", "ts": "2026-11-02T11:00:00"}
        with open(self.h.path("decisions"), "w", encoding="utf-8") as f:
            json.dump(d, f)
        s = cloud_sync.pull(self.h, log=lambda m: None)
        self.assertEqual(s["new"], 0)                                           # nothing duplicated
        sent = self.received["/api/sync/decisions"]["decisions"]
        self.assertIn("https://ex.com/j/1||FPGA Engineer", sent)               # decided here: sent online
        self.assertNotIn("https://ex.com/j/2||RTL Designer", sent)             # decided online: not echoed back
        self.assertNotIn("candidate", json.dumps(self.received))               # nothing about the candidate travels


class TestCloudCopies(unittest.TestCase):
    def test_worker_copies_are_current(self):
        """cloud/src/shared/ must match the originals (run: cd cloud && npm run sync)."""
        root = os.path.dirname(HERE)
        for src, dst in (("engine/web/app.html", "index.html"), ("engine/web/form.html", "candidate_form.html"),
                         ("engine/defaults/search_defaults.json", "search_defaults.json"), ("engine/defaults/skill_vocabulary.json", "skill_vocabulary.json"),
                         ("engine/defaults/job_sites.json", "job_sites.json")):
            with open(os.path.join(root, src), "rb") as a, open(os.path.join(root, "cloud", "src", "shared", dst), "rb") as b:
                self.assertEqual(a.read(), b.read(), f"{dst} is out of date: cd cloud && npm run sync")

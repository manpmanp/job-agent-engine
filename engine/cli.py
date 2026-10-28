# Job-search agent engine
# File:    engine/cli.py
# Purpose: Command-line entry point behind ./run.sh.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""Command-line entry point. Use ./run.sh <command>; see docs/commands.md."""
import argparse
import json
import os
import shutil
import sys
from datetime import date

from . import home as home_mod
from . import tracker as tr
from . import decisions, checkpoint, weekly, documents
from .profile import Intake


def _row_by_key(h, key):
    if "||" not in key:
        raise SystemExit('posting key must be "<URL>||<Title>" (as shown by ./run.sh tailor pending)')
    url, title = key.split("||", 1)
    for r in tr.read_all_rows(h.path("tracker")):
        if r.get("URL") == url and r.get("Title") == title:
            return r
    raise SystemExit(f"posting not found in tracker: {key}")


# --------------------------------------------------------------------- init
def ensure_home(h):
    """Creates every missing folder and file of an agent home (inputs from
    the blank templates, empty state files, output folders and the weekly
    page). Never overwrites anything. Returns the paths it created."""
    created = []
    for key, tmpl in [("search_config", "search_config.json"), ("employers", "employers.json"),
                      ("document_style", "document_style.json"), ("tailoring_rules", "tailoring_rules.md"),
                      ("tailoring_checks", "tailoring_checks.json"), ("characteristics", "characteristics.md")]:
        dest = h.path(key)
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(home_mod.INPUT_TEMPLATES_DIR, tmpl), dest)
            created.append(dest)
    cand = h.path("candidate")
    form = os.path.join(cand, "profile_form.json")
    for d in (cand, h.path("references")):
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(form):
        shutil.copy2(os.path.join(home_mod.INPUT_TEMPLATES_DIR, "candidate", "profile_form.json"), form)
        created.append(form)
    created += ensure_state(h)
    for k in ("cv_out", "cl_out", "jd_out", "specs", "weekly_summary", "new_postings", "intake_cv", "intake_cl"):
        if not os.path.isdir(h.path(k)):
            os.makedirs(h.path(k), exist_ok=True)
            created.append(h.path(k))
    if not os.path.exists(h.path("weekly_html")):
        from . import webpage
        webpage.generate(h)
        created.append(h.path("weekly_html"))
    return created


def cmd_init(h, args):
    created = getattr(args, "_created", None)
    if created is None:
        created = ensure_home(h)
    print(f"agent home: {h.root}")
    for c in created:
        print(f"  created {os.path.relpath(c, h.root)}")
    if not created:
        print("  everything already in place, nothing overwritten")
    print("\nNext: put your keywords and locations in inputs/search_config.json, then ./run.sh status")


def ensure_state(h):
    created = []
    t = h.path("tracker")
    if not os.path.exists(t):
        cfg = h.search_config()
        tr.update(t, [], seniority_cfg=cfg.get("seniority"))
        created.append(t)
    for key, tmpl in [("rejection_log", "rejection_patterns.csv"), ("notes", "Job_Search_Notes.txt"),
                      ("decisions", "decisions_sync.json")]:
        dest = h.path(key)
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(home_mod.STATE_TEMPLATES_DIR, tmpl), dest)
            created.append(dest)
    for k in ("sync_logs", "search_progress"):
        os.makedirs(h.path(k), exist_ok=True)
    return created


# ------------------------------------------------------------------- status
def cmd_status(h, args):
    if not os.path.isdir(h.root):
        print(f"agent home {h.root} does not exist yet: run ./run.sh init")
        return
    caps = h.capabilities()
    print(f"agent home: {h.root}\n")
    groups = [("Minimum service", ["search", "weekly_list", "decision_sync"]),
              ("Online collection", ["online_collection", "named_employer_sweep", "ai_enrichment"]),
              ("Search extras", ["fit_scoring", "calendar_deadlines"]),
              ("Documents", ["tailoring_full", "tailoring_template", "characteristics_tone",
                             "personal_tailoring_rules", "reference_material", "docx_rendering"]),
              ("Candidate data", ["profile_conflicts"])]
    for title, keys in groups:
        print(title)
        for k in keys:
            on, why = caps[k]
            print(f"  [{'on ' if on else 'off'}] {k:<26} {why}")
        print()
    rows = tr.read_all_rows(h.path("tracker"))
    pend = decisions.approved_pending(h)
    print(f"tracker: {len(rows)} posting(s), {len(pend)} accepted and waiting for documents")
    last = checkpoint.latest_run(h)
    if last:
        print(f"last search checkpoint: {last}")


# ---------------------------------------------------------------- the rest
def cmd_plan(h, args):
    print(weekly.search_plan(h))


def cmd_add_postings(h, args):
    ensure_state(h)
    weekly.add_postings(h, args.file)


def cmd_weekly(h, args):
    ensure_state(h)
    from . import webpage
    cfg = h.search_config()
    if not (cfg.get("weekly_list") or {}).get("enabled", True):
        print("weekly list disabled in search_config.weekly_list")
        return
    webpage.generate(h, weekly_note=args.note)
    if (cfg.get("weekly_list") or {}).get("summary_markdown", True):
        weekly.weekly_summary(h, note=args.note)


def cmd_sync(h, args):
    ensure_state(h)
    res = decisions.apply(h, args.file, seniority_cfg=h.search_config().get("seniority"))
    if res.get("applied"):
        from . import webpage
        webpage.generate(h)
    pend = decisions.approved_pending(h)
    if pend:
        print(f"{len(pend)} accepted posting(s) waiting for documents: ./run.sh tailor pending")


def cmd_intake(h, args):
    it = Intake(h)
    a = args.intake_args
    if not a:
        raise SystemExit("usage: intake cv|cl <file> | scan | form <file> | fragment <file> --from <id> | set <field> <value> | conflicts | resolve <n> keep-new|keep-previous | sources | rebuild")
    sub = a[0]
    if sub in ("cv", "cl"):
        it.add_document(sub, a[1])
    elif sub == "form":
        it.add_data("form", a[1])
    elif sub == "fragment":
        parent = a[a.index("--from") + 1] if "--from" in a else None
        it.add_data("fragment", a[1], parent=parent)
    elif sub == "set":
        it.set_field(a[1], a[2])
    elif sub == "conflicts":
        print(it.list_conflicts())
    elif sub == "resolve":
        it.resolve(a[1], a[2])
    elif sub == "sources":
        for e in it.sources():
            print(f"{e['id']:<14} {e['submitted_at']}  {e.get('original') or e.get('data_file')}  {e.get('note') or ''}")
    elif sub == "rebuild":
        it.rebuild()
    elif sub == "scan":
        res = it.scan_intake_folders()
        for i in res["imported"]:
            print(f"imported {i['file']} as {i['id']}" + ("" if i["text_extracted"] else " (no text extracted; the agent reads the original)"))
        for s in res["skipped"]:
            print(f"already imported: {s}")
        for u in res["unsupported"]:
            print(f"not a supported type (.pdf .docx .txt .md): {u}")
        if not any(res.values()):
            print(f"no documents found; copy them into {h.path('intake_cv')} or {h.path('intake_cl')}")
    else:
        raise SystemExit(f"unknown intake command: {sub}")


def cmd_tailor(h, args):
    a = args.tailor_args
    sub = a[0] if a else "pending"
    style = h.document_style()
    caps = h.capabilities()
    if sub == "pending":
        pend = decisions.approved_pending(h)
        mode = "full" if caps["tailoring_full"][0] else "template"
        print(f"tailoring mode: {mode} ({caps['tailoring_full'][1] if mode == 'full' else 'no candidate material yet'})")
        for r in pend:
            print(f"- {r.get('Employer')}: {r.get('Title')}\n    key: {r.get('URL')}||{r.get('Title')}\n    files: {documents.filenames_for(r)['base']}")
        if not pend:
            print("nothing waiting")
        return
    if sub == "template":
        rows = decisions.approved_pending(h) if "--all-pending" in a else [_row_by_key(h, a[1])]
        for r in rows:
            names = documents.filenames_for(r)
            cfg = h.search_config()
            cv, cl = documents.template_specs(r, h.profile(), style,
                                              description=documents.saved_description(h, r.get("URL")),
                                              vocabulary=list(cfg.get("skill_terms") or []) + list(cfg.get("keywords") or []))
            p1 = documents.render(cv, os.path.join(h.path("cv_out"), "TEMPLATE_" + names["cv"]), style=style)
            p2 = documents.render(cl, os.path.join(h.path("cl_out"), "TEMPLATE_" + names["cl"]), style=style)
            print(f"template documents for {r.get('Employer')} / {r.get('Title')}:\n  {p1}\n  {p2}")
        return
    if sub == "check":
        with open(a[1], "r", encoding="utf-8") as f:
            spec = json.load(f)
        probs = documents.check_spec(spec, h.tailoring_checks(), style)
        print("passed" if not probs else "problems:\n" + "\n".join(f"  - {p}" for p in probs))
        if probs:
            sys.exit(1)
        return
    if sub == "render":
        # tailor render <spec.json> --posting "<URL>||<Title>"   (kind taken from spec.type)
        with open(a[1], "r", encoding="utf-8") as f:
            spec = json.load(f)
        probs = documents.check_spec(spec, h.tailoring_checks(), style)
        if probs and "--force" not in a:
            print("not rendered, fix these first (or pass --force):\n" + "\n".join(f"  - {p}" for p in probs))
            sys.exit(1)
        r = _row_by_key(h, a[a.index("--posting") + 1])
        names = documents.filenames_for(r)
        kind = spec.get("type", "cv")
        out_dir = h.path("cv_out" if kind == "cv" else "cl_out")
        target = os.path.join(out_dir, names[kind])
        if os.path.exists(target) and "--overwrite" not in a:
            print(f"{target} already exists (pass --overwrite to replace)")
            sys.exit(1)
        os.makedirs(h.path("specs"), exist_ok=True)
        with open(os.path.join(h.path("specs"), f"{kind.upper()}_{names['base']}.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        print(f"wrote {documents.render(spec, target, style=style)}")
        return
    if sub == "jd":
        r = _row_by_key(h, a[1])
        text = None
        if "--text" in a:
            with open(a[a.index("--text") + 1], "r", encoding="utf-8") as f:
                text = f.read()
        names = documents.filenames_for(r)
        print(f"wrote {documents.jd_snapshot(r, os.path.join(h.path('jd_out'), names['jd']), text)}")
        return
    if sub == "done":
        r = dict(_row_by_key(h, a[1]))
        names = documents.filenames_for(r)
        r["CV/Cover Letter Drafted (Y/N)"] = "Y"
        r["Notes"] = f'{r.get("Notes") or ""} | Documents: {names["cv"]}, {names["cl"]}, {names["jd"]}'.strip(" |")
        tr.update(h.path("tracker"), [r], seniority_cfg=h.search_config().get("seniority"))
        return
    raise SystemExit(f"unknown tailor command: {sub}")


def cmd_checkpoint(h, args):
    a = args.cp_args
    if not a:
        raise SystemExit("usage: checkpoint phase <date> <phase> <status> [note] | employer <date> <name> <found> [note] | report [date]")
    if a[0] == "phase":
        checkpoint.mark_phase(h, a[1], a[2], a[3], a[4] if len(a) > 4 else "")
    elif a[0] == "employer":
        checkpoint.mark_checked(h, a[1], a[2], a[3] if len(a) > 3 else 0, a[4] if len(a) > 4 else "")
    elif a[0] == "report":
        print(checkpoint.report(h, a[1] if len(a) > 1 else (checkpoint.latest_run(h) or date.today().isoformat())))


def cmd_note(h, args):
    weekly.append_note(h, args.text)


def cmd_collect(h, args):
    ensure_state(h)
    from .collect import collect
    collect(h, only=args.only)


def cmd_fetch(h, args):
    ensure_state(h)
    from .collect import fetch_url
    fetch_url(h, args.url, add=args.add, render=not args.no_render, employer=args.employer, title=args.title)


def cmd_verify(h, args):
    ensure_state(h)
    from .collect.verify import verify
    verify(h)


def cmd_enrich(h, args):
    from .enrich import enrich
    enrich(h)


def cmd_run(h, args):
    from .runs import run
    run(h, args.mode)


def cmd_schedule(h, args):
    from .runs import schedule_text
    print(schedule_text(h))


def cmd_open(h, args):
    """Opens the weekly page in the default browser, from the local file."""
    import webbrowser
    path = h.path("weekly_html")
    if not os.path.exists(path):
        cmd_weekly(h, argparse.Namespace(note=None))
    url = "file://" + os.path.abspath(path)
    if not webbrowser.open(url):
        print(f"open this in your browser: {url}")
    else:
        print(f"opened {path}")


def cmd_form(h, args):
    from .formserver import serve
    serve(h, port=args.port, open_browser=not args.no_browser)


def cmd_demo(h, args):
    from . import demo
    demo.build(args.home)


def main(argv=None):
    p = argparse.ArgumentParser(prog="run.sh", description="Job-search agent engine")
    p.add_argument("--home", help="agent home folder (default: $JOB_AGENT_HOME or ./my_agent)")
    sp = p.add_subparsers(dest="cmd")
    sp.add_parser("init")
    sp.add_parser("status")
    sp.add_parser("plan")
    x = sp.add_parser("add-postings"); x.add_argument("file")
    x = sp.add_parser("weekly"); x.add_argument("note", nargs="?")
    x = sp.add_parser("sync"); x.add_argument("file", nargs="?")
    x = sp.add_parser("intake"); x.add_argument("intake_args", nargs=argparse.REMAINDER)
    x = sp.add_parser("tailor"); x.add_argument("tailor_args", nargs=argparse.REMAINDER)
    x = sp.add_parser("checkpoint"); x.add_argument("cp_args", nargs=argparse.REMAINDER)
    x = sp.add_parser("note"); x.add_argument("text")
    x = sp.add_parser("collect"); x.add_argument("--only", choices=["jobtech", "employers", "aggregators", "jsearch", "adzuna", "hn"])
    x = sp.add_parser("fetch"); x.add_argument("url"); x.add_argument("--add", action="store_true")
    x.add_argument("--no-render", action="store_true"); x.add_argument("--employer"); x.add_argument("--title")
    sp.add_parser("verify")
    sp.add_parser("enrich")
    x = sp.add_parser("run"); x.add_argument("mode", nargs="?", default="auto", choices=["weekly", "daily", "auto"])
    sp.add_parser("schedule")
    sp.add_parser("open")
    x = sp.add_parser("form"); x.add_argument("--port", type=int, default=8765); x.add_argument("--no-browser", action="store_true")
    sp.add_parser("demo")
    args = p.parse_args(argv)
    if not args.cmd:
        # Plain ./run.sh: set up the agent home if needed and do today's run.
        base = list(argv) if argv is not None else sys.argv[1:]
        args = p.parse_args(base + ["run", "auto"])
    if args.cmd == "demo":
        return cmd_demo(None, args)
    h = home_mod.resolve_home(args.home)
    created = ensure_home(h)
    if args.cmd == "init":
        args._created = created
    elif created:
        fresh = h.path("search_config") in created
        print(f"agent home {'created' if fresh else 'completed'} at {h.root}: {len(created)} missing file(s)/folder(s) created"
              + ("; add your keywords and locations to inputs/search_config.json" if not h.capabilities()["search"][0] else ""))
    {"init": cmd_init, "status": cmd_status, "plan": cmd_plan, "add-postings": cmd_add_postings,
     "weekly": cmd_weekly, "sync": cmd_sync, "intake": cmd_intake, "tailor": cmd_tailor,
     "checkpoint": cmd_checkpoint, "note": cmd_note, "collect": cmd_collect, "fetch": cmd_fetch, "verify": cmd_verify,
     "enrich": cmd_enrich, "run": cmd_run, "schedule": cmd_schedule, "open": cmd_open, "form": cmd_form}[args.cmd](h, args)


if __name__ == "__main__":
    main()

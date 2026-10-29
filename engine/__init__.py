# Job-search agent engine
# File:    engine/__init__.py
# Purpose: Package marker and version of the engine.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""Job-search agent engine: generic, candidate-independent logic.

Everything personal is read from an *agent home* folder supplied at run
time (see engine/home.py and docs/inputs.md). Nothing in this package
contains or assumes data about a specific candidate.
"""
__version__ = "0.4.7"
__author__ = "manpmanp"
__date__ = "2026-10-28"


def _hide_console_windows():
    """On Windows, every console program the app starts (schtasks for the
    daily run, headless Chrome, the Playwright driver, pdftotext, its own
    background jobs) would open a black console window for a moment, because
    the app itself has no console. This makes all of them start hidden,
    unless a caller asks for specific creation flags."""
    import os
    import subprocess
    if os.name != "nt" or getattr(subprocess.Popen, "_job_agent_hidden", False):
        return
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = no_window
        return original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__
    subprocess.Popen._job_agent_hidden = True


_hide_console_windows()

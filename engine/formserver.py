# Job-search agent engine
# File:    engine/formserver.py
# Purpose: Kept for older callers: the input forms are now part of the local app (engine/app.py).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""'./run.sh --setup' and './run.sh form' open the app on its Setup page."""
from .app import serve as _serve


def serve(home, port=8765, open_browser=True):
    return _serve(home, port=port, open_browser=open_browser, path="/#setup")

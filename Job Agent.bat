@echo off
rem Job-search agent engine
rem File:    Job Agent.bat
rem Purpose: Windows double-click launcher: opens the Job Agent app.
rem Author:  manpmanp <manp.node@gmail.com>
rem Generated with Claude (Anthropic), under the author's direction and review.
rem License: MIT (see LICENSE)
rem Version: 0.4.0
rem Date:    2026-10-28
cd /d "%~dp0"
where py >nul 2>nul && (py -3 start.py %* & goto :end)
where python >nul 2>nul && (python start.py %* & goto :end)
echo Job Agent needs Python 3. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then double-click this file again.
pause
:end

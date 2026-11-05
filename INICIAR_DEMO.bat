@echo off
cd /d "%~dp0projects\it-05-ticket-triage"
py -m ticket_triage.web --open
pause

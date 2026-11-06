@echo off
setlocal
cd /d "%~dp0projects\it-05-ticket-triage" || goto nofolder
where py >nul 2>&1 && (py -m ticket_triage.web --open & goto fin)
where python >nul 2>&1 && (python -m ticket_triage.web --open & goto fin)
echo No se encontro Python en este equipo.
echo Instalalo desde https://www.python.org/downloads/ y marca "Add python.exe to PATH".
goto fin
:nofolder
echo No se encontro la carpeta projects\it-05-ticket-triage junto a este archivo.
:fin
pause

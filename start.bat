@echo off
setlocal

:: ── Vérifie Docker ────────────────────────────────────────────────────────────
where docker >nul 2>&1
if errorlevel 1 (
    echo Docker non trouve.
    echo Telechargement de Docker Desktop...
    powershell -Command "Start-Process 'https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe' -Wait" 2>nul
    echo Installe Docker Desktop, redémarre ton PC puis relance ce fichier.
    pause
    exit /b 1
)

:: ── Vérifie que Docker tourne ────────────────────────────────────────────────
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker n'est pas demarre. Lancement de Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo Attente du démarrage de Docker...
    timeout /t 15 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 (
        echo Docker n'a pas demarre. Lance Docker Desktop manuellement puis reessaie.
        pause
        exit /b 1
    )
)

:: ── Lance l'application ───────────────────────────────────────────────────────
cd /d "%~dp0"

docker image inspect mtg_biblio-app >nul 2>&1
if errorlevel 1 (
    echo Premiere execution - construction de l'image quelques minutes...
    docker compose build
)

docker compose up -d
echo.
echo MTG Collection lance sur http://localhost:8090
pause

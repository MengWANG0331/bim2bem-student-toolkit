@echo off
setlocal

set "IMAGE=ghcr.io/mengwang0331/bim2bem-cbip:latest"

where docker >nul 2>&1
if errorlevel 1 (
    echo Docker was not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and try again.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Drag an .ifc file onto this script, or run: run.bat path\to\model.ifc
    pause
    exit /b 1
)

if not exist "%~1" (
    echo File not found: %~1
    pause
    exit /b 1
)

set "IFC_DIR=%~dp1"
if "%IFC_DIR:~-1%"=="\" set "IFC_DIR=%IFC_DIR:~0,-1%"
set "IFC_NAME=%~nx1"
set "OUT_DIR=%~dp0cases_out"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

echo == Pulling pipeline image (skipped if already up to date) ==
docker pull %IMAGE%
if errorlevel 1 (
    echo Docker pull failed - is Docker Desktop running?
    pause
    exit /b 1
)

echo == Running pipeline on %IFC_NAME% ==
docker run --rm -v "%IFC_DIR%:/input:ro" -v "%OUT_DIR%:/output" %IMAGE% "/input/%IFC_NAME%"
if errorlevel 1 (
    echo Pipeline failed - see the log above.
    pause
    exit /b 1
)

echo == Done. Results in: %OUT_DIR% ==
pause

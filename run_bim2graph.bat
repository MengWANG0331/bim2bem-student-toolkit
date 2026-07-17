@echo off
setlocal

set "HERE=%~dp0"
set "VENV=%HERE%bim2graph\.venv"

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/ and try again.
    echo During install, make sure to check "Add python.exe to PATH".
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Drag an .ifc file onto this script, or run: run_bim2graph.bat path\to\model.ifc
    pause
    exit /b 1
)

if not exist "%~1" (
    echo File not found: %~1
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    echo == First run: setting up a local Python environment, this can take a few minutes ==
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
    "%VENV%\Scripts\python.exe" -m pip install -r "%HERE%bim2graph\requirements.txt"
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

set "OUT_DIR=%HERE%cases_out_bim2graph"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

echo == Running BIM2Graph on %~nx1 ==
"%VENV%\Scripts\python.exe" "%HERE%bim2graph\run_pipeline.py" "%~1" -o "%OUT_DIR%"
if errorlevel 1 (
    echo Pipeline failed - see the log above.
    pause
    exit /b 1
)

echo == Done. Results in: %OUT_DIR% ==
pause

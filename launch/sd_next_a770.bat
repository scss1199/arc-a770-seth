@echo off
REM ============================================================================
REM  SD.Next launcher for Intel Arc A770 on Windows 11
REM  See ../docs/02-env-vars.md for the rationale behind every setting below.
REM
REM  Edit the three path variables in the USER CONFIGURATION block.
REM  CPU affinity default (FFFF) assumes 14900K/13900K (8 P-cores x 2 HT = 16).
REM ============================================================================

REM --- USER CONFIGURATION --- edit these four lines to match your install ----
set "SDNEXT_ROOT=C:\sd_next_a770"
set "ONEAPI_SETVARS=C:\Program Files (x86)\Intel\oneAPI\setvars.bat"
set "EDGE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set "CPU_AFFINITY=FFFF"
REM     CPU_AFFINITY hex mask of P-core logical threads:
REM       14900K / 13900K / 13700K : FFFF   (8 P-cores x 2 HT = 16 threads 0-15)
REM       14700K / 13700K          : FF     (8 P-cores x 1 HT = 8 threads)
REM       All cores (no affinity)   : FFFFFFFF
REM ----------------------------------------------------------------------------

chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal EnableDelayedExpansion

REM --- Date stamp for banner ---
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set "dt=%%a"
set "YYYY=!dt:~0,4!"
set "MM=!dt:~4,2!"
set "DD=!dt:~6,2!"
set "START_DATE=!YYYY!/!MM!/!DD!"

cd /d "%SDNEXT_ROOT%"

REM --- Optional deep cache cleanup (set CLEANING_MODE=1 to enable on this run) ---
REM     All Intel caches are force-disabled via env vars below, so physical cache
REM     dirs should stay empty. This is a belt-and-suspenders recovery for the case
REM     where a crashed run left stale files behind.
set CLEANING_MODE=0
if !CLEANING_MODE!==1 (
    if exist "%LOCALAPPDATA%\Intel\ComputeCache" rd /s /q "%LOCALAPPDATA%\Intel\ComputeCache"
    if exist "C:\ProgramData\Intel\ShaderCache" rd /s /q "C:\ProgramData\Intel\ShaderCache"
    echo [clean] Intel compute and shader caches cleared.
)

REM --- Safe-backup SD.Next config before launch (protects against corruption) ---
for %%F in (ui-config.json config.json) do (
    if exist "%SDNEXT_ROOT%\%%F" for %%I in ("%SDNEXT_ROOT%\%%F") do (
        if %%~zI GTR 1024 copy /y "%SDNEXT_ROOT%\%%F" "%SDNEXT_ROOT%\%%~nF_backup.json" >nul
    )
)

REM --- Load oneAPI environment + venv ---
call "%ONEAPI_SETVARS%" >nul 2>&1
call .\venv\Scripts\activate
set "PATH=%SDNEXT_ROOT%\venv\Lib\site-packages\torch\lib;%SDNEXT_ROOT%\venv\Lib\site-packages\intel_extension_for_pytorch\lib;%PATH%"

REM ============================================================================
REM  Intel GPU runtime configuration
REM  Each flag has a documented reason in docs/02-env-vars.md. Do not blindly
REM  enable caches — they have been deliberately disabled after repeated
REM  long-run corruption failures.
REM ============================================================================

REM --- Device selection: first Level Zero device ---
set ONEAPI_DEVICE_SELECTOR=level_zero:0
set ZE_AFFINITY_MASK=0

REM --- All Intel GPU caches OFF (long-run stability choice) ---
set IGC_EnableShaderCache=0
set IPEX_WEIGHT_CACHE=0
set IPEX_XPU_ONEDNN_LAYOUT=OFF
set SYCL_CACHE_PERSISTENT=0

REM --- Level Zero (v1 adapter) runtime tuning ---
set SYCL_PI_LEVEL_ZERO_BATCH_SIZE=32
set SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0
set SYCL_PI_LEVEL_ZERO_DEVICE_SCOPE_EVENTS=0
set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1
set SYCL_PI_LEVEL_ZERO_REUSE_DISCARDED_EVENTS=1

REM --- PyTorch XPU allocator tuning ---
set PYTORCH_XPU_ALLOC_CONF=max_split_size_mb:512

REM --- SD.Next command line args ---
set COMMANDLINE_ARGS=--use-ipex --backend diffusers --skip-env --skip-requirements

REM --- Delayed auto-open of the SD.Next UI in Edge (20s after launch) ---
if exist "%EDGE_PATH%" (
    start /b "" cmd /c "timeout /t 20 >nul && start "" "%EDGE_PATH%" http://127.0.0.1:7860/"
)

echo ====================================================================================================================================================================
echo                                                     - Intel Arc A770 - SD.Next tuned launch - !START_DATE! -
echo ====================================================================================================================================================================

REM --- Launch Python bound to P-cores at HIGH priority ---
REM  /AFFINITY pins Python to performance cores, avoiding Windows scheduling it
REM  on efficiency cores during CPU-bound stages (YOLO detection, prompt parse).
start "SD.Next" /B /WAIT /HIGH /AFFINITY %CPU_AFFINITY% python launch.py

exit /b

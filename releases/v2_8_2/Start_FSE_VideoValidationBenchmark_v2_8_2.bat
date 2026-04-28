@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 video_validation_benchmark_v2_8_2.py
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python video_validation_benchmark_v2_8_2.py
    goto :end
)

echo Python 3 is not installed or not available in PATH.
pause

:end
endlocal

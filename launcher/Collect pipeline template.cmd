@echo off
"%~dp0preparation\GT5P-Prepare.exe" --collect-contribution --install "%~dp0."
set "tourline_collect_exit=%errorlevel%"
if not "%tourline_collect_exit%"=="0" echo Collection did not finish. Your existing caches and private recording were kept.
pause
exit /b %tourline_collect_exit%

@echo off
"%~dp0preparation\GT5P-Prepare.exe" --collect-contribution --install "%~dp0."
set "tourline_collect_exit=%errorlevel%"
if not "%tourline_collect_exit%"=="0" echo Collection or verification did not finish. Recording and caches were kept. Use Resume pipeline verification.cmd after closing the game.
pause
exit /b %tourline_collect_exit%

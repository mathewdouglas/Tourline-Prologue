@echo off
"%~dp0preparation\GT5P-Prepare.exe" --verify-contribution --install "%~dp0."
set "tourline_verify_exit=%errorlevel%"
if not "%tourline_verify_exit%"=="0" echo Verification did not finish. Your recording and completed work were kept.
pause
exit /b %tourline_verify_exit%

@echo off
setlocal
if "%~1"=="" (
  echo usage: build_editor.bat path\to\Project.uproject [extra Build.bat arguments]
  exit /b 1
)
if "%UE_ROOT%"=="" (
  echo set UE_ROOT to the engine folder, for example D:\EpicGames\UE_5.5
  exit /b 1
)
set "PROJECT=%~f1"
for %%F in ("%PROJECT%") do set "NAME=%%~nF"
call "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" %NAME%Editor Win64 Development "-Project=%PROJECT%" -WaitMutex %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

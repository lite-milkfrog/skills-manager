@echo off
setlocal
for %%I in ("%~dp0\..\..") do set "SM_ROOT=%%~fI"
set "PYTHONPATH=%SM_ROOT%\src"
if exist "%SM_ROOT%\.venv\Scripts\python.exe" (
  set "SM_PYTHON=%SM_ROOT%\.venv\Scripts\python.exe"
) else (
  set "SM_PYTHON=py"
)
cd /d "%SM_ROOT%"
if /I "%SM_PYTHON%"=="py" (
  py -3 -m skill_control_plane.web_manager --host 127.0.0.1 --port 8955
) else (
  "%SM_PYTHON%" -m skill_control_plane.web_manager --host 127.0.0.1 --port 8955
)

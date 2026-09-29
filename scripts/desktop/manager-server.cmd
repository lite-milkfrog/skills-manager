@echo off
setlocal
for %%I in ("%~dp0\..\..") do set "SM_ROOT=%%~fI"
if exist "%SM_ROOT%\.venv\Scripts\python.exe" (
  set "SM_PYTHON=%SM_ROOT%\.venv\Scripts\python.exe"
) else (
  set "SM_PYTHON=py"
)
cd /d "%SM_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:SKILLS_MANAGER_USER_HOME=[Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile); $env:PYTHONPATH=$env:SM_ROOT + '\src'; if ($env:SM_PYTHON -eq 'py') { & py -3 -m skill_control_plane.web_manager --host 127.0.0.1 --port 8955 } else { & $env:SM_PYTHON -m skill_control_plane.web_manager --host 127.0.0.1 --port 8955 }; exit $LASTEXITCODE"

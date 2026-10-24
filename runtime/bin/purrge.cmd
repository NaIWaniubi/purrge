@echo off
rem purrge 入口（Windows）：找到 Python 并转给 dg.py
set "PY=python"
where python >nul 2>nul || set "PY=py"
"%PY%" "%~dp0..\lib\dg.py" %* & exit /b

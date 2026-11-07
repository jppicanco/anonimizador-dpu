@echo off
REM Executa a suite automatizada de testes.
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python -m pytest -rs
pause

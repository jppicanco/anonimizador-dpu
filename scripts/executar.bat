@echo off
REM Abre o Anonimizador DPU.
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python -m anonimizador_dpu.app.main
if errorlevel 1 (
    echo.
    echo O aplicativo terminou com erro. Execute scripts\verificar_ambiente.py.
    pause
)

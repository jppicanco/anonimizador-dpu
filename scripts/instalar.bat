@echo off
REM Instalacao das dependencias do Anonimizador DPU (Windows).
REM NAO instala o Tesseract OCR: veja o README.md, secao 3.1.
setlocal
cd /d "%~dp0.."
echo ============================================================
echo  Anonimizador DPU - instalacao das dependencias
echo ============================================================
if not exist ".venv" (
    echo Criando ambiente virtual .venv ...
    python -m venv .venv || goto :erro
)
call .venv\Scripts\activate.bat || goto :erro
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt || goto :erro
echo.
echo Verificando o ambiente...
python scripts\verificar_ambiente.py
echo.
echo Instalacao concluida. Use scripts\executar.bat para abrir o aplicativo.
pause
exit /b 0
:erro
echo.
echo FALHA na instalacao. Verifique as mensagens acima.
pause
exit /b 1

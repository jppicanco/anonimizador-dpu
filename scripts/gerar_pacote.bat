@echo off
REM Gera o pacote de distribuicao completo (executavel + Tesseract + docs).
REM Execute a partir da raiz do projeto.

setlocal
cd /d "%~dp0\.."

echo.
echo === Encerrando instancias abertas do aplicativo ===
REM Com o aplicativo aberto, o Windows trava os arquivos e o PyInstaller
REM aborta com acesso negado, deixando no lugar o executavel anterior.
taskkill /IM AnonimizadorDPU.exe /F >nul 2>&1

echo.
echo === Gerando o executavel ===
python -m PyInstaller scripts\anonimizador_dpu.spec --noconfirm
if errorlevel 1 (
    echo.
    echo FALHA ao gerar o executavel. O pacote NAO foi montado.
    exit /b 1
)

echo.
echo === Montando o pacote ===
python scripts\montar_pacote.py
if errorlevel 1 (
    echo.
    echo FALHA ao montar o pacote.
    exit /b 1
)

echo.
echo Pronto: dist\AnonimizadorDPU.zip
endlocal

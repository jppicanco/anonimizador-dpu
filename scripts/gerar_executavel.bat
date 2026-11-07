@echo off
REM Gera o executavel Windows em dist\AnonimizadorDPU\.
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python -m pip install pyinstaller || goto :erro
python -m PyInstaller scripts\anonimizador_dpu.spec --noconfirm || goto :erro
echo.
echo Executavel gerado em dist\AnonimizadorDPU\AnonimizadorDPU.exe
echo Teste o pacote em uma maquina SEM conexao com a internet antes de distribuir.
pause
exit /b 0
:erro
echo FALHA ao gerar o executavel.
pause
exit /b 1

@echo off
cd /d C:\GIT\invest
echo.
echo ========================================
echo 🚀 Iniciando Streamlit...
echo ========================================
echo.
echo ⏳ Aguarde... o aplicativo abrirá no navegador em alguns segundos...
echo.
echo 📱 Se o navegador não abrir automaticamente, acesse:
echo    http://localhost:8501
echo.
echo ❌ Para parar o servidor, pressione Ctrl+C
echo.
C:/GIT/invest/.venv/Scripts/python.exe -m streamlit run APP.py
pause


cd C:\GIT\invest
Write-Host "========================================" -ForegroundColor Green
Write-Host "🚀 Iniciando Streamlit..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "⏳ Aguarde... o aplicativo abrirá no navegador em alguns segundos..." -ForegroundColor Yellow
Write-Host ""
Write-Host "📱 Se o navegador não abrir automaticamente, acesse:" -ForegroundColor Cyan
Write-Host "   http://localhost:8501" -ForegroundColor Cyan
Write-Host ""
Write-Host "❌ Para parar o servidor, pressione Ctrl+C" -ForegroundColor Yellow
Write-Host ""

C:/GIT/invest/.venv/Scripts/python.exe -m streamlit run APP.py


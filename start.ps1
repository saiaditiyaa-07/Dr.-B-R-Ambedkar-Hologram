# Avatar Chatbot - One-click startup script
Write-Host "🤖 Starting Avatar Chatbot..." -ForegroundColor Cyan

# Kill anything on port 8000 or 8001
$ports = @(8000, 8001)
foreach ($port in $ports) {
    $stalePid = netstat -ano | Select-String "127.0.0.1:$port\s+.*LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] }
    if ($stalePid) {
        Write-Host "⚡ Killing stale process on port $port (PID: $stalePid)..." -ForegroundColor Yellow
        taskkill /PID $stalePid /F | Out-Null
        Start-Sleep -Seconds 1
    }
}

# Start backend
Write-Host "🐍 Starting Python backend on http://127.0.0.1:8001 ..." -ForegroundColor Green
$pyExec = if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") { "$PSScriptRoot\.venv\Scripts\python.exe" } else { "python" }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\server'; & '$pyExec' -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload"

Start-Sleep -Seconds 2

# Start frontend
Write-Host "⚛️  Starting Vite frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\client'; npm run dev"

Write-Host ""
Write-Host "✅ Both servers starting! Open http://localhost:5173 (or 5174) in your browser." -ForegroundColor Cyan

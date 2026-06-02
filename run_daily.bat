@echo off
wsl pgrep -x ollama >nul
if %ERRORLEVEL%==1 (
    echo [System] WSL Ollama is now running...
    wsl bash -c "ollama serve > /dev/null 2>&1 &"
    timeout /t 8 /nobreak >nul
) else (
    echo [System] WSL Ollama is already running...
)
wsl python3 /mnt/c/Users/Public/jameshin.github.io/daily_batch.py
pause

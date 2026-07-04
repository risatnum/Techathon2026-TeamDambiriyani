@echo off
setlocal enabledelayedexpansion

:: ==========================================
:: Configuration
:: ==========================================
set REPO_URL=https://github.com/risatnum/Techathon2026-TeamDambiriyani.git
set PROJECT_DIR=Techathon2026-TeamDambiriyani
set ENV_GIST_URL=https://gist.githubusercontent.com/risatnum/0cfb7563128a8f9bfc4f4b3781f02197/raw/6c197a10ef14e69d768c747a9a016148340a8563/.env
set DISCORD_INVITE_URL=https://discord.com/oauth2/authorize?client_id=1522626157948964874&permissions=8&scope=bot%20applications.commands

echo.
echo  =====================================================
echo       Office Monitoring System - One Click Setup
echo  =====================================================
echo.

:: -----------------------------------------------
:: 1. Check if the project is already downloaded
:: -----------------------------------------------
if not exist "%PROJECT_DIR%" (
    echo  [1/6] Project not found. Downloading from GitHub...
    echo.
    git clone %REPO_URL% %PROJECT_DIR%
    if errorlevel 1 (
        echo.
        echo  [ERROR] Failed to clone repository.
        echo  Make sure Git is installed: https://git-scm.com/
        pause
        exit /b 1
    )
    echo.
    echo  Download complete!
) else (
    echo  [1/6] Project already downloaded. Skipping.
)

cd "%PROJECT_DIR%"

:: -----------------------------------------------
:: 2. Download .env file for the Discord bot
:: -----------------------------------------------
echo.
if not exist "bot\.env" (
    echo  [2/6] Downloading environment config for Discord Bot...
    powershell -Command "Invoke-WebRequest -Uri '%ENV_GIST_URL%' -OutFile 'bot\.env'"
    if errorlevel 1 (
        echo  [WARNING] Could not download .env file. The Discord Bot may not work.
        echo  You can manually place a .env file in the bot\ folder later.
    ) else (
        echo  Environment config downloaded and placed in bot\ folder.
    )
) else (
    echo  [2/6] Bot environment config already exists. Skipping.
)

:: -----------------------------------------------
:: 3. Setup Backend (FastAPI)
:: -----------------------------------------------
echo.
echo  [3/6] Setting up Backend...
if not exist "backend\venv" (
    echo  Creating virtual environment for backend...
    python -m venv backend\venv
    echo  Installing backend dependencies...
    backend\venv\Scripts\pip install -r backend\requirements.txt
) else (
    echo  Backend dependencies already installed. Skipping.
)
echo  Starting Backend...
start "Backend" cmd /c "title Backend & call backend\venv\Scripts\activate & cd backend & uvicorn app.main:socket_app --host 0.0.0.0 --port 8000"

:: -----------------------------------------------
:: 4. Setup Simulator
:: -----------------------------------------------
echo.
echo  [4/6] Setting up Simulator...
if not exist "simulator\venv" (
    echo  Creating virtual environment for simulator...
    python -m venv simulator\venv
    echo  Installing simulator dependencies...
    simulator\venv\Scripts\pip install -r simulator\requirements.txt
) else (
    echo  Simulator dependencies already installed. Skipping.
)
echo  Starting Simulator...
start "Simulator" cmd /c "title Simulator & call simulator\venv\Scripts\activate & cd simulator & python main.py"

:: -----------------------------------------------
:: 5. Setup Frontend (React + Vite)
:: -----------------------------------------------
echo.
echo  [5/6] Setting up Frontend Dashboard...
if not exist "frontend\node_modules" (
    echo  Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
) else (
    echo  Frontend dependencies already installed. Skipping.
)
echo  Starting Frontend...
start "Frontend" cmd /c "title Frontend & cd frontend & npm run dev"

:: -----------------------------------------------
:: 6. Setup Discord Bot + Invitation Prompt
:: -----------------------------------------------
echo.
echo  [6/6] Setting up Discord Bot...
if not exist "bot\node_modules" (
    echo  Installing bot dependencies...
    cd bot
    call npm install
    cd ..
) else (
    echo  Bot dependencies already installed. Skipping.
)
echo  Starting Discord Bot...
start "Discord Bot" cmd /k "title Discord Bot & cd bot & npm start"

:: -----------------------------------------------
:: 7. Discord Bot Invitation
:: -----------------------------------------------
echo.
echo  =====================================================
echo   Would you like to invite the Discord Bot to your
echo   server to receive live alerts and updates?
echo  =====================================================
echo.
set /p INVITE_CHOICE="  Type Y to invite, or N to skip: "

if /i "!INVITE_CHOICE!"=="y" (
    echo.
    echo  Opening Discord Bot invite link in your browser...
    start %DISCORD_INVITE_URL%
) else (
    echo.
    echo  Got it! Continuing without Discord.
    echo  You won't receive Discord alerts or updates.
)

:: -----------------------------------------------
:: 8. Open the Dashboard
:: -----------------------------------------------
echo.
echo  Waiting 5 seconds for services to start up...
timeout /t 5 /nobreak >nul
echo  Opening dashboard in your default browser...
start http://localhost:5173

echo.
echo  =====================================================
echo   All services are running! You can close this
echo   window, but keep the other terminal windows open.
echo  =====================================================
echo.
pause

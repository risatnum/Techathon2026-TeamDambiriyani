@echo off
setlocal

:: ==========================================
:: Setup your GitHub repository URL here
:: ==========================================
set REPO_URL=https://github.com/yourusername/dumbiriyani.git
set PROJECT_DIR=dumbiriyani

echo ==========================================
echo Office Monitoring System - Auto Setup & Run
echo ==========================================
echo.

:: 1. Check if the project is downloaded, if not clone it
if not exist "%PROJECT_DIR%" (
    echo [1/5] Project not found locally. Downloading from GitHub...
    git clone %REPO_URL% %PROJECT_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to clone repository. Please check if git is installed and the URL is correct.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Project folder "%PROJECT_DIR%" already exists. Skipping download.
)

cd "%PROJECT_DIR%"

:: 2. Setup and run Backend (FastAPI)
echo.
echo [2/5] Setting up Backend...
if not exist "backend\venv" (
    echo Creating virtual environment for backend...
    python -m venv backend\venv
    echo Installing backend dependencies...
    backend\venv\Scripts\pip install -r backend\requirements.txt
) else (
    echo Backend dependencies already installed. Skipping.
)
echo Starting Backend...
start "Backend" cmd /c "title Backend & call backend\venv\Scripts\activate & cd backend & uvicorn app.main:socket_app --host 0.0.0.0 --port 8000"

:: 3. Setup and run Simulator
echo.
echo [3/5] Setting up Simulator...
if not exist "simulator\venv" (
    echo Creating virtual environment for simulator...
    python -m venv simulator\venv
    echo Installing simulator dependencies...
    simulator\venv\Scripts\pip install -r simulator\requirements.txt
) else (
    echo Simulator dependencies already installed. Skipping.
)
echo Starting Simulator...
start "Simulator" cmd /c "title Simulator & call simulator\venv\Scripts\activate & cd simulator & python main.py"

:: 4. Setup and run Frontend (React)
echo.
echo [4/5] Setting up Frontend...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
) else (
    echo Frontend dependencies already installed. Skipping.
)
echo Starting Frontend...
start "Frontend" cmd /c "title Frontend & cd frontend & npm run dev"

:: 5. Setup and run Discord Bot
echo.
echo [5/5] Setting up Discord Bot...
if not exist "bot\node_modules" (
    echo Installing bot dependencies...
    cd bot
    call npm install
    cd ..
) else (
    echo Bot dependencies already installed. Skipping.
)
echo Starting Discord Bot...
start "Discord Bot" cmd /c "title Discord Bot & cd bot & npm start"

:: 6. Open the browser
echo.
echo Waiting 5 seconds for services to start up...
timeout /t 5 /nobreak >nul
echo Opening dashboard in your default browser...
start http://localhost:5173

echo.
echo ==========================================
echo All services have been launched in separate windows!
echo ==========================================
pause

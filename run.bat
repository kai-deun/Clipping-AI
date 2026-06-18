@echo off
echo Starting AI Video Clipper...

:: Start FastAPI Backend in a new command window
echo Starting FastAPI backend...
start cmd /k ".\venv\Scripts\python -m uvicorn app:app --reload"

:: Start Vite Frontend in a new command window
echo Starting Vite frontend...
start cmd /k "cd frontend & npm run dev"

:: Wait 3 seconds for servers to initialize
timeout /t 3 /nobreak > nul

:: Open the browser to the frontend URL
echo Opening browser...
start http://localhost:5173

echo Done! Close the command windows to stop the servers.

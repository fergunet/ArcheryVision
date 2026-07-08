@echo off
REM Lanzador de ArcheryVision para Windows (doble clic)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv
    echo.
    echo Creando entorno virtual e instalando dependencias...
    python -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual. Verifica que Python este instalado.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo La aplicacion se cerro con un error.
    pause
)

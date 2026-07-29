@echo off
REM Lanzador de ArcheryVision para Windows (doble clic)
cd /d "%~dp0"

set VENV_PY=.venv\Scripts\python.exe
set DEPS_MARKER=.venv\requirements.installed

if not exist "%VENV_PY%" (
    echo No se encontro el entorno virtual .venv
    echo.
    echo Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual. Verifica que Python este instalado.
        pause
        exit /b 1
    )
    goto :install_deps
)

if not exist "%DEPS_MARKER%" goto :install_deps

fc /b requirements.txt "%DEPS_MARKER%" >nul 2>&1
if errorlevel 1 goto :install_deps

goto :run

:install_deps
echo Instalando/actualizando dependencias (puede tardar unos minutos)...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Fallo instalando dependencias.
    pause
    exit /b 1
)
copy /y requirements.txt "%DEPS_MARKER%" >nul

:run
"%VENV_PY%" main.py

if errorlevel 1 (
    echo.
    echo La aplicacion se cerro con un error.
    pause
)

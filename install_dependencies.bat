@echo off
chcp 65001 >nul
setlocal

echo ================================================
echo   Установка зависимостей генератора документов
echo ================================================
echo.

py -3 --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Требуется Python 3.10 или новее.
    echo Установите Python 3.10+ с https://www.python.org/downloads/windows/
    echo При установке включите пункт Add Python to PATH.
    pause
    exit /b 1
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [ОШИБКА] Найден Python ниже версии 3.10.
    pause
    exit /b 1
)

py -3 -m pip install --upgrade pip
if errorlevel 1 (
    echo [ОШИБКА] Не удалось обновить pip.
    pause
    exit /b 1
)

py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не все зависимости установлены.
    echo Проверьте подключение к интернету и повторите запуск.
    pause
    exit /b 1
)

echo.
echo [ГОТОВО] Зависимости установлены.
echo Для запуска используйте: py -3 123.py
pause

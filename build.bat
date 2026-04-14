@echo off
:: ============================================================
:: build.bat — Compile Save My Data en .exe avec PyInstaller
::
:: Prérequis : pip install pyinstaller
::
:: Sortie : dist\SaveMyData\SaveMyData.exe
:: ============================================================

echo.
echo  === Save My Data — Build PyInstaller ===
echo.

:: Nettoyer les builds precedents
if exist dist\SaveMyData (
    echo  [1/3] Nettoyage dist\SaveMyData ...
    rmdir /s /q dist\SaveMyData
)
if exist build\SaveMyData (
    echo  [1/3] Nettoyage build\SaveMyData ...
    rmdir /s /q build\SaveMyData
)

echo  [2/3] Compilation en cours ...
python -m PyInstaller save_my_data.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo  [ERREUR] La compilation a echoue.
    pause
    exit /b 1
)

echo.
echo  [3/3] Build termine.
echo.
echo  Executable : dist\SaveMyData\SaveMyData.exe
echo.
pause

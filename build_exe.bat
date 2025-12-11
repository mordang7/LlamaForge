@echo off
pushd "%~dp0"
echo Building LlamaForge_BETA_V0.1a.exe...
if exist LlamaForge_BETA_V0.1a.exe del LlamaForge_BETA_V0.1a.exe
pyinstaller --onefile --noconsole --icon=LlamaForge.ico --add-data "templates;templates" --add-data "static;static" --add-data "icons;icons" --name "LlamaForge_BETA_V0.1a" app.py
if exist dist\LlamaForge_BETA_V0.1a.exe (
    move dist\LlamaForge_BETA_V0.1a.exe LlamaForge_BETA_V0.1a.exe
    rmdir /s /q build dist
    del /q *.spec
    echo Build complete: LlamaForge_BETA_V0.1a.exe
) else (
    echo Build failed.
)
pause

@echo off
echo Building LlamaGUI_C_ALPHA_V0.7.7.exe...
if exist LlamaGUI_C_ALPHA_V0.7.7.exe del LlamaGUI_C_ALPHA_V0.7.7.exe
pyinstaller --onefile --noconsole --icon=icons/LlamaGUI_32.png --add-data "templates;templates" --add-data "static;static" --add-data "icons;icons" --name "LlamaGUI_C_ALPHA_V0.7.7" app.py
if exist dist\LlamaGUI_C_ALPHA_V0.7.7.exe (
    move dist\LlamaGUI_C_ALPHA_V0.7.7.exe LlamaGUI_C_ALPHA_V0.7.7.exe
    rmdir /s /q build dist
    del /q *.spec
    echo Build complete: LlamaGUI_C_ALPHA_V0.7.7.exe
) else (
    echo Build failed.
)
pause

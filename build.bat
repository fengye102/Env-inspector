@echo off
chcp 65001 > nul
echo 正在打包 env_inspector...

pyinstaller ^
  --onefile ^
  --windowed ^
  --icon=assets/icon.ico ^
  --name=env_inspector ^
  --add-data "assets;assets" ^
  main.py

echo.
if exist dist\env_inspector.exe (
    echo 打包成功！输出文件：dist\env_inspector.exe
) else (
    echo 打包失败，请检查错误信息。
)
pause
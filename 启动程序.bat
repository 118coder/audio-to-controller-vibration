@echo off
chcp 65001 >nul
title 音频振动控制器 - 管理员启动

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ 已检测到管理员权限
    goto :run_program
) else (
    echo ⚠️ 需要管理员权限来获得最佳性能
    echo 正在请求管理员权限...
    goto :request_admin
)

:request_admin
:: 请求管理员权限并重新启动
powershell -Command "Start-Process '%~f0' -Verb RunAs -WorkingDirectory '%~dp0'"
exit

:run_program
:: 确保工作目录正确
cd /d "%~dp0"
cls
echo.
echo ╔══════════════════════════════════════╗
echo ║        音频振动控制器启动器          ║
echo ╚══════════════════════════════════════╝
echo.
echo 🎮 正在启动音频振动控制器...
echo 📍 工作目录: %~dp0
echo 🔧 以管理员权限运行以获得最佳性能
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ 错误: 未找到Python
    echo 请安装Python 3.8或更高版本
    pause
    exit /b 1
)

:: 检查requirements.txt并安装依赖（如果需要）
if exist "requirements.txt" (
    echo 🔍 检查Python依赖包...
    pip list >nul 2>&1
    if %errorLevel% neq 0 (
        echo ⚠️ 警告: pip命令不可用
    ) else (
        echo ✅ Python环境正常
    )
)

echo.
echo 🚀 启动程序...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: 启动主程序（高优先级模式）
python main.py  --chunk-size 16

:: 程序结束后的处理
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if %errorLevel% == 0 (
    echo ✅ 程序正常退出
) else (
    echo ❌ 程序异常退出 (错误代码: %errorLevel%)
    echo.
    echo 常见问题解决方案:
    echo 1. 检查手柄是否正确连接
    echo 2. 确认音频设备可用
    echo 3. 查看上方错误信息
)

echo.
echo 📝 按任意键退出...
pause >nul

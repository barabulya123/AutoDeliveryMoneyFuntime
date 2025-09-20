@echo off
chcp 65001 > nul
title Minecraft Currency Plugin - Универсальный Установщик
color 0A

echo.
echo ===============================================================================
echo 🎮 MINECRAFT CURRENCY PLUGIN - УНИВЕРСАЛЬНЫЙ УСТАНОВЩИК
echo    Автоматическая установка ВСЕХ компонентов
echo    Версия: 2.0 ^| Для FunPay Cardinal
echo ===============================================================================
echo.

echo 🔍 Проверка Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден!
    echo.
    echo 📋 ТРЕБУЕТСЯ PYTHON 3.7+
    echo    Скачайте с: https://python.org/downloads/
    echo.
    echo 💡 При установке Python обязательно отметьте:
    echo    "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% найден

echo.
echo 🚀 Запуск универсального установщика...
echo.
echo ⚠️  ВНИМАНИЕ: Установщик автоматически скачает и установит:
echo    • Node.js (если не установлен)
echo    • Все Python зависимости
echo    • Все npm пакеты
echo    • Настроит плагин
echo.
echo 📡 Требуется интернет-соединение для скачивания компонентов
echo.

set /p confirm="Продолжить установку? (y/N): "
if /i not "%confirm%"=="y" (
    echo Установка отменена пользователем.
    pause
    exit /b 0
)

echo.
echo 🔄 Запуск Python установщика...
echo.

python minecraft_currency_universal_installer.py

if %errorlevel% equ 0 (
    echo.
    echo ===============================================================================
    echo ✅ УНИВЕРСАЛЬНАЯ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!
    echo ===============================================================================
    echo.
    echo 🚀 СЛЕДУЮЩИЕ ШАГИ:
    echo    1. Запустите Cardinal: python main.py
    echo    2. В Telegram: /mc_settings
    echo    3. 🚨 ОБЯЗАТЕЛЬНО смените данные бота на СВОИ!
    echo    4. Настройте chat_id для уведомлений
    echo    5. Тест: /mc_test_bot
    echo    6. Запуск: /mc_start
    echo.
    echo 💡 ВАЖНО: Замените стандартные YourBotUsername/YourBotPassword на ваши!
    echo 📞 Поддержка: @ilpajj
    echo.
) else (
    echo.
    echo ❌ ОШИБКА ПРИ УСТАНОВКЕ
    echo.
    echo 🔧 Возможные причины:
    echo    • Нет интернет-соединения
    echo    • Недостаточно прав администратора
    echo    • Проблемы с загрузкой компонентов
    echo.
    echo 💡 Попробуйте:
    echo    1. Запустить от имени администратора
    echo    2. Проверить интернет-соединение
    echo    3. Временно отключить антивирус
    echo.
    echo 📞 Поддержка: @ilpajj
    echo.
)

echo ===============================================================================
pause

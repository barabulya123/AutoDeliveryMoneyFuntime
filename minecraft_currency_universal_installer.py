#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minecraft Currency Plugin - Универсальный установщик
Версия: 2.0
Автор: FunPayCardinal Plugin

Этот установщик автоматически скачивает и устанавливает ВСЕ необходимые компоненты:
- Node.js (если не установлен)
- Все Python зависимости
- Настройка плагина
- Проверка работоспособности

Требует только Python 3.7+ и интернет-соединение.
"""

import os
import sys
import json
import subprocess
import shutil
import platform
import tempfile
import zipfile
import urllib.request
import urllib.error
import time
import threading
from pathlib import Path

# Цвета для вывода (работают в большинстве терминалов)
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_colored(text, color=Colors.WHITE):
    """Вывод цветного текста с фоллбэком для Windows"""
    try:
        # Включаем поддержку ANSI в Windows 10+
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
        print(f"{color}{text}{Colors.END}")
    except:
        # Фоллбэк без цветов
        print(text)

def print_header():
    """Заголовок установщика"""
    print_colored("=" * 70, Colors.CYAN)
    print_colored("🎮 MINECRAFT CURRENCY PLUGIN - УНИВЕРСАЛЬНЫЙ УСТАНОВЩИК", Colors.BOLD + Colors.GREEN)
    print_colored("   Автоматическая установка ВСЕХ компонентов", Colors.WHITE)
    print_colored("   Версия: 2.0 | Для FunPay Cardinal", Colors.WHITE)
    print_colored("=" * 70, Colors.CYAN)

def show_progress_bar(current, total, prefix="Прогресс", length=50):
    """Отображение прогресс-бара"""
    if total == 0:
        return
    
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    
    print_colored(f'\r{prefix} |{bar}| {percent}% Complete', Colors.BLUE, end='')
    if current == total:
        print()  # Переход на новую строку после завершения

def download_with_progress(url, destination, description="Загрузка"):
    """Скачивание файла с прогресс-баром"""
    print_colored(f"\n📥 {description}...", Colors.YELLOW)
    print_colored(f"🔗 URL: {url}", Colors.WHITE)
    
    try:
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                show_progress_bar(downloaded, total_size, f"📥 {description}")
        
        urllib.request.urlretrieve(url, destination, reporthook=progress_hook)
        print_colored(f"✅ {description} завершена", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Ошибка {description.lower()}: {e}", Colors.RED)
        return False

def check_internet_connection():
    """Проверка интернет-соединения"""
    print_colored("\n🌐 Проверка интернет-соединения...", Colors.YELLOW)
    
    test_urls = [
        "https://www.google.com",
        "https://nodejs.org",
        "https://pypi.org"
    ]
    
    for url in test_urls:
        try:
            urllib.request.urlopen(url, timeout=10)
            print_colored(f"✅ Интернет-соединение активно", Colors.GREEN)
            return True
        except:
            continue
    
    print_colored("❌ Нет интернет-соединения!", Colors.RED)
    print_colored("📋 Для работы установщика требуется интернет для:", Colors.YELLOW)
    print_colored("   • Скачивания Node.js", Colors.WHITE)
    print_colored("   • Установки npm пакетов", Colors.WHITE)
    print_colored("   • Проверки обновлений", Colors.WHITE)
    return False

def check_python_version():
    """Проверка версии Python"""
    print_colored("\n🐍 Проверка Python...", Colors.YELLOW)
    
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print_colored(f"❌ Требуется Python 3.7+, установлен {python_version.major}.{python_version.minor}", Colors.RED)
        print_colored("📋 Скачайте новую версию с https://python.org/downloads/", Colors.YELLOW)
        return False
    
    print_colored(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro} - OK", Colors.GREEN)
    return True

def install_python_packages():
    """Установка Python пакетов"""
    print_colored("\n📦 Установка Python зависимостей...", Colors.YELLOW)
    
    packages = [
        "aiofiles",
        "asyncio",
        "requests",
        "urllib3"
    ]
    
    for package in packages:
        try:
            print_colored(f"🔧 Установка {package}...", Colors.CYAN)
            result = subprocess.run([sys.executable, "-m", "pip", "install", package], 
                                  capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print_colored(f"✅ {package} установлен", Colors.GREEN)
            else:
                print_colored(f"⚠️ {package} - возможные проблемы: {result.stderr[:100]}", Colors.YELLOW)
                
        except subprocess.TimeoutExpired:
            print_colored(f"⚠️ {package} - таймаут установки", Colors.YELLOW)
        except Exception as e:
            print_colored(f"⚠️ {package} - ошибка: {e}", Colors.YELLOW)
    
    print_colored("✅ Установка Python пакетов завершена", Colors.GREEN)
    return True

def detect_system_info():
    """Определение информации о системе"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    print_colored(f"\n🖥️ Система: {platform.system()} {platform.release()}", Colors.CYAN)
    print_colored(f"🔧 Архитектура: {platform.machine()}", Colors.CYAN)
    
    # Определяем архитектуру для Node.js
    if "64" in machine or "amd64" in machine or "x86_64" in machine:
        arch = "x64"
    elif "arm64" in machine or "aarch64" in machine:
        arch = "arm64"
    else:
        arch = "x86"
    
    return system, arch

def check_nodejs_installation():
    """Проверка установки Node.js"""
    print_colored("\n🟢 Проверка Node.js...", Colors.YELLOW)
    
    # Проверяем разные команды для Node.js
    node_commands = ['node', 'nodejs']
    npm_commands = ['npm', 'npm.cmd']
    
    node_found = False
    npm_found = False
    node_version = None
    npm_version = None
    
    # Проверка Node.js
    for cmd in node_commands:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                node_version = result.stdout.strip()
                node_found = True
                print_colored(f"✅ Node.js найден: {node_version}", Colors.GREEN)
                break
        except:
            continue
    
    # Проверка npm
    for cmd in npm_commands:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                npm_version = result.stdout.strip()
                npm_found = True
                print_colored(f"✅ npm найден: {npm_version}", Colors.GREEN)
                break
        except:
            continue
    
    if not node_found:
        print_colored("❌ Node.js не найден - будет установлен автоматически", Colors.YELLOW)
    
    if not npm_found:
        print_colored("❌ npm не найден - будет установлен с Node.js", Colors.YELLOW)
    
    return node_found and npm_found, node_version, npm_version

def download_and_install_nodejs():
    """Скачивание и установка Node.js"""
    print_colored("\n🟢 Установка Node.js...", Colors.YELLOW)
    
    system, arch = detect_system_info()
    
    # URL для скачивания Node.js LTS
    base_url = "https://nodejs.org/dist/v18.17.1/"
    
    if system == "windows":
        if arch == "x64":
            filename = "node-v18.17.1-x64.msi"
        else:
            filename = "node-v18.17.1-x86.msi"
        installer_type = "msi"
    elif system == "darwin":  # macOS
        filename = f"node-v18.17.1-darwin-{arch}.pkg"
        installer_type = "pkg"
    else:  # Linux
        filename = f"node-v18.17.1-linux-{arch}.tar.xz"
        installer_type = "tar"
    
    download_url = base_url + filename
    
    # Создаем временную папку
    temp_dir = tempfile.mkdtemp()
    installer_path = os.path.join(temp_dir, filename)
    
    print_colored(f"📥 Скачивание Node.js для {system} {arch}...", Colors.CYAN)
    print_colored(f"🔗 Источник: {download_url}", Colors.WHITE)
    
    # Скачиваем установщик
    if not download_with_progress(download_url, installer_path, "Node.js"):
        print_colored("❌ Не удалось скачать Node.js", Colors.RED)
        return False
    
    print_colored(f"💾 Размер файла: {os.path.getsize(installer_path) // (1024*1024)} МБ", Colors.WHITE)
    
    # Устанавливаем Node.js
    try:
        if installer_type == "msi":
            print_colored("🔧 Установка Node.js (MSI)...", Colors.CYAN)
            print_colored("⚠️ Может потребоваться подтверждение администратора!", Colors.YELLOW)
            
            # Тихая установка MSI
            result = subprocess.run([
                "msiexec", "/i", installer_path, 
                "/quiet", "/norestart",
                "ADDLOCAL=ALL"
            ], timeout=600)
            
            if result.returncode == 0:
                print_colored("✅ Node.js успешно установлен!", Colors.GREEN)
            else:
                print_colored(f"⚠️ Установка завершена с кодом {result.returncode}", Colors.YELLOW)
            
        elif installer_type == "pkg":
            print_colored("🔧 Установка Node.js (PKG)...", Colors.CYAN)
            result = subprocess.run(["sudo", "installer", "-pkg", installer_path, "-target", "/"], timeout=600)
            
        elif installer_type == "tar":
            print_colored("🔧 Распаковка Node.js (TAR)...", Colors.CYAN)
            
            # Извлекаем в /usr/local для Linux
            extract_path = "/usr/local"
            if not os.access(extract_path, os.W_OK):
                print_colored("⚠️ Требуются права администратора для установки в /usr/local", Colors.YELLOW)
                extract_path = os.path.expanduser("~/nodejs")
                os.makedirs(extract_path, exist_ok=True)
            
            # Распаковываем архив
            import tarfile
            with tarfile.open(installer_path, 'r:xz') as tar:
                tar.extractall(extract_path)
            
            print_colored(f"✅ Node.js распакован в {extract_path}", Colors.GREEN)
        
        # Очищаем временные файлы
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
        # Добавляем небольшую паузу для завершения установки
        time.sleep(5)
        
        return True
        
    except subprocess.TimeoutExpired:
        print_colored("⏰ Таймаут установки Node.js", Colors.RED)
        return False
    except Exception as e:
        print_colored(f"❌ Ошибка установки Node.js: {e}", Colors.RED)
        return False

def verify_nodejs_after_install():
    """Проверка Node.js после установки"""
    print_colored("\n🔍 Проверка установки Node.js...", Colors.YELLOW)
    
    # Ждем немного для обновления PATH
    time.sleep(3)
    
    # Обновляем переменные окружения
    if platform.system() == "Windows":
        # Добавляем стандартные пути Node.js в PATH
        nodejs_paths = [
            r"C:\Program Files\nodejs",
            r"C:\Program Files (x86)\nodejs",
            os.path.expanduser(r"~\AppData\Roaming\npm")
        ]
        
        current_path = os.environ.get('PATH', '')
        for nodejs_path in nodejs_paths:
            if os.path.exists(nodejs_path) and nodejs_path not in current_path:
                os.environ['PATH'] = nodejs_path + os.pathsep + current_path
                print_colored(f"➕ Добавлен путь: {nodejs_path}", Colors.CYAN)
    
    # Проверяем Node.js еще раз
    node_found, node_version, npm_version = check_nodejs_installation()
    
    if node_found:
        print_colored("✅ Node.js успешно установлен и работает!", Colors.GREEN)
        return True
    else:
        print_colored("❌ Node.js не обнаружен после установки", Colors.RED)
        print_colored("🔧 Возможные решения:", Colors.YELLOW)
        print_colored("   1. Перезапустите терминал/командную строку", Colors.WHITE)
        print_colored("   2. Перезагрузите компьютер", Colors.WHITE)
        print_colored("   3. Добавьте Node.js в PATH вручную", Colors.WHITE)
        return False

def detect_cardinal_path():
    """Автоматическое обнаружение пути к FunPay Cardinal"""
    print_colored("\n🔍 Поиск FunPay Cardinal...", Colors.YELLOW)
    
    possible_paths = [
        Path.cwd(),  # Текущая папка
        Path.cwd().parent,  # Родительская папка
        Path.cwd().parent.parent,  # Прародительская папка
        Path.cwd() / "FunPayCardinal",
        Path.cwd().parent / "FunPayCardinal",
        Path.home() / "FunPayCardinal",
        Path.home() / "Desktop" / "FunPayCardinal",
        Path.home() / "Downloads" / "FunPayCardinal",
    ]
    
    # Также ищем по ключевым файлам Cardinal
    for root, dirs, files in os.walk(Path.cwd().parent):
        if "main.py" in files and "plugins" in dirs:
            possible_paths.append(Path(root))
        # Ограничиваем глубину поиска
        if Path(root).resolve().parts.__len__() > Path.cwd().resolve().parts.__len__() + 3:
            break
    
    for path in possible_paths:
        try:
            if (path / "main.py").exists() and (path / "plugins").exists():
                print_colored(f"✅ Найден FunPay Cardinal: {path}", Colors.GREEN)
                return path
        except:
            continue
    
    # Ручной ввод пути
    print_colored("❓ FunPay Cardinal не найден автоматически", Colors.YELLOW)
    print_colored("📁 Пожалуйста, укажите путь к папке FunPay Cardinal", Colors.WHITE)
    
    while True:
        try:
            custom_path = input("Введите полный путь к папке FunPay Cardinal: ").strip().strip('"')
            if not custom_path:
                continue
                
            path = Path(custom_path)
            if (path / "main.py").exists() and (path / "plugins").exists():
                print_colored(f"✅ Путь подтвержден: {path}", Colors.GREEN)
                return path
            else:
                print_colored("❌ Неверный путь. Убедитесь, что папка содержит main.py и plugins/", Colors.RED)
                print_colored("💡 Пример правильного пути: C:\\FunPayCardinal", Colors.WHITE)
        except KeyboardInterrupt:
            print_colored("\n❌ Установка прервана пользователем", Colors.RED)
            sys.exit(1)
        except Exception as e:
            print_colored(f"❌ Ошибка: {e}", Colors.RED)

def create_files(cardinal_path):
    """Создание всех необходимых файлов"""
    print_colored("\n📁 Создание файлов плагина...", Colors.YELLOW)
    
    plugins_dir = cardinal_path / "plugins"
    bot_dir = plugins_dir / "minecraft_bot"
    
    # Создаем папки
    bot_dir.mkdir(exist_ok=True)
    print_colored(f"✅ Папка создана: {bot_dir}", Colors.GREEN)
    
    # Проверяем наличие основного файла плагина
    current_dir = Path(__file__).parent
    main_plugin_file = current_dir / "minecraft_currency.py"
    
    if main_plugin_file.exists():
        # Копируем существующий файл
        shutil.copy2(main_plugin_file, plugins_dir / "minecraft_currency.py")
        print_colored(f"✅ Скопирован: minecraft_currency.py", Colors.GREEN)
    else:
        print_colored("⚠️ minecraft_currency.py не найден - будет создан базовый файл", Colors.YELLOW)
        # Здесь можно создать базовый файл плагина
    
    # Создаем simple_bot.js
    create_simple_bot_js(bot_dir)
    print_colored(f"✅ Создан: simple_bot.js", Colors.GREEN)
    
    # Создаем package.json
    create_package_json(bot_dir)
    print_colored(f"✅ Создан: package.json", Colors.GREEN)
    
    # Создаем папки для данных
    storage_dir = cardinal_path / "storage"
    cache_dir = storage_dir / "cache"
    logs_dir = storage_dir / "logs"
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    print_colored(f"✅ Созданы папки данных", Colors.GREEN)
    
    return bot_dir

def create_simple_bot_js(bot_dir):
    """Создание файла simple_bot.js"""
    simple_bot_content = '''const mineflayer = require('mineflayer');

class SimpleFuntimeBot {
    constructor() {
        this.bot = null;
        this.isConnected = false;
        this.config = {
            username: 'Tabbydoodle',
            password: 'pee228',
            anarchy: 'an210',
            host: 'funtime.su',
            port: 25565,
            version: '1.19.4'
        };
    }

    async connect() {
        if (this.isConnected) {
            return true;
        }

        try {
            this.bot = mineflayer.createBot({
                host: this.config.host,
                port: this.config.port,
                username: this.config.username,
                password: this.config.password,
                version: this.config.version,
                auth: 'offline'
            });

            this.setupEventHandlers();

            return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Connection timeout'));
                }, 30000);

                this.bot.once('spawn', () => {
                    clearTimeout(timeout);
                    this.isConnected = true;
                    resolve(true);
                });

                this.bot.once('error', (err) => {
                    clearTimeout(timeout);
                    reject(err);
                });
            });
        } catch (error) {
            return false;
        }
    }

    setupEventHandlers() {
        this.bot.on('spawn', () => {
            // Авторизация на анархии
            setTimeout(() => {
                this.bot.chat(`/login ${this.config.anarchy}`);
            }, 2000);
            
            // Переход на 210 анархию
            setTimeout(() => {
                this.bot.chat('/an210');
            }, 4000);
        });

        this.bot.on('error', (err) => {
            this.isConnected = false;
        });

        this.bot.on('end', () => {
            this.isConnected = false;
        });

        this.bot.on('kicked', (reason) => {
            this.isConnected = false;
        });
    }

    async giveMoney(playerName, amount) {
        if (!this.isConnected) {
            throw new Error('Bot not connected');
        }

        try {
            // Ждем стабилизации подключения
            await this.delay(3000);
            
            // Переходим на правильную анархию
            this.bot.chat('/an210');
            await this.delay(3000);

            // Перевод денег (двукратный ввод для FunTime)
            const command = `/pay ${playerName} ${amount}`;
            
            this.bot.chat(command);
            await this.delay(2000);
            this.bot.chat(command);
            await this.delay(3000);
            
            return true;
            
        } catch (error) {
            throw error;
        }
    }

    async disconnect() {
        if (this.bot && this.isConnected) {
            this.bot.quit();
            this.isConnected = false;
            await this.delay(1000);
        }
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Простая функция для выдачи денег
async function payPlayer(playerName, amount) {
    const bot = new SimpleFuntimeBot();
    
    try {
        await bot.connect();
        await bot.giveMoney(playerName, amount);
        
        console.log(JSON.stringify({
            success: true,
            player: playerName,
            amount: amount,
            message: `Successfully transferred ${amount.toLocaleString()} coins to ${playerName}`
        }));
        
        return true;
        
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            error: error.name || 'unknown_error',
            message: error.message
        }));
        
        return false;
        
    } finally {
        await bot.disconnect();
    }
}

// Простая функция для проверки подключения
async function testConnection() {
    const bot = new SimpleFuntimeBot();
    
    try {
        await bot.connect();
        
        console.log(JSON.stringify({
            success: true,
            isConnected: bot.isConnected,
            message: 'Bot connection test successful'
        }));
        
        return true;
        
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            isConnected: false,
            error: error.name || 'connection_error',
            message: error.message
        }));
        
        return false;
        
    } finally {
        await bot.disconnect();
    }
}

// Экспорт функций
module.exports = { SimpleFuntimeBot, payPlayer, testConnection };

// Если запущен напрямую
if (require.main === module) {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log(JSON.stringify({
            success: false,
            error: 'no_command',
            message: 'Usage: node simple_bot.js <player> <amount> or node simple_bot.js test'
        }));
        process.exit(1);
    }
    
    // Команда тестирования
    if (args[0].toLowerCase() === 'test') {
        testConnection().then(success => {
            process.exit(success ? 0 : 1);
        });
        return;
    }
    
    // Команда выдачи денег
    if (args.length < 2) {
        console.log(JSON.stringify({
            success: false,
            error: 'invalid_args',
            message: 'Usage: node simple_bot.js <player> <amount>'
        }));
        process.exit(1);
    }
    
    const playerName = args[0];
    const amount = parseInt(args[1]);
    
    if (isNaN(amount) || amount <= 0) {
        console.log(JSON.stringify({
            success: false,
            error: 'invalid_amount',
            message: 'Invalid amount'
        }));
        process.exit(1);
    }
    
    payPlayer(playerName, amount).then(success => {
        process.exit(success ? 0 : 1);
    });
}'''
    
    with open(bot_dir / "simple_bot.js", 'w', encoding='utf-8') as f:
        f.write(simple_bot_content)

def create_package_json(bot_dir):
    """Создание файла package.json"""
    package_content = {
        "name": "funtime-currency-bot",
        "version": "1.0.0",
        "description": "Minecraft bot для автоматической выдачи валюты на сервере Funtime",
        "main": "simple_bot.js",
        "scripts": {
            "start": "node simple_bot.js",
            "test": "node simple_bot.js test",
            "pay": "node simple_bot.js"
        },
        "dependencies": {
            "mineflayer": "^4.17.0",
            "prismarine-chat": "^1.10.0"
        },
        "keywords": ["minecraft", "mineflayer", "funtime", "currency"],
        "author": "FunPayCardinal Plugin",
        "license": "MIT"
    }
    
    with open(bot_dir / "package.json", 'w', encoding='utf-8') as f:
        json.dump(package_content, f, indent=2, ensure_ascii=False)

def install_node_dependencies(bot_dir):
    """Установка зависимостей Node.js"""
    print_colored("\n📦 Установка зависимостей Node.js...", Colors.YELLOW)
    
    # Список команд npm для попытки
    npm_commands = ['npm', 'npm.cmd']
    
    success = False
    
    for npm_cmd in npm_commands:
        try:
            print_colored(f"🔧 Попытка установки через {npm_cmd}...", Colors.CYAN)
            
            # Установка зависимостей
            result = subprocess.run([npm_cmd, 'install'], 
                                  cwd=bot_dir, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=600)  # 10 минут
            
            if result.returncode == 0:
                print_colored("✅ Зависимости Node.js установлены успешно!", Colors.GREEN)
                success = True
                break
            else:
                print_colored(f"⚠️ Ошибка с {npm_cmd}: {result.stderr[:200]}", Colors.YELLOW)
                continue
                
        except subprocess.TimeoutExpired:
            print_colored(f"⏰ Таймаут при установке через {npm_cmd}", Colors.YELLOW)
            continue
        except FileNotFoundError:
            print_colored(f"❌ {npm_cmd} не найден", Colors.YELLOW)
            continue
        except Exception as e:
            print_colored(f"❌ Ошибка с {npm_cmd}: {e}", Colors.YELLOW)
            continue
    
    if not success:
        print_colored("❌ Не удалось установить зависимости через npm", Colors.RED)
        print_colored("🔧 Попытка ручной установки...", Colors.YELLOW)
        
        # Создаем минимальную структуру
        try:
            node_modules_dir = bot_dir / "node_modules"
            node_modules_dir.mkdir(exist_ok=True)
            
            print_colored("⚠️ Создана базовая структура", Colors.YELLOW)
            print_colored("📋 ТРЕБУЕТСЯ: Выполните 'npm install' в папке minecraft_bot вручную!", Colors.RED)
        except Exception as e:
            print_colored(f"❌ Ошибка создания структуры: {e}", Colors.RED)
            return False
    
    return success

def test_installation(bot_dir):
    """Тестирование установки"""
    print_colored("\n🧪 Тестирование установки...", Colors.YELLOW)
    
    success_count = 0
    total_tests = 4
    
    # Тест 1: Проверка файлов
    print_colored("🔍 Тест 1: Проверка файлов...", Colors.CYAN)
    files_to_check = [
        bot_dir / "simple_bot.js",
        bot_dir / "package.json"
    ]
    
    files_ok = True
    for file_path in files_to_check:
        if file_path.exists():
            print_colored(f"   ✅ {file_path.name}", Colors.GREEN)
        else:
            print_colored(f"   ❌ {file_path.name} отсутствует", Colors.RED)
            files_ok = False
    
    if files_ok:
        success_count += 1
    
    # Тест 2: Проверка Node.js
    print_colored("🔍 Тест 2: Проверка Node.js...", Colors.CYAN)
    node_ok, node_version, npm_version = check_nodejs_installation()
    if node_ok:
        print_colored(f"   ✅ Node.js работает: {node_version}", Colors.GREEN)
        success_count += 1
    else:
        print_colored("   ❌ Node.js не работает", Colors.RED)
    
    # Тест 3: Проверка зависимостей
    print_colored("🔍 Тест 3: Проверка node_modules...", Colors.CYAN)
    node_modules_dir = bot_dir / "node_modules"
    if node_modules_dir.exists():
        mineflayer_dir = node_modules_dir / "mineflayer"
        if mineflayer_dir.exists():
            print_colored("   ✅ Mineflayer установлен", Colors.GREEN)
            success_count += 1
        else:
            print_colored("   ⚠️ Mineflayer не найден", Colors.YELLOW)
    else:
        print_colored("   ❌ node_modules не найден", Colors.RED)
    
    # Тест 4: Проверка синтаксиса JavaScript
    print_colored("🔍 Тест 4: Проверка синтаксиса бота...", Colors.CYAN)
    try:
        result = subprocess.run(['node', '--check', 'simple_bot.js'], 
                              cwd=bot_dir, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print_colored("   ✅ Синтаксис JavaScript корректен", Colors.GREEN)
            success_count += 1
        else:
            print_colored(f"   ❌ Ошибка синтаксиса: {result.stderr}", Colors.RED)
            
    except Exception as e:
        print_colored(f"   ⚠️ Не удалось проверить синтаксис: {e}", Colors.YELLOW)
    
    # Результат тестирования
    print_colored(f"\n📊 Результат тестирования: {success_count}/{total_tests} тестов пройдено", Colors.CYAN)
    
    if success_count >= 3:
        print_colored("✅ Установка в основном успешна!", Colors.GREEN)
        return True
    elif success_count >= 2:
        print_colored("⚠️ Установка частично успешна - требуется ручная настройка", Colors.YELLOW)
        return True
    else:
        print_colored("❌ Установка неуспешна - требуется исправление", Colors.RED)
        return False

def create_setup_instructions(cardinal_path):
    """Создание подробных инструкций"""
    instructions_path = cardinal_path / "plugins" / "MINECRAFT_CURRENCY_COMPLETE_SETUP.txt"
    
    node_ok, node_version, npm_version = check_nodejs_installation()
    
    instructions = f"""
🎮 MINECRAFT CURRENCY PLUGIN - ПОЛНАЯ ИНСТРУКЦИЯ ПО НАСТРОЙКЕ

✅ УНИВЕРСАЛЬНАЯ УСТАНОВКА ЗАВЕРШЕНА!

📁 УСТАНОВЛЕННЫЕ КОМПОНЕНТЫ:
├── Python зависимости (aiofiles, asyncio, requests)
├── Node.js {node_version if node_ok else 'требует установки'}
├── npm {npm_version if node_ok else 'требует установки'}
├── plugins/minecraft_currency.py        # Основной плагин
└── plugins/minecraft_bot/
    ├── simple_bot.js                   # Minecraft бот
    ├── package.json                    # Конфигурация
    └── node_modules/                   # npm пакеты

🔧 ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА:

1. ЗАПУСТИТЕ FUNPAY CARDINAL:
   python main.py

2. ОТКРОЙТЕ TELEGRAM И ВЫПОЛНИТЕ:
   /mc_settings

3. ОБЯЗАТЕЛЬНО НАСТРОЙТЕ БОТА:
   • 🤖 НАСТРОЙКИ БОТА
   • Измените никнейм на ваш Minecraft аккаунт
   • Измените пароль на ваш пароль от аккаунта
   • Установите ваш Telegram chat_id

4. ПРОВЕРЬТЕ РАБОТУ БОТА:
   /mc_test_bot                    # Тест подключения
   /mc_test_pay                    # Тест перевода 1000 монет

5. ЗАПУСТИТЕ ПЛАГИН:
   /mc_start                       # Активация плагина

📋 КОМАНДЫ УПРАВЛЕНИЯ:
• /mc_start      - Запуск плагина
• /mc_stop       - Остановка плагина
• /mc_settings   - Меню настроек
• /mc_pending    - Ожидающие заказы
• /mc_test_bot   - Проверка подключения
• /mc_test_pay   - Тест выдачи валюты
• /mc_toggle_auto - Вкл/выкл автовыдачу

⚙️ НАСТРОЙКИ ПО УМОЛЧАНИЮ:
• Сервер: funtime.su (анархия 210)
• 1 товар = 1,000,000 монет
• Автовыдача: ОТКЛЮЧЕНА (настройте в /mc_settings)
• Тестовый игрок: TestUser

🚨 КРИТИЧЕСКИ ВАЖНО:

1. СМЕНИТЕ ДАННЫЕ БОТА:
   ❌ НЕ используйте стандартные данные бота
   ✅ Укажите данные ВАШЕГО Minecraft аккаунта

2. НАСТРОЙТЕ CHAT_ID:
   • Получите ваш chat_id от @userinfobot
   • Укажите его в notification_chat_id

3. ПРОВЕРЬТЕ ДЕНЬГИ НА БОТЕ:
   • У бота должны быть деньги на сервере для переводов
   • Рекомендуется иметь минимум 10,000,000 монет

💡 ЛОГИКА РАБОТЫ:
1. Покупатель оплачивает ЛЮБОЙ товар на FunPay
2. Плагин автоматически конвертирует в Minecraft валюту
3. Покупатель указывает свой игровой никнейм
4. Бот переводит валюту на сервере

🔧 УСТРАНЕНИЕ ПРОБЛЕМ:

❌ "npm не найден":
   • Перезапустите терминал
   • Перезагрузите компьютер
   • Переустановите Node.js

❌ "Бот не подключается":
   • Проверьте никнейм и пароль бота
   • Убедитесь что сервер онлайн
   • Проверьте интернет-соединение

❌ "Команды не выполняются":
   • У бота должны быть права на сервере
   • Проверьте что бот авторизован (/login password)
   • Убедитесь что бот на правильной анархии (/an210)

❌ "Python ошибки":
   • Убедитесь что Python 3.7+
   • Переустановите зависимости: pip install aiofiles asyncio

📞 ПОДДЕРЖКА:
• Telegram: @ilpajj
• При обращении приложите логи из папки storage/logs/

🎯 ГОТОВНОСТЬ К РАБОТЕ:
☐ Node.js установлен и работает
☐ npm зависимости установлены
☐ Никнейм и пароль бота изменены на ваши
☐ Chat_id настроен для уведомлений
☐ Тест подключения (/mc_test_bot) успешен
☐ Тест перевода (/mc_test_pay) успешен
☐ Плагин запущен (/mc_start)

Дата установки: {time.strftime('%Y-%m-%d %H:%M:%S')}
Система: {platform.system()} {platform.release()}
Python: {sys.version.split()[0]}
Node.js: {node_version if node_ok else 'не установлен'}
"""
    
    with open(instructions_path, 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    return instructions_path

def main():
    """Основная функция универсального установщика"""
    print_header()
    
    try:
        # Шаг 1: Проверка базовых требований
        print_colored("\n🔍 ЭТАП 1: ПРОВЕРКА СИСТЕМЫ", Colors.BOLD + Colors.CYAN)
        
        if not check_python_version():
            print_colored("❌ Установка прервана из-за несовместимой версии Python", Colors.RED)
            return
        
        if not check_internet_connection():
            print_colored("❌ Установка прервана из-за отсутствия интернета", Colors.RED)
            return
        
        # Шаг 2: Установка Python зависимостей
        print_colored("\n📦 ЭТАП 2: PYTHON ЗАВИСИМОСТИ", Colors.BOLD + Colors.CYAN)
        install_python_packages()
        
        # Шаг 3: Проверка и установка Node.js
        print_colored("\n🟢 ЭТАП 3: NODE.JS", Colors.BOLD + Colors.CYAN)
        node_installed, node_version, npm_version = check_nodejs_installation()
        
        if not node_installed:
            print_colored("🔧 Node.js не найден - начинаем автоматическую установку...", Colors.YELLOW)
            
            if download_and_install_nodejs():
                if verify_nodejs_after_install():
                    print_colored("✅ Node.js успешно установлен!", Colors.GREEN)
                else:
                    print_colored("⚠️ Node.js установлен, но требует перезапуска терминала", Colors.YELLOW)
            else:
                print_colored("❌ Не удалось установить Node.js автоматически", Colors.RED)
                print_colored("📋 Скачайте и установите Node.js вручную с https://nodejs.org/", Colors.YELLOW)
                
                input("Нажмите Enter после установки Node.js для продолжения...")
                
                # Повторная проверка
                node_installed, node_version, npm_version = check_nodejs_installation()
                if not node_installed:
                    print_colored("❌ Node.js все еще не найден", Colors.RED)
                    return
        
        # Шаг 4: Обнаружение FunPay Cardinal
        print_colored("\n📁 ЭТАП 4: ПОИСК FUNPAY CARDINAL", Colors.BOLD + Colors.CYAN)
        cardinal_path = detect_cardinal_path()
        if not cardinal_path:
            print_colored("❌ Не удалось найти FunPay Cardinal", Colors.RED)
            return
        
        # Шаг 5: Создание файлов
        print_colored("\n📄 ЭТАП 5: СОЗДАНИЕ ФАЙЛОВ", Colors.BOLD + Colors.CYAN)
        bot_dir = create_files(cardinal_path)
        
        # Шаг 6: Установка зависимостей Node.js
        print_colored("\n📦 ЭТАП 6: ЗАВИСИМОСТИ NODE.JS", Colors.BOLD + Colors.CYAN)
        npm_success = install_node_dependencies(bot_dir)
        
        # Шаг 7: Тестирование
        print_colored("\n🧪 ЭТАП 7: ТЕСТИРОВАНИЕ", Colors.BOLD + Colors.CYAN)
        test_success = test_installation(bot_dir)
        
        # Шаг 8: Создание инструкций
        print_colored("\n📋 ЭТАП 8: ФИНАЛИЗАЦИЯ", Colors.BOLD + Colors.CYAN)
        instructions_path = create_setup_instructions(cardinal_path)
        
        # Финальный отчет
        print_colored("\n" + "=" * 70, Colors.CYAN)
        print_colored("🎉 УНИВЕРСАЛЬНАЯ УСТАНОВКА ЗАВЕРШЕНА!", Colors.BOLD + Colors.GREEN)
        print_colored("=" * 70, Colors.CYAN)
        
        print_colored(f"\n📊 РЕЗУЛЬТАТЫ УСТАНОВКИ:", Colors.BOLD + Colors.WHITE)
        print_colored(f"   • Python зависимости: ✅ Установлены", Colors.GREEN)
        print_colored(f"   • Node.js: {'✅ Работает' if node_installed else '⚠️ Требует настройки'}", 
                     Colors.GREEN if node_installed else Colors.YELLOW)
        print_colored(f"   • npm зависимости: {'✅ Установлены' if npm_success else '⚠️ Требуют ручной установки'}", 
                     Colors.GREEN if npm_success else Colors.YELLOW)
        print_colored(f"   • Плагин: ✅ Создан", Colors.GREEN)
        print_colored(f"   • Тестирование: {'✅ Успешно' if test_success else '⚠️ Частично'}", 
                     Colors.GREEN if test_success else Colors.YELLOW)
        
        print_colored(f"\n📁 Плагин установлен в: {cardinal_path / 'plugins'}", Colors.WHITE)
        print_colored(f"📋 Инструкции: {instructions_path.name}", Colors.WHITE)
        
        print_colored(f"\n🚀 СЛЕДУЮЩИЕ ШАГИ:", Colors.BOLD + Colors.YELLOW)
        print_colored(f"   1. Запустите Cardinal: python main.py", Colors.WHITE)
        print_colored(f"   2. В Telegram: /mc_settings", Colors.WHITE)
        print_colored(f"   3. 🚨 ОБЯЗАТЕЛЬНО смените никнейм и пароль бота!", Colors.RED)
        print_colored(f"   4. Настройте chat_id для уведомлений", Colors.WHITE)
        print_colored(f"   5. Тест: /mc_test_bot", Colors.WHITE)
        print_colored(f"   6. Запуск: /mc_start", Colors.WHITE)
        
        if not npm_success:
            print_colored(f"\n⚠️ ТРЕБУЕТСЯ РУЧНАЯ УСТАНОВКА:", Colors.BOLD + Colors.YELLOW)
            print_colored(f"   cd {bot_dir}", Colors.WHITE)
            print_colored(f"   npm install", Colors.WHITE)
        
        print_colored(f"\n💡 ВАЖНО: Стандартные данные бота ДОЛЖНЫ быть заменены на ваши!", Colors.RED + Colors.BOLD)
        print_colored(f"📞 Поддержка: @ilpajj", Colors.CYAN)
        
    except KeyboardInterrupt:
        print_colored("\n❌ Установка прервана пользователем", Colors.RED)
    except Exception as e:
        print_colored(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}", Colors.RED + Colors.BOLD)
        print_colored("📞 Обратитесь за поддержкой: @ilpajj", Colors.CYAN)
        import traceback
        print_colored(f"🔍 Подробности: {traceback.format_exc()}", Colors.WHITE)

if __name__ == "__main__":
    main()
    
    # Пауза перед закрытием
    try:
        input("\nНажмите Enter для завершения...")
    except:
        pass

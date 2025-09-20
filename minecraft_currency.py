from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Tuple
if TYPE_CHECKING:
    from cardinal import Cardinal

import os
import json
import logging
import traceback
import threading
import subprocess
import time
from datetime import datetime, timedelta
import html
import re

from FunPayAPI.updater.events import NewMessageEvent, NewOrderEvent
from FunPayAPI import enums
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Информация о плагине
NAME = "MinecraftCurrency"
VERSION = "1.2"
DESCRIPTION = "Плагин для продажи валюты на Funtime"
CREDITS = "@ilpajj"
UUID = "12e01de2-de3a-447a-a49e-c0f7c143cf98"
SETTINGS_PAGE = False

# Глобальные переменные
RUNNING = False
IS_STARTED = False

# Хранение данных о заказах
orders_info = {}  # Информация о заказах для сопоставления
pending_orders = {}  # Ожидающие выдачи валюты

# Telegram бот и конфигурация
bot = None
config = {}
cardinal_instance = None

# Состояния для редактирования настроек
user_states = {}  # Хранит текущее состояние пользователя при редактировании

# Пути к файлам
LOG_DIR = os.path.join("storage", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "minecraft_currency.log")

CONFIG_PATH = os.path.join("storage", "cache", "minecraft_currency_config.json")
ORDERS_PATH = os.path.join("storage", "cache", "minecraft_currency_orders.json")
PENDING_ORDERS_PATH = os.path.join("storage", "cache", "pending_minecraft_orders.json")

os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(ORDERS_PATH), exist_ok=True)
os.makedirs(os.path.dirname(PENDING_ORDERS_PATH), exist_ok=True)

# Настройка логирования
logger = logging.getLogger("FPC.minecraft_currency")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

LOGGER_PREFIX = "[MINECRAFT CURRENCY]"

def load_config() -> Dict:
    """Загрузка конфигурации плагина"""
    logger.info("Загрузка конфигурации...")
    
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info("Конфигурация загружена.")
            return config
        else:
            logger.info("Файл конфигурации не найден, создание по умолчанию...")
            config = create_default_config()
            save_config(config)
            return config
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return create_default_config()

def create_default_config() -> Dict:
    """Создание конфигурации по умолчанию"""
    return {
        "auto_start": True,
        "notification_chat_id": None,
        "coins_per_unit": 1000000,
        "process_all_orders": True,
    "allowed_lot_ids": [],
    "check_lot_ids": False,
    # Список доверенных отправителей уведомлений об оплате (по умолчанию FunPay имеет id 0)
    "trusted_payment_senders": [0],
        "messages": {
            "after_payment": "💰 Спасибо за покупку!\n\n"
                           "✅Ваш заказ принят и будет конвертирован в валюту Minecraft.\n"
                           "➗Укажите ваш никнейм в Minecraft для выдачи валюты.\n\n"
                           "Пример: Steve",
            "processing": "⏳ Ваш заказ #{order_id} принят в обработку!\n"
                         "Сумма: {amount:,} монет\n"
                         "Никнейм: {username}\n\n"
                         "🤖 Бот сейчас подключится к серверу и переведет вам валюту автоматически!\n"
                         "Ожидайте 1-2 минуты...",
            "completed": "✅ Валюта успешно переведена!\n"
                        "Заказ #{order_id} выполнен.\n"
                        "Переведено {amount:,} монет игроку {username}\n\n"
                        "Спасибо за покупку! 🎮"
        },
        "require_username": True,
        "admin_notifications": True,
        "auto_give_currency": True,
        "minecraft_bot": {
            "enabled": True,
            "bot_username": "Bot",
            "server": "funtime.su",
            "password": "password",
            "anarchy": "an210",
            "test_username": "Test_user"
        }
    }

def save_config(cfg: Dict):
    """Сохранение конфигурации"""
    logger.info("Сохранение конфигурации...")
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    logger.info("Конфигурация сохранена.")

def load_orders_info() -> Dict:
    """Загрузка информации о заказах"""
    file_lock = threading.Lock()
    
    try:
        with file_lock:
            if os.path.exists(ORDERS_PATH):
                try:
                    with open(ORDERS_PATH, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        if not file_content.strip():
                            return {}
                        else:
                            return json.loads(file_content)
                except (json.JSONDecodeError, Exception) as e:
                    logger.error(f"Ошибка при чтении файла {ORDERS_PATH}: {e}")
                    return {}
            else:
                return {}
    except Exception as e:
        logger.error(f"Ошибка при доступе к файлу {ORDERS_PATH}: {e}")
        return {}

def save_orders_info(orders: Dict):
    """Сохранение информации о заказах"""
    file_lock = threading.Lock()
    
    try:
        with file_lock:
            with open(ORDERS_PATH, 'w', encoding='utf-8') as f:
                json.dump(orders, f, ensure_ascii=False, indent=4)
            logger.info("Информация о заказах сохранена.")
    except Exception as e:
        logger.error(f"Ошибка сохранения информации о заказах: {e}")

def load_pending_orders() -> Dict:
    """Загрузка ожидающих заказов"""
    if not os.path.exists(PENDING_ORDERS_PATH):
        return {}
    try:
        with open(PENDING_ORDERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_pending_orders(orders: Dict):
    """Сохранение ожидающих заказов"""
    with open(PENDING_ORDERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=4)

def get_lot_info_by_order(c: Cardinal, order_event) -> Tuple[int, str]:
    """Получение информации о лоте из события заказа"""
    try:
        # Загружаем конфигурацию для получения настройки монет за единицу
        cfg = load_config()
        coins_per_unit = cfg.get('coins_per_unit', 1000000)  # По умолчанию 1 миллион
        
        # Получаем информацию из события заказа
        if hasattr(order_event, 'order') and order_event.order:
            order = order_event.order
            
            # Получаем количество купленных единиц товара
            quantity = 1  # По умолчанию 1 единица
            
            # Способ 1: Из атрибута amount (количество товара)
            if hasattr(order, 'amount') and order.amount:
                quantity = int(order.amount)
                logger.info(f"Количество единиц из order.amount: {quantity}")
            
            # Способ 2: Из атрибута quantity
            elif hasattr(order, 'quantity') and order.quantity:
                quantity = int(order.quantity)
                logger.info(f"Количество единиц из order.quantity: {quantity}")
            
            # Способ 3: Из атрибута count
            elif hasattr(order, 'count') and order.count:
                quantity = int(order.count)
                logger.info(f"Количество единиц из order.count: {quantity}")
            
            else:
                logger.warning(f"Не удалось найти количество единиц товара, используется значение по умолчанию: {quantity}")
            
            # Рассчитываем общее количество монет
            total_coins = quantity * coins_per_unit
            
            # Получаем описание для отображения
            description = "Товар конвертирован в Minecraft валюту"
            if hasattr(order, 'description') and order.description:
                description = f"{order.description} → Minecraft валюта"
            elif hasattr(order, 'short_description') and order.short_description:
                description = f"{order.short_description} → Minecraft валюта"
            elif hasattr(order, 'lot_title') and order.lot_title:
                description = f"{order.lot_title} → Minecraft валюта"
            
            result_description = f"{description} ({total_coins:,} монет за {quantity} ед.)"
            
            logger.info(f"Рассчитано количество валюты: {quantity} ед. × {coins_per_unit:,} = {total_coins:,} монет")
            return total_coins, result_description
            
    except Exception as e:
        logger.error(f"Ошибка получения информации о лоте: {e}")
    
    # Возвращаем значения по умолчанию
    cfg = load_config()
    default_coins = cfg.get('coins_per_unit', 1000000)
    logger.warning("Не удалось получить информацию о лоте, используются значения по умолчанию")
    return default_coins, f"Товар конвертирован в Minecraft валюту ({default_coins:,} монет за 1 ед.)"

def is_allowed_lot(c: Cardinal, order_event) -> bool:
    """Проверка ID лотов принудительно отключена — разрешаем все заказы."""
    logger.info(f"{LOGGER_PREFIX} Проверка ID лотов принудительно отключена — обрабатываем все заказы")
    return True

def test_minecraft_bot_connection():
    """Тестирование подключения Minecraft бота"""
    try:
        # Используем упрощенный бот для тестирования
        bot_script_path = os.path.join(os.path.dirname(__file__), "minecraft_bot", "simple_bot.js")
        
        if not os.path.exists(bot_script_path):
            logger.error(f"{LOGGER_PREFIX} Файл упрощенного бота не найден: {bot_script_path}")
            return False
            
        # Тестовое подключение
        result = subprocess.run([
            "node", bot_script_path, "test"
        ], capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            try:
                # Ищем JSON в выводе
                stdout_lines = result.stdout.strip().split('\n')
                for line in reversed(stdout_lines):
                    if line.strip().startswith('{') and 'success' in line:
                        status_data = json.loads(line.strip())
                        logger.info(f"{LOGGER_PREFIX} Статус бота: {status_data}")
                        return status_data.get('success', False) and status_data.get('isConnected', False)
                        
                # Если JSON не найден, проверяем по тексту
                if 'success' in result.stdout.lower():
                    return True
                return False
            except json.JSONDecodeError:
                # Если не JSON, проверяем наличие ключевых слов
                if 'success' in result.stdout.lower():
                    return True
                return False
        else:
            logger.error(f"{LOGGER_PREFIX} Ошибка тестирования бота: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning(f"{LOGGER_PREFIX} Таймаут тестирования бота")
        return False
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Критическая ошибка тестирования бота: {e}")
        return False

def give_minecraft_currency(username, amount):
    """Автоматическая выдача валюты через упрощенный Minecraft бота"""
    # Подготовка путей и параметров
    logger.info(f"{LOGGER_PREFIX} Начинаем выдачу {amount:,} монет игроку {username}")
    bot_script_path = os.path.join(os.path.dirname(__file__), "minecraft_bot", "simple_bot.js")

    if not os.path.exists(bot_script_path):
        logger.error(f"{LOGGER_PREFIX} Файл упрощенного бота не найден: {bot_script_path}")
        return {'success': False, 'error': 'bot_script_not_found', 'message': 'Файл Minecraft бота не найден'}

    cfg = load_config()
    mb = cfg.get('minecraft_bot', {})
    bot_username = mb.get('bot_username', '')
    bot_password = mb.get('password', '')
    server = mb.get('server', 'funtime.su')
    port = mb.get('port', 25565)
    anarchy = mb.get('anarchy', 'an210')

    # Первый (полный) вызов: передаём все параметры
    command_args = ["node", bot_script_path, username, str(amount), bot_username, bot_password, server, str(port), anarchy]
    # Show full args (password unmasked) as requested
    logger.info(f"{LOGGER_PREFIX} Запуск Node-скрипта с args: {command_args}")

    try:
        result = subprocess.run(command_args, capture_output=True, text=True, timeout=90, encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        logger.error(f"{LOGGER_PREFIX} ❌ Таймаут запуска Node-скрипта (90 сек)")
        return {'success': False, 'error': 'timeout', 'message': 'Таймаут выполнения Node-скрипта'}
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка запуска Node-скрипта: {e}")
        result = None

    # Если результат отсутствует или код != 0, делаем резервный (простой) вызов
    if not result or (hasattr(result, 'returncode') and result.returncode != 0):
        logger.info(f"{LOGGER_PREFIX} Первый вызов неуспешен, пытаем fallback (node simple_bot.js <player> <amount>)")
        fallback_args = ["node", bot_script_path, username, str(amount)]
        try:
            fallback_result = subprocess.run(fallback_args, capture_output=True, text=True, timeout=90, encoding='utf-8', errors='replace')
            result = fallback_result
        except subprocess.TimeoutExpired:
            logger.error(f"{LOGGER_PREFIX} ❌ Таймаут резервного вызова Node-скрипта (90 сек)")
            return {'success': False, 'error': 'timeout', 'message': 'Таймаут выполнения Node-скрипта (fallback)'}
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка резервного вызова Node-скрипта: {e}")
            return {'success': False, 'error': 'bot_execution_failed', 'message': str(e)}

    # Лог вывода
    try:
        logger.info(f"{LOGGER_PREFIX} Результат выполнения бота (код: {result.returncode})")
        logger.info(f"{LOGGER_PREFIX} Stdout: {result.stdout}")
        if result.stderr:
            logger.info(f"{LOGGER_PREFIX} Stderr: {result.stderr}")
    except Exception:
        logger.warning(f"{LOGGER_PREFIX} Невозможно прочитать результат выполнения бота")

    # Обработка результата
    if result and getattr(result, 'returncode', 1) == 0:
        stdout_content = result.stdout or ""
        try:
            stdout_lines = stdout_content.strip().split('\n') if stdout_content else []
            json_line = None
            for line in reversed(stdout_lines):
                if line.strip().startswith('{') and ('success' in line or 'error' in line):
                    json_line = line.strip()
                    break

            if json_line:
                result_data = json.loads(json_line)
                logger.info(f"{LOGGER_PREFIX} Результат перевода: {result_data}")
                if result_data.get('success'):
                    return {'success': True, 'message': result_data.get('message', 'Успешно'), 'player': username, 'amount': amount}
                else:
                    return {'success': False, 'error': result_data.get('error', 'unknown'), 'message': result_data.get('message', 'Ошибка')}
            else:
                return {'success': True, 'message': 'Успешно выдано (без JSON)', 'player': username, 'amount': amount}
        except json.JSONDecodeError:
            return {'success': True, 'message': 'Успешно выдано (парсинг JSON не удался)', 'player': username, 'amount': amount}
    else:
        stderr_text = getattr(result, 'stderr', None) if result else 'Неизвестная ошибка'
        logger.error(f"{LOGGER_PREFIX} ❌ Ошибка выполнения бота: {stderr_text}")
        return {'success': False, 'error': 'bot_execution_failed', 'message': f'Ошибка выполнения бота: {stderr_text[:200] if stderr_text else "Неизвестная ошибка"}'}

def auto_complete_order_with_currency(order_id, admin_chat_id=None):
    """Автоматическое завершение заказа с выдачей валюты"""
    global pending_orders, orders_info
    
    # Находим заказ в ожидающих
    order_data = pending_orders.get(order_id)
    
    if not order_data:
        logger.error(f"{LOGGER_PREFIX} Заказ #{order_id} не найден в ожидающих для автозавершения")
        return False
    
    username = order_data.get('minecraft_username')
    amount = order_data.get('amount', 0)
    
    if not username:
        logger.error(f"{LOGGER_PREFIX} Не указан никнейм для заказа #{order_id}")
        return False
    
    logger.info(f"{LOGGER_PREFIX} Начинаем автозавершение заказа #{order_id} для {username} на сумму {amount:,}")
    
    # Пытаемся выдать валюту
    currency_result = give_minecraft_currency(username, amount)
    
    if currency_result['success']:
        # Валюта выдана успешно, завершаем заказ
        order_data['status'] = 'completed'
        order_data['completed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_data['completed_by'] = 'auto_bot'
        order_data['auto_completed'] = True
        
        # Удаляем из ожидающих
        del pending_orders[order_id]
        save_pending_orders(pending_orders)
        
        # Уведомляем покупателя
        cfg = load_config()
        completion_msg = cfg['messages']['completed'].format(
            order_id=order_id,
            amount=amount,
            username=username
        )
        completion_msg += f"\n\n🤖 Деньги переведены автоматически!"
        
        # Уведомляем только покупателя
        if order_id in orders_info:
            target_chat_id = orders_info[order_id]['chat_id']
            try:
                cardinal_instance.send_message(target_chat_id, completion_msg)
                logger.info(f"{LOGGER_PREFIX} Уведомление о завершении отправлено покупателю в чат {target_chat_id}")
            except Exception as e:
                logger.error(f"{LOGGER_PREFIX} Ошибка отправки уведомления покупателю: {e}")
        
        logger.info(f"{LOGGER_PREFIX} ✅ Заказ #{order_id} автоматически завершен - уведомлен только покупатель")
        return True
        
    else:
        # Валюта не выдана, логируем ошибку
        logger.error(f"{LOGGER_PREFIX} ❌ Не удалось автоматически выдать валюту для заказа #{order_id}: {currency_result['message']}")
        
        # Уведомляем администратора об ошибке
        if admin_chat_id and bot:
            error_msg = f"❌ ОШИБКА АВТОМАТИЧЕСКОЙ ВЫДАЧИ\n\n" \
                      f"Заказ: #{order_id}\n" \
                      f"Игрок: {username}\n" \
                      f"Сумма: {amount:,} монет\n" \
                      f"Ошибка: {currency_result['message']}\n\n" \
                      f"Требуется ручная выдача валюты!\n" \
                      f"✅ /complete_{order_id} - Выдал вручную\n" \
                      f"❌ /cancel_{order_id} - Отменить заказ"
            
            try:
                bot.send_message(admin_chat_id, error_msg)
                logger.info(f"{LOGGER_PREFIX} Уведомление об ошибке автовыдачи отправлено администратору")
            except Exception as e:
                logger.error(f"{LOGGER_PREFIX} Ошибка отправки уведомления об ошибке: {e}")
        
        return False

def minecraft_currency_handler(c: Cardinal, e, *args):
    """Основной обработчик событий"""
    global RUNNING, orders_info, pending_orders

    try:
        if not RUNNING:
            return

        my_id = c.account.id
        bot_ = c.telegram.bot

        if isinstance(e, NewMessageEvent):
            # Обработка сообщений от покупателей
            if e.message.author_id == my_id:
                logger.info(f"{LOGGER_PREFIX} Сообщение от самого себя, пропускаем")
                return

            msg_text = e.message.text.strip() if e.message.text else ""
            msg_author_id = e.message.author_id
            msg_chat_id = e.message.chat_id
            
            logger.info(f"{LOGGER_PREFIX} Получено сообщение от пользователя {msg_author_id} в чате {msg_chat_id}: '{msg_text}'")

            # Попытка распознать уведомление об оплате в чате (иногда FunPay шлёт текстовое сообщение вместо NewOrderEvent)
            try:
                pay_match = re.search(r"оплатил(?:.|) заказ #([A-Z0-9]+)", msg_text, re.IGNORECASE)
                if pay_match:
                    new_order_id = pay_match.group(1)
                    cfg_check = load_config()
                    trusted_senders = cfg_check.get('trusted_payment_senders', [0])
                    # Обрабатываем уведомления об оплате только от доверенных отправителей
                    if msg_author_id not in trusted_senders:
                        logger.warning(f"{LOGGER_PREFIX} Игнорируем уведомление об оплате #{new_order_id} от недоверенного отправителя {msg_author_id}")
                    else:
                        logger.info(f"{LOGGER_PREFIX} Обнаружено уведомление об оплате заказа #{new_order_id} в сообщении чата от доверенного отправителя")
                    # Если уже есть в ожидающих — пропускаем
                    if new_order_id in pending_orders:
                        logger.info(f"{LOGGER_PREFIX} Заказ #{new_order_id} уже есть в pending_orders, пропускаем создание")
                    else:
                        try:
                            # Пытаемся получить полную информацию о заказе
                            od_full = c.account.get_order(new_order_id)
                            buyer_chat_id = od_full.chat_id
                            buyer_id = od_full.buyer_id
                            buyer_username = getattr(od_full, 'buyer_username', None)

                            orders_info[new_order_id] = {
                                'buyer_id': buyer_id,
                                'chat_id': buyer_chat_id,
                                'buyer_username': buyer_username,
                                'order_id': new_order_id
                            }
                            save_orders_info(orders_info)

                            # Используем существующую функцию расчёта количества валюты
                            dummy = type('D', (), {})()
                            dummy.order = od_full
                            amount, lot_title = get_lot_info_by_order(c, dummy)

                            pending_orders[new_order_id] = {
                                'order_id': new_order_id,
                                'amount': amount,
                                'lot_title': lot_title,
                                'price': getattr(od_full, 'price', 0),
                                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'status': 'waiting_username',
                                'waiting_for_username': True,
                                'minecraft_username': None
                            }
                            save_pending_orders(pending_orders)
                            logger.info(f"{LOGGER_PREFIX} Заказ #{new_order_id} добавлен в ожидающие (по уведомлению в чате)")

                            # Отправляем сообщение покупателю с просьбой указать никнейм
                            cfg = load_config()
                            if buyer_chat_id:
                                try:
                                    c.send_message(buyer_chat_id, cfg['messages']['after_payment'])
                                    logger.info(f"{LOGGER_PREFIX} Отправлено сообщение покупателю в чат {buyer_chat_id} (по уведомлению)")
                                except Exception as sm_err:
                                    logger.error(f"{LOGGER_PREFIX} Ошибка отправки сообщения покупателю (по уведомлению): {sm_err}")
                        except Exception as ex_get:
                            logger.error(f"{LOGGER_PREFIX} Ошибка получения информации о заказе {new_order_id} при разборе уведомления: {ex_get}")
            except Exception as notify_ex:
                logger.error(f"{LOGGER_PREFIX} Ошибка при разборе уведомления об оплате: {notify_ex}")

            # Сначала проверяем, не ожидает ли пользователь подтверждения ника
            for order_id, order_data in pending_orders.items():
                order_info = orders_info.get(order_id)
                if order_info and order_info.get("buyer_id") == msg_author_id and order_data.get('waiting_for_confirmation', False):
                    # Обработка ответа пользователя на подтверждение
                    resp = msg_text.strip()
                    target_chat_id = order_info.get('chat_id')
                    if resp in ['+', 'плюс', '+1', 'yes', 'да']:
                        # Подтверждение — убедимся, что есть proposed_username
                        proposed = order_data.get('proposed_username')
                        if not proposed:
                            # Нету предложённого ника — просим ввести ещё раз
                            order_data['waiting_for_confirmation'] = False
                            order_data['waiting_for_username'] = True
                            save_pending_orders(pending_orders)
                            try:
                                c.send_message(target_chat_id, "❗ Не найден предложённый никнейм. Пожалуйста, отправьте никнейм ещё раз:")
                            except Exception:
                                pass
                            logger.warning(f"{LOGGER_PREFIX} Пользователь попытался подтвердить ник, но proposed_username отсутствует для заказа #{order_id}")
                            return

                        # Сохраняем подтверждённый ник в основное поле и меняем статус
                        order_data['minecraft_username'] = proposed
                        order_data['waiting_for_confirmation'] = False
                        order_data['status'] = 'ready_for_admin'
                        if 'proposed_username' in order_data:
                            del order_data['proposed_username']
                        save_pending_orders(pending_orders)

                        def give_thread():
                            try:
                                logger.info(f"{LOGGER_PREFIX} Пользователь подтвердил ник для заказа #{order_id}: {proposed}")
                                auto_complete_order_with_currency(order_id, target_chat_id)
                            except Exception as ex:
                                logger.error(f"{LOGGER_PREFIX} Ошибка при автоматической выдаче после подтверждения: {ex}")

                        threading.Thread(target=give_thread, daemon=True).start()
                        try:
                            c.send_message(target_chat_id, "✅ Подтверждение получено. Валюта будет выдана автоматически.")
                        except Exception:
                            pass
                        return

                    elif resp in ['-', 'минус', 'no', 'нет']:
                        # Отказ — попросить ник ещё раз
                        order_data['waiting_for_confirmation'] = False
                        order_data['waiting_for_username'] = True
                        if 'proposed_username' in order_data:
                            del order_data['proposed_username']
                        save_pending_orders(pending_orders)
                        try:
                            c.send_message(target_chat_id, "📥Введите новый никнейм.")
                        except Exception:
                            pass
                        return
                    else:
                        # Неизвестный ответ
                        try:
                            c.send_message(target_chat_id, "📩Пожалуйста, подтвердите выбор [+/-]")
                        except Exception:
                            pass
                        return

            # Ищем заказ по author_id
            found_order = None
            found_order_id = None
            
            # Сначала ищем в pending_orders заказы, ожидающие никнейм от этого пользователя
            for order_id, order_data in pending_orders.items():
                if order_data.get('waiting_for_username', False):
                    # Проверяем есть ли информация об этом заказе в orders_info
                    order_info = orders_info.get(order_id)
                    if order_info and order_info.get("buyer_id") == msg_author_id:
                        found_order = order_data
                        found_order_id = order_id
                        logger.info(f"{LOGGER_PREFIX} Найден заказ {order_id} для пользователя {msg_author_id}")
                        break
            
            if found_order:
                logger.info(f"{LOGGER_PREFIX} Обрабатываем никнейм от пользователя: '{msg_text}'")
                
                # Получили никнейм от пользователя — сохраняем как предложенный и просим подтвердить
                username = msg_text
                found_order['proposed_username'] = username
                found_order['waiting_for_username'] = False
                found_order['waiting_for_confirmation'] = True
                found_order['status'] = 'awaiting_confirmation'

                # Сохраняем обновленные данные
                save_pending_orders(pending_orders)

                # Отправляем сообщение с просьбой подтвердить
                cfg = load_config()
                target_chat_id = orders_info[found_order_id]['chat_id']
                try:
                    c.send_message(target_chat_id, f"❓Вы уверены в выдаче валюты на `{username}`? [+/-]")
                    logger.info(f"{LOGGER_PREFIX} Запрошено подтверждение ника от пользователя в чат {target_chat_id}")
                except Exception as send_error:
                    logger.error(f"{LOGGER_PREFIX} Ошибка отправки запроса на подтверждение пользователю: {send_error}")

                return
                
                logger.info(f"{LOGGER_PREFIX} Автовыдача: {auto_give_enabled}, Бот: {bot_enabled}")
                
                if auto_give_enabled and bot_enabled:
                    logger.info(f"{LOGGER_PREFIX} Автовыдача включена, запускаем автоматическое завершение...")
                    
                    # Запускаем автоматическое завершение в отдельном потоке
                    def auto_complete_thread():
                        time.sleep(2)  # Небольшая задержка для стабильности
                        result = auto_complete_order_with_currency(found_order['order_id'], cfg.get('notification_chat_id'))
                        logger.info(f"{LOGGER_PREFIX} Результат автозавершения заказа #{found_order['order_id']}: {result}")

                    threading.Thread(target=auto_complete_thread, daemon=True).start()
                else:
                    # Если автовыдача выключена - уведомляем администратора
                    if cfg.get('admin_notifications', True) and cfg.get('notification_chat_id'):
                        admin_msg = f"🆕 НОВЫЙ ЗАКАЗ НА ВЫДАЧУ ВАЛЮТЫ\n\n" \
                                  f"💰 Заказ: #{found_order['order_id']}\n" \
                                  f"👤 Никнейм: {username}\n" \
                                  f"💎 Сумма: {found_order['amount']:,} монет\n" \
                                  f"💵 Оплачено: {found_order.get('price', 0)} руб.\n\n" \
                                  f"Для выдачи валюты используйте команды:\n" \
                                  f"✅ /complete_{found_order['order_id']} - Выдал валюту\n" \
                                  f"🤖 /auto_{found_order['order_id']} - Автовыдача\n" \
                                  f"❌ /cancel_{found_order['order_id']} - Отменить заказ"
                        
                        try:
                            bot_.send_message(cfg['notification_chat_id'], admin_msg)
                            logger.info(f"{LOGGER_PREFIX} Отправлено уведомление администратору")
                        except Exception as admin_error:
                            logger.error(f"{LOGGER_PREFIX} Ошибка отправки уведомления администратору: {admin_error}")
                
                logger.info(f"{LOGGER_PREFIX} Получен никнейм {username} для заказа #{found_order['order_id']}")
            else:
                logger.info(f"{LOGGER_PREFIX} Нет ожидающего заказа для пользователя {msg_author_id}")
                # Логируем все доступные ожидающие заказы для отладки
                logger.info(f"{LOGGER_PREFIX} Доступные ожидающие заказы: {list(pending_orders.keys())}")
                logger.info(f"{LOGGER_PREFIX} Доступные orders_info: {list(orders_info.keys())}")
                
                # Детализированная отладка
                for order_id, order_data in pending_orders.items():
                    order_info = orders_info.get(order_id, {})
                    logger.info(f"{LOGGER_PREFIX} Заказ {order_id}: waiting={order_data.get('waiting_for_username', False)}, buyer_id={order_info.get('buyer_id')}")

        elif isinstance(e, NewOrderEvent):
            # Обработка новых заказов
            logger.info(f"{LOGGER_PREFIX} Получен новый заказ, проверяем...")
            
            try:
                if e.order.buyer_id == my_id:
                    logger.info(f"{LOGGER_PREFIX} Заказ от самого себя, пропускаем")
                    return

                order_id = e.order.id
                order_desc = e.order.description
                order_amount = e.order.amount
                order_price = e.order.price
                
                logger.info(f"{LOGGER_PREFIX} Новый заказ #{order_id}: {order_desc}, x{order_amount}")
                
                # Проверяем, разрешен ли лот для обработки
                if not is_allowed_lot(c, e):
                    logger.info(f"{LOGGER_PREFIX} Заказ #{order_id} пропущен - лот не в списке разрешенных")
                    return
                
                logger.info(f"{LOGGER_PREFIX} Заказ #{order_id} прошел проверку ID лота - начинаем обработку")
                
                # Получаем полную информацию о заказе
                try:
                    od_full = c.account.get_order(order_id)
                    buyer_chat_id = od_full.chat_id
                    buyer_id = od_full.buyer_id
                    buyer_username = od_full.buyer_username
                    
                    logger.info(f"{LOGGER_PREFIX} Полная информация: buyer_id={buyer_id}, chat_id={buyer_chat_id}, username={buyer_username}")

                    # Сохраняем информацию о заказе для связи с чатом
                    orders_info[order_id] = {
                        "buyer_id": buyer_id,
                        "chat_id": buyer_chat_id,
                        "buyer_username": buyer_username,
                        "order_id": order_id
                    }
                    save_orders_info(orders_info)
                    
                except Exception as full_order_error:
                    logger.error(f"{LOGGER_PREFIX} Ошибка получения полной информации о заказе: {full_order_error}")
                    buyer_chat_id = e.order.chat_id if hasattr(e.order, 'chat_id') else None
                    buyer_id = e.order.buyer_id
                    
                    orders_info[order_id] = {
                        "buyer_id": buyer_id,
                        "chat_id": buyer_chat_id,
                        "order_id": order_id
                    }
                    save_orders_info(orders_info)
                
                # Получаем информацию о количестве валюты
                amount, lot_title = get_lot_info_by_order(c, e)
                logger.info(f"{LOGGER_PREFIX} Определены параметры заказа: {amount:,} монет, '{lot_title}'")
                
                # Создаем запись об ожидающем заказе
                pending_orders[order_id] = {
                    'order_id': order_id,
                    'amount': amount,
                    'lot_title': lot_title,
                    'price': order_price,
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'waiting_username',
                    'waiting_for_username': True,
                    'minecraft_username': None
                }

                save_pending_orders(pending_orders)
                logger.info(f"{LOGGER_PREFIX} Заказ #{order_id} добавлен в ожидающие")
                
                # Отправляем сообщение покупателю с просьбой указать никнейм
                cfg = load_config()
                if buyer_chat_id:
                    try:
                        c.send_message(buyer_chat_id, cfg['messages']['after_payment'])
                        logger.info(f"{LOGGER_PREFIX} Отправлено сообщение покупателю в чат {buyer_chat_id}")
                    except Exception as msg_error:
                        logger.error(f"{LOGGER_PREFIX} Ошибка отправки сообщения покупателю: {msg_error}")
                
            except Exception as handler_error:
                logger.error(f"{LOGGER_PREFIX} Ошибка в обработчике новых заказов: {handler_error}")
                logger.error(f"{LOGGER_PREFIX} Трейсбек: {traceback.format_exc()}")

    except Exception as main_error:
        logger.error(f"{LOGGER_PREFIX} Глобальная ошибка в обработчике событий: {main_error}")
        logger.error(f"{LOGGER_PREFIX} Глобальный трейсбек: {traceback.format_exc()}")

def complete_order(message: types.Message, order_id: str):
    """Завершение заказа администратором"""
    global pending_orders, orders_info
    
    # Находим заказ в ожидающих
    order_data = pending_orders.get(order_id)
    
    if not order_data:
        bot.send_message(message.chat.id, f"❌ Заказ #{order_id} не найден в ожидающих.")
        return
    
    # Отмечаем заказ как выполненный
    order_data['status'] = 'completed'
    order_data['completed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_data['completed_by'] = message.from_user.id
    
    # Удаляем из ожидающих
    del pending_orders[order_id]
    save_pending_orders(pending_orders)
    
    # Уведомляем покупателя
    cfg = load_config()
    completion_msg = cfg['messages']['completed'].format(
        order_id=order_id,
        amount=order_data['amount'],
        username=order_data['minecraft_username']
    )
    
    # Уведомляем только покупателя
    if order_id in orders_info:
        target_chat_id = orders_info[order_id]['chat_id']
        try:
            cardinal_instance.send_message(target_chat_id, completion_msg)
            logger.info(f"{LOGGER_PREFIX} Уведомление о завершении отправлено покупателю в чат {target_chat_id}")
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка отправки уведомления покупателю: {e}")
    
    # Краткое подтверждение администратору
    admin_msg = f"✅ Заказ #{order_id} отмечен как выполненный"
    
    bot.send_message(message.chat.id, admin_msg)
    
    logger.info(f"{LOGGER_PREFIX} Заказ #{order_id} завершен администратором - уведомлен только покупатель")

def cancel_order(message: types.Message, order_id: str):
    """Отмена заказа администратором"""
    global pending_orders, orders_info
    
    # Находим заказ в ожидающих
    order_data = pending_orders.get(order_id)
    
    if not order_data:
        bot.send_message(message.chat.id, f"❌ Заказ #{order_id} не найден в ожидающих.")
        return
    
    # Отмечаем заказ как отмененный
    order_data['status'] = 'cancelled'
    order_data['cancelled_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_data['cancelled_by'] = message.from_user.id
    
    # Удаляем из ожидающих
    del pending_orders[order_id]
    save_pending_orders(pending_orders)
    
    # Уведомляем покупателя
    cancel_msg = f"❌ К сожалению, ваш заказ #{order_id} был отменен.\n" \
                f"Если у вас есть вопросы, обратитесь к администратору."
    
    # Используем chat_id из orders_info для отправки сообщения
    if order_id in orders_info:
        target_chat_id = orders_info[order_id]['chat_id']
        try:
            cardinal_instance.send_message(target_chat_id, cancel_msg)
            logger.info(f"{LOGGER_PREFIX} Уведомление об отмене отправлено в чат {target_chat_id}")
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка отправки уведомления об отмене: {e}")
    
    # Уведомляем администратора
    admin_msg = f"❌ Заказ #{order_id} отменен."
    bot.send_message(message.chat.id, admin_msg)
    
    logger.info(f"{LOGGER_PREFIX} Заказ #{order_id} отменен администратором")

def show_pending_orders(message: types.Message):
    """Показать все ожидающие заказы"""
    if not pending_orders:
        bot.send_message(message.chat.id, "📋 Нет ожидающих заказов.")
        return
    
    msg = "📋 **ОЖИДАЮЩИЕ ЗАКАЗЫ**\n\n"
    
    for order_id, data in pending_orders.items():
        status_emoji = "⏳" if data['status'] == 'waiting_username' else "✅"
        username = data.get('minecraft_username', 'не указан')
        
        msg += f"{status_emoji} Заказ #{data['order_id']}\n" \
               f"💰 Сумма: {data['amount']:,} монет\n" \
               f"👤 Никнейм: {username}\n" \
               f"📅 Дата: {data['date']}\n" \
               f"💵 Оплачено: {data.get('price', 0)} руб.\n"
        
        if data['status'] == 'ready_for_admin':
            msg += f"✅ /complete_{data['order_id']} | 🤖 /auto_{data['order_id']} | ❌ /cancel_{data['order_id']}\n"
        
        msg += "\n"
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

def clear_all_orders(message: types.Message):
    """Очистка всех заказов (ожидающих и информации)"""
    global pending_orders, orders_info
    
    pending_count = len(pending_orders)
    info_count = len(orders_info)
    
    # Очищаем данные
    pending_orders.clear()
    orders_info.clear()
    
    # Сохраняем изменения
    save_pending_orders(pending_orders)
    save_orders_info(orders_info)
    
    msg = f"🗑️ **ОЧИСТКА ЗАВЕРШЕНА**\n\n" \
          f"• Удалено ожидающих заказов: {pending_count}\n" \
          f"• Удалено записей информации: {info_count}\n" \
          f"• Все файлы данных очищены\n\n" \
          f"✅ Система готова к работе с новыми заказами"
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')
    logger.info(f"{LOGGER_PREFIX} Администратор очистил все заказы: pending={pending_count}, info={info_count}")

def minecraft_currency_settings(message: types.Message):
    """Показать интерактивное меню настроек плагина"""
    cfg = load_config()
    
    # Создаем главное меню с категориями
    markup = InlineKeyboardMarkup(row_width=1)
    
    # Основные категории
    markup.add(
        InlineKeyboardButton("🤖 НАСТРОЙКИ БОТА", callback_data="show_bot_category")
    )
    markup.add(
        InlineKeyboardButton("💬 НАСТРОЙКИ СООБЩЕНИЙ", callback_data="show_messages_category")
    )
    markup.add(
        InlineKeyboardButton("📋 УПРАВЛЕНИЕ ЗАКАЗАМИ", callback_data="show_orders_category")
    )
    # Управление лотами удалено по настройке — кнопка скрыта
    markup.add(
        InlineKeyboardButton("🔧 ОБЩИЕ НАСТРОЙКИ", callback_data="show_general_category")
    )
    markup.add(
        InlineKeyboardButton("🔄 Обновить главное меню", callback_data="refresh_settings")
    )
    
    # Основная информация
    notif_chat = cfg.get('notification_chat_id', 'Не задан')
    status_text = "✅ ЗАПУЩЕН" if RUNNING else "❌ ОСТАНОВЛЕН"
    auto_give = cfg.get('auto_give_currency', False)
    bot_enabled = cfg.get('minecraft_bot', {}).get('enabled', False)
    bot_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
    bot_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
    test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
    # Показываем пароль явно (по требованию)
    masked_password = bot_password if bot_password != 'не указан' else 'не указан'
    coins_per_unit = cfg.get('coins_per_unit', 1000000)
    
    # Подсчет размеров файлов заказов
    orders_file_size = "н/д"
    pending_file_size = "н/д"
    try:
        if os.path.exists(ORDERS_PATH):
            orders_file_size = f"{os.path.getsize(ORDERS_PATH)} байт"
        if os.path.exists(PENDING_ORDERS_PATH):
            pending_file_size = f"{os.path.getsize(PENDING_ORDERS_PATH)} байт"
    except:
        pass
    
    msg = f"""🎮 **MINECRAFT CURRENCY PLUGIN v{VERSION}**

📊 **СТАТУС:** {status_text}

🤖 **MINECRAFT БОТ:**
• Автовыдача валюты: {'✅ ВКЛЮЧЕНА' if auto_give else '❌ ВЫКЛЮЧЕНА'}
• Никнейм бота: `{bot_username}`
• Пароль бота: `{masked_password}`
• Бот включен: {'✅' if bot_enabled else '❌'}
• Сервер: {cfg.get('minecraft_bot', {}).get('server', 'funtime.su')}
"""
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=markup)

def show_full_settings(message: types.Message):
    """Показать полные настройки плагина"""
    cfg = load_config()
    
    notif_chat = cfg.get('notification_chat_id', 'Не задан')
    auto_start = cfg.get('auto_start', True)
    admin_notifications = cfg.get('admin_notifications', True)
    require_username = cfg.get('require_username', True)
    coins_per_unit = cfg.get('coins_per_unit', 1000000)
    process_all_orders = cfg.get('process_all_orders', True)
    
    status_text = "✅ ЗАПУЩЕН" if RUNNING else "❌ ОСТАНОВЛЕН"
    auto_give = cfg.get('auto_give_currency', False)
    bot_enabled = cfg.get('minecraft_bot', {}).get('enabled', False)
    bot_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
    bot_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
    # Показываем пароль явно (по требованию)
    masked_password = bot_password if bot_password != 'не указан' else 'не указан'
    
    msg = f"""🎮 **ПОЛНЫЕ НАСТРОЙКИ ПЛАГИНА v{VERSION}**

📊 **СТАТУС:** {status_text}

⚙️ **ОСНОВНЫЕ НАСТРОЙКИ:**
• Автозапуск: {'✅' if auto_start else '❌'}
• Обрабатывать ВСЕ заказы: {'✅ ДА' if process_all_orders else '❌ Только Minecraft'}
• Уведомления админу: {'✅' if admin_notifications else '❌'}
• Требовать никнейм: {'✅' if require_username else '❌'}
• Монет за 1 единицу: {coins_per_unit:,}
• Chat ID уведомлений: `{notif_chat}`

🤖 **MINECRAFT БОТ:**
• Автовыдача валюты: {'✅ ВКЛЮЧЕНА (все заказы автоматически)' if auto_give else '❌ ВЫКЛЮЧЕНА (ручная выдача)'}
• Бот включен: {'✅' if bot_enabled else '❌'}
• Никнейм бота: **{bot_username}**
• Сервер: {cfg.get('minecraft_bot', {}).get('server', 'funtime.su')}

📝 **ОПИСАНИЕ:**
{DESCRIPTION}

💡 **ЛОГИКА РАСЧЕТА:**
1 единица товара = {coins_per_unit:,} монет
Если покупатель покупает 3 шт, получит {coins_per_unit * 3:,} монет

🎯 **РЕЖИМ РАБОТЫ:**
{'🟢 ОБРАБАТЫВАЮТСЯ ВСЕ ЗАКАЗЫ - любой товар будет конвертирован в Minecraft валюту' if process_all_orders else '🔵 Только заказы Minecraft валюты'}

{'🤖 АВТОВЫДАЧА: При получении никнейма бот автоматически переводит валюту' if auto_give else '👨‍💼 РУЧНАЯ ВЫДАЧА: Требуется подтверждение администратора для каждого заказа'}

📋 **ДОСТУПНЫЕ КОМАНДЫ:**
• `/mc_start` - Запустить плагин
• `/mc_stop` - Остановить плагин
• `/mc_pending` - Показать ожидающие заказы
• `/mc_clear` - Очистить все заказы (ожидающие + данные)
• `/mc_toggle_auto` - Переключить автовыдачу валюты (ВКЛ/ВЫКЛ)
• `/mc_process_all` - Обработать все ожидающие заказы ботом
• `/mc_test_pay` - Тестовый перевод валюты (для отладки)
• `/mc_force_auto` - Принудительно запустить автовыдачу для всех готовых заказов
• `/mc_settings` - Интерактивное меню настроек
• `/mc_test_bot` - Тестировать Minecraft бота
• `/complete_[ID]` - Выдал валюту (заказ ID)
• `/auto_[ID]` - Автоматическая выдача валюты
• `/cancel_[ID]` - Отменить заказ (заказ ID)

💡 **Ожидающих заказов:** {len(pending_orders)}

🔧 **Заказов в памяти:** {len(orders_info)}

📝 **ТЕКУЩИЕ СООБЩЕНИЯ:**

🔸 **После оплаты:**
```
{cfg['messages']['after_payment']}
```

🔸 **При обработке:**
```
{cfg['messages']['processing']}
```

🔸 **После завершения:**
```
{cfg['messages']['completed']}
```

🛠️ **ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА:**
1. Установите ваш chat_id в настройке notification_chat_id
2. Укажите никнейм вашего Minecraft бота в bot_username
3. Убедитесь, что у бота есть средства для перевода
4. Проверьте подключение командой /mc_test_bot
"""
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

def show_bot_category(chat_id, message_id=None):
    """Показать категорию настроек бота"""
    try:
        cfg = load_config()
        
        # Создаем меню категории бота
        markup = InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            InlineKeyboardButton("🔧 Изменить никнейм", callback_data="change_bot_username"),
            InlineKeyboardButton("🔑 Изменить пароль", callback_data="change_bot_password")
        )
        markup.add(
            InlineKeyboardButton("🎯 Тестовый никнейм", callback_data="change_test_username")
        )
        # Кнопка для смены IP/хоста сервера
        markup.add(
            InlineKeyboardButton("🌐 Изменить IP/хост сервера", callback_data="change_server_ip")
        )
        markup.add(
            InlineKeyboardButton("👁️ Показать пароль", callback_data="show_password")
        )
        markup.add(
            InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main")
        )
        
        # Информация о настройках бота
        bot_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
        bot_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
        test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
        # Показываем пароль явно (по требованию)
        masked_password = bot_password if bot_password != 'не указан' else 'не указан'
        bot_enabled = cfg.get('minecraft_bot', {}).get('enabled', False)
        server = cfg.get('minecraft_bot', {}).get('server', 'funtime.su')
        
        msg = f"""🤖 **НАСТРОЙКИ MINECRAFT БОТА**

🎮 **ТЕКУЩИЕ НАСТРОЙКИ:**
• Никнейм бота: `{bot_username}`
• Пароль бота: `{masked_password}`
• Тестовый никнейм: `{test_username}`
• Бот включен: {'✅' if bot_enabled else '❌'}
• Сервер: {server}

📋 **ДОСТУПНЫЕ ДЕЙСТВИЯ:**
• Изменить никнейм бота
• Изменить пароль для входа
• Изменить тестовый никнейм
• Посмотреть текущий пароль

💡 **Информация:**
Эти настройки используются для автоматического подключения бота к серверу Minecraft и выдачи валюты.
Тестовый никнейм используется для команды `/mc_test_pay` - на него будет переведено 1000 монет для проверки работы бота.
"""
        
        if message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка в show_bot_category: {e}")
        error_msg = "❌ **ОШИБКА ЗАГРУЗКИ НАСТРОЕК БОТА**\n\n" \
                   f"Произошла ошибка: {e}\n\n" \
                   "Попробуйте обновить меню или перезапустить плагин."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main"))
        
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, error_msg, parse_mode='Markdown', reply_markup=markup)

def show_messages_category(chat_id, message_id=None):
    """Показать категорию настроек сообщений"""
    try:
        cfg = load_config()
        
        # Проверяем наличие секции messages
        if 'messages' not in cfg:
            cfg['messages'] = {
                'after_payment': 'Текст после оплаты не настроен',
                'processing': 'Текст обработки не настроен',
                'completed': 'Текст завершения не настроен'
            }
            save_config(cfg)
        
        # Создаем меню категории сообщений
        markup = InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            InlineKeyboardButton("📝 После оплаты", callback_data="change_after_payment"),
            InlineKeyboardButton("⏳ При обработке", callback_data="change_processing")
        )
        markup.add(
            InlineKeyboardButton("✅ После завершения", callback_data="change_completed")
        )
        markup.add(
            InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main")
        )
        
        # Безопасное получение длин текстов
        after_payment_len = len(cfg.get('messages', {}).get('after_payment', ''))
        processing_len = len(cfg.get('messages', {}).get('processing', ''))
        completed_len = len(cfg.get('messages', {}).get('completed', ''))
        
        msg = f"""💬 **НАСТРОЙКИ СООБЩЕНИЙ**

📝 **ТЕКУЩИЕ СООБЩЕНИЯ:**
🔹 После оплаты: {after_payment_len} символов
🔹 При обработке: {processing_len} символов  
🔹 После завершения: {completed_len} символов

📋 **ДОСТУПНЫЕ ДЕЙСТВИЯ:**
• Изменить текст после оплаты заказа
• Изменить текст при обработке заказа
• Изменить текст после завершения заказа

💡 **Информация:**
Эти тексты отправляются покупателям на разных этапах обработки заказа. Вы можете использовать переменные `{"{order_id}"}`, `{"{amount}"}`, `{"{username}"}`в текстах.
"""
        
        if message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка в show_messages_category: {e}")
        error_msg = "❌ **ОШИБКА ЗАГРУЗКИ НАСТРОЕК СООБЩЕНИЙ**\n\n" \
                   f"Произошла ошибка: {e}\n\n" \
                   "Попробуйте обновить меню или перезапустить плагин."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main"))
        
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, error_msg, parse_mode='Markdown', reply_markup=markup)

def show_orders_category(chat_id, message_id=None):
    """Показать категорию управления заказами"""
    try:
        # Создаем меню категории заказов
        markup = InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            InlineKeyboardButton("🗑️ Очистить файлы", callback_data="clear_order_files"),
            InlineKeyboardButton("📤 Выгрузить файлы", callback_data="export_order_files")
        )
        markup.add(
            InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main")
        )
        
        # Подсчет информации о файлах
        orders_file_size = "н/д"
        pending_file_size = "н/д"
        config_file_size = "н/д"
        
        try:
            if os.path.exists(ORDERS_PATH):
                orders_file_size = f"{os.path.getsize(ORDERS_PATH)} байт"
            if os.path.exists(PENDING_ORDERS_PATH):
                pending_file_size = f"{os.path.getsize(PENDING_ORDERS_PATH)} байт"
            if os.path.exists(CONFIG_PATH):
                config_file_size = f"{os.path.getsize(CONFIG_PATH)} байт"
        except:
            pass
        
        msg = f"""📋 **УПРАВЛЕНИЕ ЗАКАЗАМИ**

💾 **СОСТОЯНИЕ ФАЙЛОВ:**
• Заказы в памяти: {len(orders_info)}
• Ожидающих заказов: {len(pending_orders)}
• Размер файла заказов: {orders_file_size}
• Размер файла ожидающих: {pending_file_size}
• Размер конфигурации: {config_file_size}

📋 **ДОСТУПНЫЕ ДЕЙСТВИЯ:**
• Очистить все файлы заказов
• Выгрузить файлы для резервного копирования

⚠️ **ВНИМАНИЕ:**
Очистка файлов удалит ВСЕ данные о заказах безвозвратно!
Рекомендуется сначала создать резервную копию.
"""
        
        if message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка в show_orders_category: {e}")
        error_msg = "❌ **ОШИБКА ЗАГРУЗКИ УПРАВЛЕНИЯ ЗАКАЗАМИ**\n\n" \
                   f"Произошла ошибка: {e}\n\n" \
                   "Попробуйте обновить меню или перезапустить плагин."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main"))
        
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, error_msg, parse_mode='Markdown', reply_markup=markup)

def show_lots_category(chat_id, message_id=None):
    # Заглушка: управление лотами удалено
    try:
        msg = "🎯 Управление лотами отключено в этой сборке плагина."
        if message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка в show_lots_category: {e}")


def show_general_category(chat_id, message_id=None):
    """Показать категорию общих настроек"""
    try:
        cfg = load_config()
        
        # Создаем меню общих настроек
        markup = InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            InlineKeyboardButton("📊 Показать все настройки", callback_data="show_all_settings")
        )
        markup.add(
            InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main")
        )
        
        # Основная информация о плагине
        status_text = "✅ ЗАПУЩЕН" if RUNNING else "❌ ОСТАНОВЛЕН"
        auto_give = cfg.get('auto_give_currency', False)
        coins_per_unit = cfg.get('coins_per_unit', 1000000)
        process_all_orders = cfg.get('process_all_orders', True)
        notif_chat = cfg.get('notification_chat_id', 'Не задан')
        
        msg = f"""🔧 **ОБЩИЕ НАСТРОЙКИ**

📊 **СТАТУС ПЛАГИНА:** {status_text}

⚙️ **ОСНОВНЫЕ ПАРАМЕТРЫ:**
• Автовыдача валюты: {'✅ ВКЛЮЧЕНА' if auto_give else '❌ ВЫКЛЮЧЕНА'}
• Монет за 1 единицу: {coins_per_unit:,}
• Обработка всех заказов: {'✅ ДА' if process_all_orders else '❌ НЕТ'}
• Chat ID уведомлений: `{notif_chat}`

📋 **ДОСТУПНЫЕ ДЕЙСТВИЯ:**
• Посмотреть полные настройки системы

💡 **Информация:**
Здесь отображается общая информация о состоянии плагина и основных параметрах работы.

📝 **КОМАНДЫ УПРАВЛЕНИЯ:**
• `/mc_start` - Запустить плагин
• `/mc_stop` - Остановить плагин
• `/mc_toggle_auto` - Переключить автовыдачу
• `/mc_pending` - Показать ожидающие заказы
"""
        
        if message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} Ошибка в show_general_category: {e}")
        error_msg = "❌ **ОШИБКА ЗАГРУЗКИ ОБЩИХ НАСТРОЕК**\n\n" \
                   f"Произошла ошибка: {e}\n\n" \
                   "Попробуйте обновить меню или перезапустить плагин."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад к главному меню", callback_data="back_to_main"))
        
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, error_msg, parse_mode='Markdown', reply_markup=markup)

def start_minecraft_plugin(message: types.Message):
    """Запуск плагина"""
    global RUNNING, IS_STARTED, orders_info, pending_orders
    
    if RUNNING:
        bot.send_message(message.chat.id, "✅ Плагин уже запущен.")
        return
    
    RUNNING = True
    IS_STARTED = True
    
    # Загружаем данные при запуске
    orders_info = load_orders_info()
    pending_orders = load_pending_orders()
    
    logger.info(f"{LOGGER_PREFIX} Загружено {len(orders_info)} заказов в память")
    logger.info(f"{LOGGER_PREFIX} Загружено {len(pending_orders)} ожидающих заказов")
    logger.info(f"{LOGGER_PREFIX} Создатель @ilpajj, funpay - https://funpay.com/users/5327459/")
    
    bot.send_message(message.chat.id, "✅ Minecraft Currency плагин запущен.")
    logger.info(f"{LOGGER_PREFIX} Плагин запущен")

def stop_minecraft_plugin(message: types.Message):
    """Остановка плагина"""
    global RUNNING
    
    if not RUNNING:
        bot.send_message(message.chat.id, "❌ Плагин уже остановлен.")
        return
    
    RUNNING = False
    bot.send_message(message.chat.id, "❌ Minecraft Currency плагин остановлен.")
    logger.info(f"{LOGGER_PREFIX} Плагин остановлен")

def toggle_auto_give(message: types.Message):
    """Переключение автоматической выдачи валюты"""
    cfg = load_config()
    current_state = cfg.get('auto_give_currency', False)
    new_state = not current_state
    
    # Обновляем настройку
    cfg['auto_give_currency'] = new_state
    save_config(cfg)
    
    state_text = "✅ ВКЛЮЧЕНА" if new_state else "❌ ОТКЛЮЧЕНА"
    bot.send_message(message.chat.id, f"🤖 Автоматическая выдача валюты: {state_text}")
    
    logger.info(f"{LOGGER_PREFIX} Автовыдача валюты {'включена' if new_state else 'отключена'} администратором")
    
    # Если включили автовыдачу - обрабатываем все ожидающие заказы
    if new_state:
        process_pending_orders_auto(message)

def process_pending_orders_auto(message: types.Message):
    """Автоматическая обработка всех ожидающих заказов"""
    global pending_orders
    
    # Находим заказы готовые к выдаче (имеют никнейм)
    ready_orders = []
    for order_id, order_data in pending_orders.items():
        if (order_data.get('status') == 'ready_for_admin' and 
            order_data.get('minecraft_username') and
            not order_data.get('minecraft_username') == 'не указан'):
            ready_orders.append((order_id, order_data))
    
    if not ready_orders:
        bot.send_message(message.chat.id, "📋 Нет заказов готовых к автоматической выдаче.")
        return
    
    bot.send_message(message.chat.id, f"🤖 Найдено {len(ready_orders)} заказов для автоматической выдачи. Начинаем обработку...")
    
    def process_all_orders():
        processed = 0
        successful = 0
        failed = 0
        
        for order_id, order_data in ready_orders:
            try:
                logger.info(f"{LOGGER_PREFIX} Автообработка заказа #{order_id}")
                result = auto_complete_order_with_currency(order_id, message.chat.id)
                processed += 1
                
                if result:
                    successful += 1
                    logger.info(f"{LOGGER_PREFIX} ✅ Заказ #{order_id} успешно обработан автоматически")
                else:
                    failed += 1
                    logger.error(f"{LOGGER_PREFIX} ❌ Ошибка автообработки заказа #{order_id}")
                
                # Небольшая пауза между заказами
                time.sleep(3)
                
            except Exception as e:
                failed += 1
                logger.error(f"{LOGGER_PREFIX} Критическая ошибка обработки заказа #{order_id}: {e}")
        
        # Отчет о результатах
        report_msg = f"📊 **АВТООБРАБОТКА ЗАВЕРШЕНА**\n\n" \
                    f"• Обработано заказов: {processed}\n" \
                    f"• Успешно: {successful} ✅\n" \
                    f"• Ошибок: {failed} ❌\n\n"
        
        if successful > 0:
            report_msg += f"💰 Валюта выдана автоматически для {successful} заказов!"
        
        if failed > 0:
            report_msg += f"\n⚠️ {failed} заказов требуют ручной обработки."
        
        try:
            bot.send_message(message.chat.id, report_msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка отправки отчета: {e}")
    
    # Запускаем обработку в отдельном потоке
    threading.Thread(target=process_all_orders, daemon=True).start()

def handle_settings_callback(call):
    """Обработка нажатий кнопок в меню настроек"""
    global user_states
    
    user_id = call.from_user.id
    
    # Обработка новых категорий настроек
    if call.data == "show_bot_category":
        show_bot_category(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "show_messages_category":
        show_messages_category(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "show_orders_category":
        show_orders_category(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "show_general_category":
        show_general_category(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
        
    # Управление лотами отключено — пропускаем
        
    elif call.data == "back_to_main":
        # Создаем главное меню настроек
        try:
            cfg = load_config()
            
            # Создаем главное меню с категориями
            markup = InlineKeyboardMarkup(row_width=1)
            
            # Основные категории
            markup.add(
                InlineKeyboardButton("🤖 НАСТРОЙКИ БОТА", callback_data="show_bot_category")
            )
            markup.add(
                InlineKeyboardButton("💬 НАСТРОЙКИ СООБЩЕНИЙ", callback_data="show_messages_category")
            )
            markup.add(
                InlineKeyboardButton("📋 УПРАВЛЕНИЕ ЗАКАЗАМИ", callback_data="show_orders_category")
            )
            # Кнопка управления лотами удалена
            markup.add(
                InlineKeyboardButton("🔧 ОБЩИЕ НАСТРОЙКИ", callback_data="show_general_category")
            )
            markup.add(
                InlineKeyboardButton("🔄 Обновить главное меню", callback_data="refresh_settings")
            )
            
            # Основная информация
            notif_chat = cfg.get('notification_chat_id', 'Не задан')
            status_text = "✅ ЗАПУЩЕН" if RUNNING else "❌ ОСТАНОВЛЕН"
            auto_give = cfg.get('auto_give_currency', False)
            bot_enabled = cfg.get('minecraft_bot', {}).get('enabled', False)
            bot_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
            bot_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
            test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
            # Показываем пароль явно (по требованию)
            masked_password = bot_password if bot_password != 'не указан' else 'не указан'
            coins_per_unit = cfg.get('coins_per_unit', 1000000)
            
            # Подсчет размеров файлов заказов
            orders_file_size = "н/д"
            pending_file_size = "н/д"
            try:
                if os.path.exists(ORDERS_PATH):
                    orders_file_size = f"{os.path.getsize(ORDERS_PATH)} байт"
                if os.path.exists(PENDING_ORDERS_PATH):
                    pending_file_size = f"{os.path.getsize(PENDING_ORDERS_PATH)} байт"
            except:
                pass
            
            msg = f"""🎮 **MINECRAFT CURRENCY PLUGIN v{VERSION}**

📊 **СТАТУС:** {status_text}

🤖 **MINECRAFT БОТ:**
• Автовыдача валюты: {'✅ ВКЛЮЧЕНА' if auto_give else '❌ ВЫКЛЮЧЕНА'}
• Никнейм бота: `{bot_username}`
• Пароль бота: `{masked_password}`
• Бот включен: {'✅' if bot_enabled else '❌'}
• Сервер: {cfg.get('minecraft_bot', {}).get('server', 'funtime.su')}
"""
            
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)
            
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка в back_to_main: {e}")
            bot.edit_message_text(f"❌ **ОШИБКА ЗАГРУЗКИ ГЛАВНОГО МЕНЮ**\n\nПроизошла ошибка: {e}", 
                                call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "show_password":
        # Показать реальный пароль
        cfg = load_config()
        current_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
        bot.edit_message_text(
            "👁️ **ОТОБРАЖЕНИЕ ПАРОЛЯ БОТА**\n\n"
            f"**Текущий пароль:** `{current_password}`\n\n"
            "🔒 **Безопасность:**\n"
            "• Не делитесь этим паролем с посторонними\n"
            "• Используйте кнопку '🔄 Обновить меню' чтобы скрыть пароль\n\n"
            "⚠️ Это сообщение содержит конфиденциальную информацию!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
    elif call.data == "set_server_spooky":
        cfg = load_config()
        cfg.setdefault('minecraft_bot', {})['server'] = 'spookytime.net'
        save_config(cfg)
        try:
            bot.edit_message_text("✅ Сервер изменён на `spookytime.net`. Node helper читает конфиг при старте.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "clear_order_files":
        # Очистка файлов заказов
        bot.edit_message_text(
            "🗑️ **ОЧИСТКА ФАЙЛОВ ЗАКАЗОВ**\n\n"
            "⚠️ **ВНИМАНИЕ!** Это действие удалит все данные о заказах:\n"
            "• Информация о заказах\n"
            "• Ожидающие заказы\n"
            "• История операций\n\n"
            "❌ **ДАННОЕ ДЕЙСТВИЕ НЕОБРАТИМО!**\n\n"
            "Подтвердите очистку, отправив: **ОЧИСТИТЬ**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        return
        
    elif call.data == "export_order_files":
        # Выгрузка файлов заказов
        try:
            files_info = []
            
            # Проверяем и отправляем файлы
            if os.path.exists(ORDERS_PATH):
                with open(ORDERS_PATH, 'rb') as f:
                    bot.send_document(call.message.chat.id, f, 
                                    caption="📋 **Файл информации о заказах**\n"
                                           f"Размер: {os.path.getsize(ORDERS_PATH)} байт")
                files_info.append("✅ orders_info.json")
            else:
                files_info.append("❌ orders_info.json (не найден)")
                
            if os.path.exists(PENDING_ORDERS_PATH):
                with open(PENDING_ORDERS_PATH, 'rb') as f:
                    bot.send_document(call.message.chat.id, f,
                                    caption="⏳ **Файл ожидающих заказов**\n"
                                           f"Размер: {os.path.getsize(PENDING_ORDERS_PATH)} байт")
                files_info.append("✅ pending_orders.json")
            else:
                files_info.append("❌ pending_orders.json (не найден)")
                
            # Также отправляем конфигурацию
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'rb') as f:
                    bot.send_document(call.message.chat.id, f,
                                    caption="⚙️ **Файл конфигурации плагина**\n"
                                           f"Размер: {os.path.getsize(CONFIG_PATH)} байт")
                files_info.append("✅ config.json")
            else:
                files_info.append("❌ config.json (не найден)")
                
            bot.edit_message_text(
                "📤 **ВЫГРУЗКА ФАЙЛОВ ЗАВЕРШЕНА**\n\n"
                "📂 **Отправленные файлы:**\n" + "\n".join(files_info) + "\n\n"
                "💡 Эти файлы можно использовать для резервного копирования или переноса настроек.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            bot.edit_message_text(
                f"❌ **ОШИБКА ВЫГРУЗКИ**\n\n"
                f"Не удалось выгрузить файлы: {e}\n\n"
                f"Проверьте права доступа к файлам и попробуйте снова.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        bot.answer_callback_query(call.id)
        return
            
    elif call.data == "change_bot_username":
        user_states[user_id] = "waiting_bot_username"
        cfg = load_config()
        current_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
        bot.edit_message_text(
            "🤖 **ИЗМЕНЕНИЕ НИКНЕЙМА БОТА**\n\n"
            f"**Текущий никнейм:** `{current_username}`\n\n"
            "Введите новый никнейм для Minecraft бота.\n"
            "Например: `nickname` или `MyBot123`\n\n"
            "📋 **Требования:**\n"
            "• От 3 до 16 символов\n"
            "• Только буквы, цифры и подчеркивания\n"
            "• Аккаунт должен существовать на сервере\n\n"
            "⚠️ **ВАЖНО!** После изменения никнейма не забудьте проверить пароль!\n"
            "Убедитесь, что этот аккаунт существует и у вас есть к нему доступ!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "change_bot_password":
        user_states[user_id] = "waiting_bot_password"
        cfg = load_config()
        current_password = cfg.get('minecraft_bot', {}).get('password', 'не указан')
        # Показываем текущий пароль явно (по требованию)
        masked_password = current_password if current_password != 'не указан' else 'не указан'
        bot.edit_message_text(
            "🔑 **ИЗМЕНЕНИЕ ПАРОЛЯ БОТА**\n\n"
            f"**Текущий пароль:** `{masked_password}`\n\n"
            "Введите новый пароль для входа Minecraft бота на сервер.\n\n"
            "📋 **Требования:**\n"
            "• Минимум 6 символов\n"
            "• Пароль должен соответствовать аккаунту бота\n\n"
            "🔒 **Безопасность:**\n"
            "Пароль будет сохранен в зашифрованном виде в настройках плагина.\n\n"
            "⚠️ Убедитесь, что пароль правильный для указанного аккаунта!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "change_test_username":
        user_states[user_id] = "waiting_test_username"
        cfg = load_config()
        current_test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
        bot.edit_message_text(
            "🎯 **ИЗМЕНЕНИЕ ТЕСТОВОГО НИКНЕЙМА**\n\n"
            f"**Текущий тестовый никнейм:** `{current_test_username}`\n\n"
            "Введите никнейм игрока, на который будут отправляться тестовые переводы при использовании команды `/mc_test_pay`.\n\n"
            "📋 **Назначение:**\n"
            "• Используется для команды `/mc_test_pay`\n"
            "• На этот никнейм переводится 1000 монет для тестирования\n"
            "• Помогает проверить работу бота без реальных заказов\n\n"
            "💡 **Рекомендации:**\n"
            "• Используйте свой собственный игровой аккаунт\n"
            "• Или аккаунт для тестирования\n"
            "• Никнейм должен быть онлайн на сервере при тестировании\n\n"
            "Например: `testplayer` или `MyTestAccount`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "change_server_ip":
        # Запрашиваем новый IP/хост (возможен формат host:port)
        user_states[user_id] = "waiting_server_ip"
        cfg = load_config()
        current_server = cfg.get('minecraft_bot', {}).get('server', 'funtime.su')
        current_port = cfg.get('minecraft_bot', {}).get('port', 25565)
        bot.edit_message_text(
            "🌐 **ИЗМЕНЕНИЕ IP**\n\n"
            f"**Текущий сервер:** `{current_server}:{current_port}`\n\n"
            "Введите новый IP-сервера"
            "К примеру funtime.su или spookytime.net",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "change_after_payment":
        user_states[user_id] = "waiting_after_payment"
        cfg = load_config()
        current_text = cfg['messages']['after_payment']
        bot.edit_message_text(
            "💬 **ИЗМЕНЕНИЕ ТЕКСТА ПОСЛЕ ОПЛАТЫ**\n\n"
            f"**Текущий текст:**\n```\n{current_text}\n```\n\n"
            "Введите новый текст сообщения, которое будет отправлено покупателю после оплаты заказа.\n\n"
            "💡 Этот текст должен объяснять покупателю, что нужно указать никнейм в Minecraft.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "change_processing":
        user_states[user_id] = "waiting_processing"
        cfg = load_config()
        current_text = cfg['messages']['processing']
        try:
            # Use HTML <pre> block so Telegram shows a proper code block with copy on supported clients
            esc = html.escape(str(current_text))
            msg_html = (
                "⏳ ИЗМЕНЕНИЕ ТЕКСТА ОБРАБОТКИ\n\n"
                "Текущий текст:\n" + f"<pre>{esc}</pre>\n\n"
                "Введите новый текст сообщения при обработке заказа.\n\n"
                "Доступные переменные: {order_id}, {amount}, {username}\n\n"
                "Этот текст отправляется когда покупатель указал никнейм и заказ принят в обработку."
            )
            bot.edit_message_text(msg_html, call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка редактирования сообщения (change_processing): {e}")
            try:
                esc = html.escape(str(current_text))
                fallback_html = "⏳ Введите новый текст для сообщения при обработке заказа (текущее):\n" + f"<pre>{esc}</pre>"
                bot.send_message(call.message.chat.id, fallback_html, parse_mode='HTML')
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "change_completed":
        user_states[user_id] = "waiting_completed"
        cfg = load_config()
        current_text = cfg['messages']['completed']
        try:
            esc = html.escape(str(current_text))
            msg_html = (
                "✅ ИЗМЕНЕНИЕ ТЕКСТА ЗАВЕРШЕНИЯ\n\n"
                "Текущий текст:\n" + f"<pre>{esc}</pre>\n\n"
                "Введите новый текст сообщения после успешного завершения заказа.\n\n"
                "Доступные переменные: {order_id}, {amount}, {username}\n\n"
                "Этот текст отправляется когда валюта успешно переведена игроку."
            )
            bot.edit_message_text(msg_html, call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка редактирования сообщения (change_completed): {e}")
            try:
                esc = html.escape(str(current_text))
                fallback_html = "✅ Введите новый текст для сообщения после завершения заказа (текущее):\n" + f"<pre>{esc}</pre>"
                bot.send_message(call.message.chat.id, fallback_html, parse_mode='HTML')
            except Exception:
                pass
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "show_all_settings":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_full_settings_message = types.Message()
        show_full_settings_message.chat = call.message.chat
        show_full_settings(show_full_settings_message)
        bot.answer_callback_query(call.id)
        return
        
    elif call.data == "refresh_settings":
        refresh_message = types.Message()
        refresh_message.chat = call.message.chat
        refresh_message.message_id = call.message.message_id
        bot.delete_message(call.message.chat.id, call.message.message_id)
        minecraft_currency_settings(refresh_message)
        bot.answer_callback_query(call.id)
        return
        
    # Управление лотами удалено — все соответствующие callback'и пропущены
        
    # Отвечаем на callback чтобы убрать "loading" индикатор
    bot.answer_callback_query(call.id)

def handle_settings_input(message: types.Message):
    """Обработка ввода новых значений настроек"""
    global user_states
    
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
        
    state = user_states[user_id]
    new_value = message.text.strip()
    
    cfg = load_config()
    
    if state == "waiting_bot_username":
        # Изменяем никнейм бота
        if len(new_value) < 3 or len(new_value) > 16:
            bot.send_message(message.chat.id, 
                           "❌ Никнейм должен быть от 3 до 16 символов!\n"
                           "Попробуйте еще раз:")
            return
            
        # Проверяем на допустимые символы (буквы, цифры, подчеркивания)
        if not new_value.replace('_', '').isalnum():
            bot.send_message(message.chat.id, 
                           "❌ Никнейм может содержать только буквы, цифры и подчеркивания!\n"
                           "Попробуйте еще раз:")
            return
            
        old_username = cfg.get('minecraft_bot', {}).get('bot_username', 'не указан')
        
        # Инициализируем minecraft_bot если его нет
        if 'minecraft_bot' not in cfg:
            cfg['minecraft_bot'] = {}
            
        cfg['minecraft_bot']['bot_username'] = new_value
        save_config(cfg)
        
        bot.send_message(message.chat.id, 
                        f"✅ **НИКНЕЙМ БОТА ИЗМЕНЕН**\n\n"
                        f"**Старый никнейм:** `{old_username}`\n"
                        f"**Новый никнейм:** `{new_value}`\n\n"
                        f"🔄 Настройки сохранены! Теперь бот будет использовать никнейм `{new_value}` для входа на сервер.\n\n"
                        f"⚠️ **ВАЖНОЕ НАПОМИНАНИЕ:**\n"
                        f"� Не забудьте убедиться, что пароль соответствует этому аккаунту!\n"
                        f"🔧 Используйте кнопку 'Изменить пароль' если нужно обновить пароль.\n\n"
                        f"💡 Проверьте подключение бота командой /mc_test_bot",
                        parse_mode='Markdown')
        
        logger.info(f"{LOGGER_PREFIX} Администратор изменил никнейм бота: {old_username} → {new_value}")
        
    elif state == "waiting_bot_password":
        # Изменяем пароль бота
        if len(new_value) < 6:
            bot.send_message(message.chat.id, 
                           "❌ Пароль должен быть минимум 6 символов!\n"
                           "Попробуйте еще раз:")
            return
            
        # Инициализируем minecraft_bot если его нет
        if 'minecraft_bot' not in cfg:
            cfg['minecraft_bot'] = {}
            
        cfg['minecraft_bot']['password'] = new_value
        save_config(cfg)
        
        # Показываем новый пароль явно (по требованию)
        masked_password = new_value

        bot.send_message(message.chat.id, 
                        f"✅ **ПАРОЛЬ БОТА ИЗМЕНЕН**\n\n"
                        f"**Новый пароль:** `{masked_password}` ({len(new_value)} символов)\n\n"
                        f"🔄 Настройки сохранены! Пароль будет использоваться для входа бота на сервер.\n\n"
                        f"🔒 **Безопасность:** Пароль сохранен в конфигурации плагина.\n\n"
                        f"💡 Проверьте подключение бота командой /mc_test_bot",
                        parse_mode='Markdown')

        logger.info(f"{LOGGER_PREFIX} Администратор изменил пароль бота (длина: {len(new_value)} символов)")

        # Удаляем сообщение с паролем для безопасности
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass  # Игнорируем ошибки удаления
        
    elif state == "waiting_test_username":
        # Изменяем тестовый никнейм
        if len(new_value) < 3 or len(new_value) > 16:
            bot.send_message(message.chat.id, 
                           "❌ Никнейм должен быть от 3 до 16 символов!\n"
                           "Попробуйте еще раз:")
            return
            
        # Проверяем на допустимые символы (буквы, цифры, подчеркивания)
        if not new_value.replace('_', '').isalnum():
            bot.send_message(message.chat.id, 
                           "❌ Никнейм может содержать только буквы, цифры и подчеркивания!\n"
                           "Попробуйте еще раз:")
            return
            
        old_test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
        
        # Инициализируем minecraft_bot если его нет
        if 'minecraft_bot' not in cfg:
            cfg['minecraft_bot'] = {}
            
        cfg['minecraft_bot']['test_username'] = new_value
        save_config(cfg)
        
        bot.send_message(message.chat.id, 
                        f"✅ **ТЕСТОВЫЙ НИКНЕЙМ ИЗМЕНЕН**\n\n"
                        f"**Старый тестовый никнейм:** `{old_test_username}`\n"
                        f"**Новый тестовый никнейм:** `{new_value}`\n\n"
                        f"🔄 Настройки сохранены! Теперь команда `/mc_test_pay` будет отправлять 1000 монет на аккаунт `{new_value}`.\n\n"
                        f"🎯 **Применение:**\n"
                        f"• Используйте `/mc_test_pay` для тестирования бота\n"
                        f"• На `{new_value}` будет переведено 1000 тестовых монет\n"
                        f"• Помогает проверить работу без реальных заказов\n\n"
                        f"💡 Убедитесь, что этот игрок онлайн при тестировании!",
                        parse_mode='Markdown')
        
        logger.info(f"{LOGGER_PREFIX} Администратор изменил тестовый никнейм: {old_test_username} → {new_value}")
    
    elif state == "waiting_server_ip":
        # Ожидаем ввода нового хоста или ip[:port]
        # Допустимые форматы: example.com, 1.2.3.4, example.com:25565, 1.2.3.4:25566
        val = new_value
        host = None
        port = None

        # Разбиваем по двоеточию для порта
        if ':' in val:
            parts = val.rsplit(':', 1)
            host = parts[0].strip()
            port_part = parts[1].strip()
            if not port_part.isdigit():
                bot.send_message(message.chat.id, "❌ Неверный формат порта. Укажите числовой порт, например: example.com:25565")
                return
            port = int(port_part)
        else:
            host = val.strip()

        # Базовая валидация хоста (не пустой, не слишком длинный)
        if not host or len(host) > 253:
            bot.send_message(message.chat.id, "❌ Неверный хост/IP. Попробуйте снова.")
            return

        # Применяем изменения в конфиге
        if 'minecraft_bot' not in cfg:
            cfg['minecraft_bot'] = {}
        cfg['minecraft_bot']['server'] = host
        if port is not None:
            cfg['minecraft_bot']['port'] = port
        else:
            # Убедимся, что порт существует в конфиге
            cfg['minecraft_bot'].setdefault('port', 25565)

        save_config(cfg)

        bot.send_message(message.chat.id,
                        f"✅ **СЕРВЕР ИЗМЕНЁН**\n\n**Новый сервер:** `{cfg['minecraft_bot']['server']}:{cfg['minecraft_bot'].get('port', 25565)}`\n\nНастройки сохранены. Теперь все операции будут выполняться на указанном сервере.",
                        parse_mode='Markdown')

        logger.info(f"{LOGGER_PREFIX} Администратор изменил сервер Minecraft: {cfg['minecraft_bot']['server']}:{cfg['minecraft_bot'].get('port', 25565)}")
        
    elif state == "waiting_after_payment":
        # Изменяем текст после оплаты
        if len(new_value) > 1000:
            bot.send_message(message.chat.id, 
                           "❌ Текст слишком длинный! Максимум 1000 символов.\n"
                           "Попробуйте еще раз:")
            return
            
        cfg['messages']['after_payment'] = new_value
        save_config(cfg)
        
        bot.send_message(message.chat.id, 
                        f"✅ **ТЕКСТ ПОСЛЕ ОПЛАТЫ ИЗМЕНЕН**\n\n"
                        f"**Новый текст:**\n```\n{new_value}\n```\n\n"
                        f"🔄 Настройки сохранены! Этот текст будет отправляться покупателям после оплаты.",
                        parse_mode='Markdown')
        
        logger.info(f"{LOGGER_PREFIX} Администратор изменил текст после оплаты")
        
    elif state == "waiting_processing":
        # Изменяем текст обработки
        if len(new_value) > 1000:
            bot.send_message(message.chat.id, 
                           "❌ Текст слишком длинный! Максимум 1000 символов.\n"
                           "Попробуйте еще раз:")
            return
            
        # Проверяем наличие необходимых переменных
        required_vars = ['{order_id}', '{amount}', '{username}']
        missing_vars = [var for var in required_vars if var not in new_value]
        
        if missing_vars:
            bot.send_message(message.chat.id, 
                           f"⚠️ **ВНИМАНИЕ!** В тексте отсутствуют важные переменные:\n"
                           f"• {', '.join(missing_vars)}\n\n"
                           f"Рекомендуется включить их для правильного отображения информации о заказе.\n"
                           f"Продолжить сохранение? Отправьте 'да' для подтверждения или новый текст для изменения.")
            user_states[user_id] = "confirm_processing"
            user_states[f"{user_id}_temp"] = new_value
            return
            
        cfg['messages']['processing'] = new_value
        save_config(cfg)
        
        bot.send_message(message.chat.id, 
                        f"✅ **ТЕКСТ ОБРАБОТКИ ИЗМЕНЕН**\n\n"
                        f"**Новый текст:**\n```\n{new_value}\n```\n\n"
                        f"🔄 Настройки сохранены! Этот текст будет отправляться при обработке заказов.",
                        parse_mode='Markdown')
        
        logger.info(f"{LOGGER_PREFIX} Администратор изменил текст обработки заказа")
        
    elif state == "waiting_completed":
        # Изменяем текст завершения
        if len(new_value) > 1000:
            bot.send_message(message.chat.id, 
                           "❌ Текст слишком длинный! Максимум 1000 символов.\n"
                           "Попробуйте еще раз:")
            return
            
        # Проверяем наличие необходимых переменных
        required_vars = ['{order_id}', '{amount}', '{username}']
        missing_vars = [var for var in required_vars if var not in new_value]
        
        if missing_vars:
            bot.send_message(message.chat.id, 
                           f"⚠️ **ВНИМАНИЕ!** В тексте отсутствуют важные переменные:\n"
                           f"• {', '.join(missing_vars)}\n\n"
                           f"Рекомендуется включить их для правильного отображения информации о заказе.\n"
                           f"Продолжить сохранение? Отправьте 'да' для подтверждения или новый текст для изменения.")
            user_states[user_id] = "confirm_completed"
            user_states[f"{user_id}_temp"] = new_value
            return
            
        cfg['messages']['completed'] = new_value
        save_config(cfg)
        
        bot.send_message(message.chat.id, 
                        f"✅ **ТЕКСТ ЗАВЕРШЕНИЯ ИЗМЕНЕН**\n\n"
                        f"**Новый текст:**\n```\n{new_value}\n```\n\n"
                        f"🔄 Настройки сохранены! Этот текст будет отправляться после успешного завершения заказов.",
                        parse_mode='Markdown')
        
        logger.info(f"{LOGGER_PREFIX} Администратор изменил текст завершения заказа")
        
    elif state == "confirm_processing":
        # Если админ отвечает 'да' — сохраняем temp; иначе воспринимаем ответ как новый текст
        if new_value.lower() == "да":
            temp_text = user_states.pop(f"{user_id}_temp", "")
            cfg['messages']['processing'] = temp_text
            save_config(cfg)

            bot.send_message(message.chat.id, 
                            f"✅ **ТЕКСТ ОБРАБОТКИ СОХРАНЕН**\n\n"
                            f"**Новый текст:**\n```\n{temp_text}\n```\n\n"
                            f"⚠️ Сохранено без некоторых переменных. Вы можете изменить текст позже через меню настроек.",
                            parse_mode='Markdown')

            user_states.pop(f"{user_id}_temp", None)
            # Очистим состояние текущего пользователя
            if user_id in user_states:
                del user_states[user_id]
            logger.info(f"{LOGGER_PREFIX} Администратор подтвердил изменение текста обработки")
        else:
            # Воспринять ввод как новый текст — валидировать и сохранить при успехе
            if len(new_value) > 1000:
                bot.send_message(message.chat.id, 
                               "❌ Текст слишком длинный! Максимум 1000 символов.\n"
                               "Попробуйте еще раз:")
                # оставляем состояние confirm_processing чтобы админ мог подтвердить или ввести снова
                user_states[f"{user_id}_temp"] = new_value
                return

            required_vars = ['{order_id}', '{amount}', '{username}']
            missing_vars = [var for var in required_vars if var not in new_value]

            if missing_vars:
                bot.send_message(message.chat.id, 
                               f"⚠️ **ВНИМАНИЕ!** В тексте отсутствуют важные переменные:\n"
                               f"• {', '.join(missing_vars)}\n\n"
                               f"Рекомендуется включить их для правильного отображения информации о заказе.\n"
                               f"Продолжить сохранение? Отправьте 'да' для подтверждения или новый текст для изменения.")
                user_states[user_id] = "confirm_processing"
                user_states[f"{user_id}_temp"] = new_value
                return

            cfg['messages']['processing'] = new_value
            save_config(cfg)

            bot.send_message(message.chat.id, 
                            f"✅ **ТЕКСТ ОБРАБОТКИ ИЗМЕНЕН**\n\n"
                            f"**Новый текст:**\n```\n{new_value}\n```\n\n"
                            f"🔄 Настройки сохранены! Этот текст будет отправляться при обработке заказов.",
                            parse_mode='Markdown')

            # Очистим состояние текущего пользователя
            if user_id in user_states:
                del user_states[user_id]

            logger.info(f"{LOGGER_PREFIX} Администратор изменил текст обработки заказа")

    elif state == "confirm_completed":
        # Если админ отвечает 'да' — сохраняем temp; иначе воспринимаем ответ как новый текст
        if new_value.lower() == "да":
            temp_text = user_states.pop(f"{user_id}_temp", "")
            cfg['messages']['completed'] = temp_text
            save_config(cfg)

            bot.send_message(message.chat.id, 
                            f"✅ **ТЕКСТ ЗАВЕРШЕНИЯ СОХРАНЕН**\n\n"
                            f"**Новый текст:**\n```\n{temp_text}\n```\n\n"
                            f"⚠️ Сохранено без некоторых переменных. Вы можете изменить текст позже через меню настроек.",
                            parse_mode='Markdown')

            user_states.pop(f"{user_id}_temp", None)
            if user_id in user_states:
                del user_states[user_id]
            logger.info(f"{LOGGER_PREFIX} Администратор подтвердил изменение текста завершения")
        else:
            # Воспринять ввод как новый текст — валидировать и сохранить при успехе
            if len(new_value) > 1000:
                bot.send_message(message.chat.id, 
                               "❌ Текст слишком длинный! Максимум 1000 символов.\n"
                               "Попробуйте еще раз:")
                user_states[f"{user_id}_temp"] = new_value
                return

            required_vars = ['{order_id}', '{amount}', '{username}']
            missing_vars = [var for var in required_vars if var not in new_value]

            if missing_vars:
                bot.send_message(message.chat.id, 
                               f"⚠️ **ВНИМАНИЕ!** В тексте отсутствуют важные переменные:\n"
                               f"• {', '.join(missing_vars)}\n\n"
                               f"Рекомендуется включить их для правильного отображения информации о заказе.\n"
                               f"Продолжить сохранение? Отправьте 'да' для подтверждения или новый текст для изменения.")
                user_states[user_id] = "confirm_completed"
                user_states[f"{user_id}_temp"] = new_value
                return

            cfg['messages']['completed'] = new_value
            save_config(cfg)

            bot.send_message(message.chat.id, 
                            f"✅ **ТЕКСТ ЗАВЕРШЕНИЯ ИЗМЕНЕН**\n\n"
                            f"**Новый текст:**\n```\n{new_value}\n```\n\n"
                            f"🔄 Настройки сохранены! Этот текст будет отправляться после успешного завершения заказов.",
                            parse_mode='Markdown')

            if user_id in user_states:
                del user_states[user_id]

            logger.info(f"{LOGGER_PREFIX} Администратор изменил текст завершения заказа")
        
    elif state == "confirm_clear_files" and new_value == "ОЧИСТИТЬ":
        # Подтверждение очистки файлов заказов
        global pending_orders, orders_info
        
        try:
            # Подсчитываем что будет удалено
            pending_count = len(pending_orders)
            info_count = len(orders_info)
            
            # Очищаем данные в памяти
            pending_orders.clear()
            orders_info.clear()
            
            # Удаляем файлы
            files_deleted = []
            if os.path.exists(ORDERS_PATH):
                os.remove(ORDERS_PATH)
                files_deleted.append("✅ orders_info.json")
            if os.path.exists(PENDING_ORDERS_PATH):
                os.remove(PENDING_ORDERS_PATH)
                files_deleted.append("✅ pending_orders.json")
                
            # Пересоздаем пустые файлы
            save_orders_info({})
            save_pending_orders({})
            
            bot.send_message(message.chat.id, 
                            f"🗑️ **ОЧИСТКА ФАЙЛОВ ЗАВЕРШЕНА**\n\n"
                            f"📊 **Удалено из памяти:**\n"
                            f"• Ожидающих заказов: {pending_count}\n"
                            f"• Записей информации: {info_count}\n\n"
                            f"📂 **Удаленные файлы:**\n" + 
                            ("\n".join(files_deleted) if files_deleted else "• Файлы не найдены") + "\n\n"
                            f"✅ Система очищена и готова к работе с новыми заказами!",
                            parse_mode='Markdown')
            
            logger.info(f"{LOGGER_PREFIX} Администратор очистил файлы заказов: pending={pending_count}, info={info_count}")
            
        except Exception as e:
            bot.send_message(message.chat.id, 
                            f"❌ **ОШИБКА ОЧИСТКИ**\n\n"
                            f"Не удалось очистить файлы: {e}\n\n"
                            f"Попробуйте выполнить команду /mc_clear для очистки через альтернативный способ.",
                            parse_mode='Markdown')
            logger.error(f"{LOGGER_PREFIX} Ошибка очистки файлов: {e}")
            
    elif state == "confirm_clear_files":
        # Неправильное подтверждение
        bot.send_message(message.chat.id, 
                        "❌ **ОЧИСТКА ОТМЕНЕНА**\n\n"
                        "Для подтверждения нужно ввести точно: **ОЧИСТИТЬ**\n\n"
                        "Очистка файлов заказов не выполнена.")
    
    elif state == "waiting_lot_add" or state == "waiting_lot_remove":
        # Функционал управления лотами отключён
        bot.send_message(message.chat.id, "⚠️ Функция управления ID лотов отключена в этой сборке.")
        logger.info(f"{LOGGER_PREFIX} Попытка использования управления лотами — функция отключена")
    
    # Очищаем состояние пользователя
    if user_id in user_states:
        del user_states[user_id]

def init_commands(c_: Cardinal):
    """Инициализация команд плагина"""
    global bot, cardinal_instance
    
    cardinal_instance = c_
    bot = c_.telegram.bot
    
    logger.info(f"{LOGGER_PREFIX} Инициализация плагина...")
    
    # Загружаем данные в глобальные переменные
    global orders_info, pending_orders
    orders_info = load_orders_info()
    pending_orders = load_pending_orders()
    
    logger.info(f"{LOGGER_PREFIX} Загружено {len(orders_info)} заказов в память")
    logger.info(f"{LOGGER_PREFIX} Загружено {len(pending_orders)} ожидающих заказов")
    
    # Регистрация команд
    @bot.message_handler(commands=['mc_settings'])
    def mc_settings_handler(message):
        minecraft_currency_settings(message)
    
    @bot.message_handler(commands=['mc_start'])
    def mc_start_handler(message):
        start_minecraft_plugin(message)
    
    @bot.message_handler(commands=['mc_stop'])
    def mc_stop_handler(message):
        stop_minecraft_plugin(message)
    
    @bot.message_handler(commands=['mc_pending'])
    def mc_pending_handler(message):
        show_pending_orders(message)
    
    @bot.message_handler(commands=['mc_clear'])
    def mc_clear_handler(message):
        clear_all_orders(message)
    
    @bot.message_handler(commands=['mc_toggle_auto'])
    def mc_toggle_auto_handler(message):
        toggle_auto_give(message)
    
    @bot.message_handler(commands=['mc_process_all'])
    def mc_process_all_handler(message):
        process_pending_orders_auto(message)
    
    @bot.message_handler(commands=['mc_test_pay'])
    def mc_test_pay_handler(message):
        """Тестовый перевод валюты"""
        cfg = load_config()
        test_username = cfg.get('minecraft_bot', {}).get('test_username', 'не указан')
        
        bot.send_message(message.chat.id, f"🧪 Тестируем перевод 1000 монет игроку {test_username}...")
        
        def test_pay_thread():
            try:
                result = give_minecraft_currency(test_username, 1000)
                if result['success']:
                    bot.send_message(message.chat.id, 
                                   f"✅ **ТЕСТОВЫЙ ПЕРЕВОД УСПЕШЕН!**\n\n"
                                   f"🎯 Игрок: `{test_username}`\n"
                                   f"💰 Сумма: 1,000 монет\n\n"
                                   f"✨ {result['message']}\n\n"
                                   f"🔧 Тестовый никнейм можно изменить в настройках бота (/mc_settings → 🤖 НАСТРОЙКИ БОТА → 🎯 Тестовый никнейм)",
                                   parse_mode='Markdown')
                else:
                    bot.send_message(message.chat.id, 
                                   f"❌ **ОШИБКА ТЕСТОВОГО ПЕРЕВОДА**\n\n"
                                   f"🎯 Игрок: `{test_username}`\n"
                                   f"💰 Сумма: 1,000 монет\n\n"
                                   f"⚠️ Ошибка: {result['message']}\n\n"
                                   f"🔧 Проверьте:\n"
                                   f"• Подключение к серверу (/mc_test_bot)\n"
                                   f"• Правильность тестового никнейма (/mc_settings)\n"
                                   f"• Что игрок {test_username} онлайн\n"
                                   f"• Достаточно ли средств у бота",
                                   parse_mode='Markdown')
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Критическая ошибка: {e}")
        
        threading.Thread(target=test_pay_thread, daemon=True).start()
    
    @bot.message_handler(commands=['mc_force_auto'])
    def mc_force_auto_handler(message):
        """Принудительный запуск автовыдачи"""
        bot.send_message(message.chat.id, "🔧 Принудительно запускаем автовыдачу для всех готовых заказов...")
        
        def force_auto_thread():
            try:
                global pending_orders
                ready_orders = []
                
                # Находим ВСЕ заказы со статусом ready_for_admin или имеющие никнейм
                for order_id, order_data in pending_orders.items():
                    username = order_data.get('minecraft_username')
                    if username and username != 'не указан':
                        ready_orders.append((order_id, order_data))
                        bot.send_message(message.chat.id, f"🎯 Найден заказ #{order_id} для {username}")
                
                if not ready_orders:
                    bot.send_message(message.chat.id, "❌ Нет заказов готовых к автовыдаче")
                    return
                
                for order_id, order_data in ready_orders:
                    username = order_data.get('minecraft_username')
                    amount = order_data.get('amount', 0)
                    
                    bot.send_message(message.chat.id, f"🤖 Запускаем автовыдачу для #{order_id}: {amount:,} монет → {username}")
                    
                    result = auto_complete_order_with_currency(order_id, message.chat.id)
                    if result:
                        bot.send_message(message.chat.id, f"✅ Заказ #{order_id} успешно выполнен!")
                    else:
                        bot.send_message(message.chat.id, f"❌ Ошибка выполнения заказа #{order_id}")
                    
                    time.sleep(2)  # Пауза между заказами
                        
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Критическая ошибка: {e}")
        
        threading.Thread(target=force_auto_thread, daemon=True).start()
    
    @bot.message_handler(commands=['mc_test_bot'])
    def mc_test_bot_handler(message):
        """Тестирование Minecraft бота"""
        bot.send_message(message.chat.id, "🤖 Тестируем подключение Minecraft бота...")
        
        def test_thread():
            try:
                result = test_minecraft_bot_connection()
                if result:
                    bot.send_message(message.chat.id, "✅ Minecraft бот успешно подключается к серверу!")
                else:
                    bot.send_message(message.chat.id, "❌ Ошибка подключения Minecraft бота. Проверьте настройки и логи.")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Критическая ошибка тестирования: {e}")
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    # Команды управления лотами удалены
    
    # /mc_lot_add удалена
    
    # /mc_lot_remove удалена
    
    # /mc_lot_toggle и /mc_filter удалены

    # /mc_lot_clear удалена
    
    @bot.message_handler(func=lambda message: message.text and message.text.startswith('/complete_'))
    def complete_handler(message):
        order_id = message.text.replace('/complete_', '')
        complete_order(message, order_id)
    
    @bot.message_handler(func=lambda message: message.text and message.text.startswith('/auto_'))
    def auto_complete_handler(message):
        """Автоматическая выдача валюты"""
        order_id = message.text.replace('/auto_', '')
        
        # Проверяем, что заказ существует
        if order_id not in pending_orders:
            bot.send_message(message.chat.id, f"❌ Заказ #{order_id} не найден в ожидающих.")
            return
        
        order_data = pending_orders[order_id]
        username = order_data.get('minecraft_username')
        amount = order_data.get('amount', 0)
        
        if not username:
            bot.send_message(message.chat.id, f"❌ Для заказа #{order_id} не указан никнейм Minecraft.")
            return
        
        bot.send_message(message.chat.id, f"🤖 Запускаем автоматическую выдачу {amount:,} монет игроку {username}...")
        
        def auto_give_thread():
            try:
                result = auto_complete_order_with_currency(order_id, message.chat.id)
                if result:
                    bot.send_message(message.chat.id, f"✅ Валюта успешно выдана автоматически!")
                else:
                    bot.send_message(message.chat.id, f"❌ Ошибка автоматической выдачи валюты. Проверьте логи.")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Критическая ошибка автовыдачи: {e}")
        
        threading.Thread(target=auto_give_thread, daemon=True).start()
    
    # Обработчик для настроек (инлайн кнопки)
    @bot.callback_query_handler(func=lambda call: call.data in [
        'show_bot_category', 'show_messages_category', 'show_orders_category', 'show_general_category',
    'back_to_main', 'change_bot_username', 'change_bot_password', 'change_test_username', 'change_after_payment', 
        'change_processing', 'change_completed', 'show_all_settings', 'refresh_settings', 
        'show_password', 'clear_order_files', 'export_order_files', 'bot_category_header', 
    'set_server_spooky', 'change_server_ip', 'messages_category_header', 'orders_category_header', 'general_category_header'
    ])
    def settings_callback_handler(call):
        handle_settings_callback(call)
    
    # Обработчик для ввода новых значений настроек
    @bot.message_handler(func=lambda message: message.from_user.id in user_states)
    def settings_input_handler(message):
        handle_settings_input(message)
    
    @bot.message_handler(func=lambda message: message.text and message.text.startswith('/cancel_'))
    def cancel_handler(message):
        order_id = message.text.replace('/cancel_', '')
        cancel_order(message, order_id)
    
    # Автозапуск если включен
    cfg = load_config()
    if cfg.get('auto_start', True):
        global RUNNING
        RUNNING = True
        logger.info(f"{LOGGER_PREFIX} Автозапуск плагина активирован")
    
    logger.info(f"{LOGGER_PREFIX} Плагин успешно инициализирован")
    
    # Выводим начальную информацию
    logger.info(f"{LOGGER_PREFIX} ========================================")
    logger.info(f"{LOGGER_PREFIX} MINECRAFT CURRENCY PLUGIN v{VERSION}")
    logger.info(f"{LOGGER_PREFIX} {DESCRIPTION}")
    logger.info(f"{LOGGER_PREFIX} Создатель @ilpajj, funpay - https://funpay.com/users/5327459/")
    logger.info(f"{LOGGER_PREFIX} ========================================")

# Регистрация обработчиков
BIND_TO_PRE_INIT = [init_commands]
BIND_TO_NEW_MESSAGE = [minecraft_currency_handler]
BIND_TO_NEW_ORDER = [minecraft_currency_handler]
BIND_TO_DELETE = None

import sqlite3
import datetime
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest

# Настройки
TOKEN = "8444869672:AAECHM3QrOlvrcriSbIbzumJ32x9b6f-7_c"
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# База данных
conn = sqlite3.connect('school.db', check_same_thread=False)
c = conn.cursor()

# Создаем таблицы
c.execute('''CREATE TABLE IF NOT EXISTS lessons
             (id INTEGER PRIMARY KEY, subject TEXT, start TEXT, end TEXT, day TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS homework
             (id INTEGER PRIMARY KEY, subject TEXT, task TEXT, deadline TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, chat_id INTEGER, username TEXT)''')
conn.commit()

# Словарь для хранения chat_id пользователей
user_chats = {}

# Клавиатура
def get_keyboard():
    buttons = [
        [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="➕ Урок")],
        [KeyboardButton(text="📚 ДЗ"), KeyboardButton(text="➕ ДЗ")],
        [KeyboardButton(text="🔔 Сегодня"), KeyboardButton(text="⏰ Вкл/Выкл уведомления")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Состояния уведомлений
notifications_enabled = {}

# /start
@router.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    
    # Сохраняем пользователя
    c.execute("INSERT OR REPLACE INTO users (user_id, chat_id, username) VALUES (?, ?, ?)",
              (user_id, chat_id, username))
    conn.commit()
    
    # Включаем уведомления по умолчанию
    notifications_enabled[user_id] = True
    
    await message.answer(
        f"Привет, {username}! Я школьный помощник.\n\n"
        f"✅ Уведомления включены\n"
        f"Я буду присылать напоминания:\n"
        f"• За 5 минут до урока\n"
        f"• За день до дедлайна ДЗ",
        reply_markup=get_keyboard()
    )

# Вкл/Выкл уведомления
@router.message(lambda m: m.text == "⏰ Вкл/Выкл уведомления")
async def toggle_notifications(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in notifications_enabled:
        notifications_enabled[user_id] = True
    
    # Меняем состояние
    notifications_enabled[user_id] = not notifications_enabled[user_id]
    
    status = "✅ ВКЛЮЧЕНЫ" if notifications_enabled[user_id] else "❌ ВЫКЛЮЧЕНЫ"
    
    await message.answer(
        f"Уведомления: {status}\n\n"
        f"Я буду присылать:\n"
        f"• За 5 минут до урока\n"
        f"• За день до дедлайна ДЗ",
        reply_markup=get_keyboard()
    )

# 📅 Расписание
@router.message(lambda m: m.text == "📅 Расписание")
async def schedule(message: types.Message):
    try:
        c.execute("SELECT * FROM lessons ORDER BY day, start")
        lessons = c.fetchall()
        
        if not lessons:
            await message.answer("Расписание пустое.")
            return
        
        # Группируем по дням
        days = {}
        for lesson in lessons:
            day = lesson[4]
            if day not in days:
                days[day] = []
            days[day].append(lesson)
        
        text = "📅 РАСПИСАНИЕ:\n\n"
        for day in ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]:
            if day in days:
                text += f"▫️ {day} ▫️\n"
                for lesson in days[day]:
                    text += f"• {lesson[1]}: {lesson[2]}-{lesson[3]}\n"
                text += "\n"
        
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# 🔔 Сегодня
@router.message(lambda m: m.text == "🔔 Сегодня")
async def today(message: types.Message):
    try:
        # Русские дни недели
        days_map = {
            "Monday": "Понедельник",
            "Tuesday": "Вторник", 
            "Wednesday": "Среда",
            "Thursday": "Четверг",
            "Friday": "Пятница",
            "Saturday": "Суббота",
            "Sunday": "Воскресенье"
        }
        
        today_en = datetime.datetime.now().strftime("%A")
        today_ru = days_map.get(today_en, today_en)
        
        c.execute("SELECT * FROM lessons WHERE day=?", (today_ru,))
        lessons = c.fetchall()
        
        if not lessons:
            await message.answer(f"Сегодня ({today_ru}) уроков нет.")
            return
        
        now = datetime.datetime.now()
        now_str = now.strftime("%H:%M")
        now_time = datetime.datetime.strptime(now_str, "%H:%M")
        
        text = f"🔔 УРОКИ НА СЕГОДНЯ ({today_ru}):\n\n"
        
        upcoming_lessons = []
        
        for lesson in lessons:
            start = datetime.datetime.strptime(lesson[2], "%H:%M")
            end = datetime.datetime.strptime(lesson[3], "%H:%M")
            
            if now_time < start:
                # Еще не начался
                mins = int((start - now_time).total_seconds() / 60)
                if mins <= 5:
                    status = f"🔔 Через {mins} мин!"
                else:
                    status = f"⏰ Через {mins} мин"
            elif start <= now_time <= end:
                # Идет сейчас
                mins_left = int((end - now_time).total_seconds() / 60)
                status = f"🟢 Идет! Осталось {mins_left} мин"
            else:
                # Уже прошел
                status = "✓ Прошел"
            
            text += f"• {lesson[1]}\n  {lesson[2]}-{lesson[3]}\n  {status}\n\n"
        
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# 📚 ДЗ
@router.message(lambda m: m.text == "📚 ДЗ")
async def show_hw(message: types.Message):
    try:
        c.execute("SELECT * FROM homework ORDER BY deadline")
        hw = c.fetchall()
        
        if not hw:
            await message.answer("Домашних заданий нет.")
            return
        
        text = "📚 ДОМАШНИЕ ЗАДАНИЯ:\n\n"
        today_date = datetime.date.today()
        
        for item in hw:
            deadline = datetime.datetime.strptime(item[3], "%Y-%m-%d").date()
            days = (deadline - today_date).days
            
            if days < 0:
                status = f"❌ Просрочено ({abs(days)} дн.)"
            elif days == 0:
                status = "⏰ СЕГОДНЯ!"
            elif days <= 3:
                status = f"🔥 Через {days} дн."
            else:
                status = f"📅 Через {days} дн."
            
            text += f"• {item[1]}\n  {item[2]}\n  {status}\n\n"
        
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# ➕ Урок
@router.message(lambda m: m.text == "➕ Урок")
async def add_lesson_prompt(message: types.Message):
    await message.answer("Напиши урок в формате:\nПредмет Начало Конец День\n\nПример:\nМатематика 14:30 15:15 Понедельник")

# ➕ ДЗ  
@router.message(lambda m: m.text == "➕ ДЗ")
async def add_hw_prompt(message: types.Message):
    await message.answer("Напиши ДЗ в формате:\nПредмет Задание Срок\n\nПример:\nМатематика Упр.5-10 2024-12-20")

# ФУНКЦИЯ ДЛЯ УВЕДОМЛЕНИЙ
async def send_notifications():
    """Функция для отправки уведомлений"""
    while True:
        try:
            now = datetime.datetime.now()
            
            # Получаем всех пользователей
            c.execute("SELECT user_id, chat_id FROM users")
            users = c.fetchall()
            
            for user_id, chat_id in users:
                # Проверяем включены ли уведомления
                if not notifications_enabled.get(user_id, True):
                    continue
                
                # 1. Проверяем уроки (за 5 минут)
                days_map = {
                    "Monday": "Понедельник",
                    "Tuesday": "Вторник", 
                    "Wednesday": "Среда",
                    "Thursday": "Четверг",
                    "Friday": "Пятница",
                    "Saturday": "Суббота",
                    "Sunday": "Воскресенье"
                }
                
                today_en = now.strftime("%A")
                today_ru = days_map.get(today_en, today_en)
                
                current_time_str = now.strftime("%H:%M")
                current_time = datetime.datetime.strptime(current_time_str, "%H:%M")
                
                c.execute("SELECT * FROM lessons WHERE day=?", (today_ru,))
                lessons = c.fetchall()
                
                for lesson in lessons:
                    start_time = datetime.datetime.strptime(lesson[2], "%H:%M")
                    
                    # Проверяем, начнется ли урок через 5 минут
                    time_diff = start_time - current_time
                    minutes_diff = int(time_diff.total_seconds() / 60)
                    
                    if minutes_diff == 5:  # Ровно за 5 минут
                        try:
                            await bot.send_message(
                                chat_id,
                                f"🔔 УРОК ЧЕРЕЗ 5 МИНУТ!\n\n"
                                f"📚 {lesson[1]}\n"
                                f"🕐 {lesson[2]}-{lesson[3]}\n"
                                f"📅 {today_ru}"
                            )
                        except Exception as e:
                            print(f"Ошибка отправки уведомления: {e}")
                
                # 2. Проверяем дедлайны ДЗ (за 1 день)
                tomorrow = now.date() + datetime.timedelta(days=1)
                tomorrow_str = tomorrow.strftime("%Y-%m-%d")
                
                c.execute("SELECT * FROM homework WHERE deadline=?", (tomorrow_str,))
                hw_tomorrow = c.fetchall()
                
                for hw in hw_tomorrow:
                    try:
                        await bot.send_message(
                            chat_id,
                            f"⏰ ЗАВТРА ДЕДЛАЙН!\n\n"
                            f"📚 {hw[1]}\n"
                            f"📝 {hw[2]}\n"
                            f"📅 Срок: {hw[3]}"
                        )
                    except Exception as e:
                        print(f"Ошибка отправки уведомления: {e}")
                
                # 3. Проверяем дедлайны ДЗ (сегодня)
                today_str = now.date().strftime("%Y-%m-%d")
                c.execute("SELECT * FROM homework WHERE deadline=?", (today_str,))
                hw_today = c.fetchall()
                
                for hw in hw_today:
                    try:
                        await bot.send_message(
                            chat_id,
                            f"🔥 СЕГОДНЯ ДЕДЛАЙН!\n\n"
                            f"📚 {hw[1]}\n"
                            f"📝 {hw[2]}\n"
                            f"⏰ Сдай до конца дня!"
                        )
                    except Exception as e:
                        print(f"Ошибка отправки уведомления: {e}")
            
            # Ждем 60 секунд до следующей проверки
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Ошибка в send_notifications: {e}")
            await asyncio.sleep(60)

# Обработка всех сообщений
@router.message()
async def handle_all(message: types.Message):
    text = message.text.strip()
    
    # Если это кнопка - игнорируем
    if text in ["📅 Расписание", "➕ Урок", "📚 ДЗ", "➕ ДЗ", "🔔 Сегодня", "⏰ Вкл/Выкл уведомления"]:
        return
    
    # Проверяем формат урока: 4 части через пробел
    parts = text.split()
    if len(parts) == 4:
        # Пробуем как урок
        try:
            subject = parts[0]
            start = parts[1]
            end = parts[2]
            day = parts[3]
            
            # Проверяем время
            datetime.datetime.strptime(start, "%H:%M")
            datetime.datetime.strptime(end, "%H:%M")
            
            # Добавляем урок
            c.execute("INSERT INTO lessons (subject, start, end, day) VALUES (?, ?, ?, ?)",
                      (subject, start, end, day))
            conn.commit()
            
            await message.answer(f"✅ Урок добавлен:\n{subject}\n{start}-{end}\n{day}", 
                               reply_markup=get_keyboard())
            return
            
        except ValueError as e:
            await message.answer(f"❌ Неверный формат времени. Используй ЧЧ:ММ", 
                               reply_markup=get_keyboard())
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}", reply_markup=get_keyboard())
            return
    
    # Проверяем формат ДЗ: 3 части через пробел
    if len(parts) == 3:
        # Пробуем как ДЗ
        try:
            subject = parts[0]
            task = parts[1]
            deadline = parts[2]
            
            # Проверяем дату
            datetime.datetime.strptime(deadline, "%Y-%m-%d")
            
            # Добавляем ДЗ
            c.execute("INSERT INTO homework (subject, task, deadline) VALUES (?, ?, ?)",
                      (subject, task, deadline))
            conn.commit()
            
            # Считаем дни
            deadline_date = datetime.datetime.strptime(deadline, "%Y-%m-%d").date()
            today = datetime.date.today()
            days = (deadline_date - today).days
            
            if days < 0:
                status = f"❌ Просрочено"
            elif days == 0:
                status = "⏰ СЕГОДНЯ!"
            else:
                status = f"📅 Через {days} дн."
            
            await message.answer(f"✅ ДЗ добавлено:\n{subject}\n{task}\n{status}", 
                               reply_markup=get_keyboard())
            return
            
        except ValueError as e:
            await message.answer(f"❌ Неверный формат даты. Используй ГГГГ-ММ-ДД", 
                               reply_markup=get_keyboard())
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}", reply_markup=get_keyboard())
            return
    
    # Если не распознано
    await message.answer("Не понял. Используй кнопки.", reply_markup=get_keyboard())

# Запуск бота и уведомлений
async def main():
    print("🤖 Бот запущен!")
    print("⏰ Уведомления работают")
    
    # Запускаем задачу для уведомлений
    asyncio.create_task(send_notifications())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
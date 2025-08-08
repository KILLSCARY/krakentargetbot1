import os
import logging
import random
import string
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from datetime import datetime, timedelta

API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    last_attempt TEXT,
    discount_code TEXT
)
""")
conn.commit()

def can_attempt(user_id):
    cursor.execute("SELECT last_attempt FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return True
    last = datetime.fromisoformat(row[0])
    return datetime.now() - last > timedelta(hours=24)

def mark_attempt(user_id, code=None):
    now = datetime.now().isoformat()
    if code:
        cursor.execute("INSERT OR REPLACE INTO users(user_id, last_attempt, discount_code) VALUES (?,?,?)", (user_id, now, code))
    else:
        cursor.execute("UPDATE users SET last_attempt = ? WHERE user_id = ?", (now, user_id))
    conn.commit()

def has_bonus(user_id):
    cursor.execute("SELECT discount_code FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] is not None

def generate_discount_code():
    suffix = ''.join(random.choices(string.digits, k=5))
    return f"KRAKEN-5%-{suffix}"

@dp.message_handler(commands=['start'])
async def start_game(message: types.Message):
    user_id = message.from_user.id
    if not can_attempt(user_id):
        await message.answer("⏳ Ты уже пробовал сегодня. Попробуй снова через 24 часа.")
        return
    if has_bonus(user_id):
        await message.answer("🎁 Ты уже получал скидку. Спасибо за участие!")
        return

    await message.answer(
        "🎩 Под одним из трёх колпачков прячется Кракен 🐙\n"
        "У тебя есть *1 попытка* в сутки!\n\nВыбери номер колпачка:",
        reply_markup=make_keyboard(),
        parse_mode='Markdown'
    )

def make_keyboard():
    buttons = [types.InlineKeyboardButton(str(i), callback_data=f'guess_{i}') for i in range(1, 4)]
    return types.InlineKeyboardMarkup(row_width=3).add(*buttons)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('guess_'))
async def process_guess(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not can_attempt(user_id):
        await bot.answer_callback_query(callback_query.id, text="⏳ Уже пробовал сегодня.")
        return
    if has_bonus(user_id):
        await bot.answer_callback_query(callback_query.id, text="🎁 Уже получал бонус.")
        return

    choice = int(callback_query.data.split('_')[1])
    kraken = random.randint(1, 3)

    if choice == kraken:
        code = generate_discount_code()
        mark_attempt(user_id, code)
        text = (
            f"🎉 Поздравляю, ты нашёл Кракена под №{choice}!\n\n"
            f"🎁 Твой скидочный код: `{code}`\n"
            f"📦 Закажи таргетинг во ВКонтакте: https://vk.com/your_target_service"
        )
    else:
        mark_attempt(user_id)
        text = f"❌ Кракена под №{choice} нет. Он был под №{kraken}.\nПопробуй завтра — /start"

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, text, parse_mode='Markdown')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

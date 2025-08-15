import asyncio
import sqlite3
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import pandas as pd

# ===== Конфигурация =====
TOKEN = "7294777489:AAFMvo3UvtnuOvpYyDIldCi0GuGyrTvyZHM"
ADMINS = [329116625, 866826839]  # Список ID админов

DB_PATH = "markets.db"

# ===== Инициализация бота =====
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== Работа с базой =====
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    conn.commit()
    conn.close()

def add_markets_from_df(df):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM markets")  # Полная замена
    for _, row in df.iterrows():
        c.execute(
            "INSERT INTO markets (name, latitude, longitude) VALUES (?, ?, ?)",
            (row['name'], row['latitude'], row['longitude'])
        )
    conn.commit()
    conn.close()

def get_all_markets():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, latitude, longitude FROM markets")
    rows = c.fetchall()
    conn.close()
    return rows

# ===== Клавиатура для обычного пользователя =====
def make_user_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    markets = get_all_markets()
    for name, lat, lon in markets:
        kb.add(InlineKeyboardButton(name, callback_data=f"{lat},{lon}"))
    return kb

# ===== Хэндлеры =====

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Вот список маркетов:", reply_markup=make_user_keyboard())

# ===== Админ команды =====

@dp.message(Command("import"))
async def cmd_import(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Нет прав для этой команды.")
        return
    await message.answer("Отправьте Excel файл с маркетами для импорта.")

@dp.message(Command("export"))
async def cmd_export(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Нет прав для этой команды.")
        return
    df = pd.DataFrame(get_all_markets(), columns=["name", "latitude", "longitude"])
    df.to_excel("exported_markets.xlsx", index=False)
    await message.answer_document(document=open("exported_markets.xlsx", "rb"))

@dp.message()
async def handle_docs(message: Message):
    if message.from_user.id not in ADMINS:
        return  # Обычные пользователи не могут загружать файлы

    if not message.document or not message.document.file_name.endswith(".xlsx"):
        return

    file = await bot.get_file(message.document.file_id)
    file_path = file.file_path
    await bot.download_file(file_path, destination="import.xlsx")

    df = pd.read_excel("import.xlsx")
    add_markets_from_df(df)
    await message.answer("Маркет импортирован и заменил старые.")

# ===== Запуск бота =====
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)  # Чтобы избежать конфликта
    try:
        print("Бот запущен через long polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

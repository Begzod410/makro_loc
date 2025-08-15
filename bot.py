import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.types import FSInputFile
import sqlite3
import pandas as pd
import asyncio

# Загружаем .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMINS = os.getenv("ADMINS").split(",")

if not TOKEN:
    raise ValueError("TOKEN не найден! Проверь .env файл или переменные окружения.")

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Работа с базой ---
DB_FILE = "markets.db"
conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS markets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    latitude REAL,
    longitude REAL
)""")
conn.commit()

# --- Команды для админов ---
@dp.message(Command(commands=["import"]))
async def cmd_import(message: types.Message):
    if str(message.from_user.id) not in ADMINS:
        await message.answer("У тебя нет прав для этой команды.")
        return
    await message.answer("Пришли Excel файл для импорта маркетов.")

@dp.message(Command(commands=["export"]))
async def cmd_export(message: types.Message):
    if str(message.from_user.id) not in ADMINS:
        await message.answer("У тебя нет прав для этой команды.")
        return
    df = pd.read_sql("SELECT * FROM markets", conn)
    file_path = "export.xlsx"
    df.to_excel(file_path, index=False)
    await message.answer_document(FSInputFile(file_path), caption="Экспорт маркетов.")

# --- Обработка присланного Excel ---
@dp.message(lambda message: message.document and str(message.from_user.id) in ADMINS)
async def excel_upload(message: types.Message):
    file_id = message.document.file_id
    file_path = f"{file_id}.xlsx"
    await bot.download_file_by_id(file_id, destination=file_path)
    df = pd.read_excel(file_path)
    cur.execute("DELETE FROM markets")  # очищаем старые маркеты
    for _, row in df.iterrows():
        cur.execute("INSERT INTO markets(name, latitude, longitude) VALUES(?,?,?)",
                    (row['name'], row['latitude'], row['longitude']))
    conn.commit()
    await message.answer(f"Импортировано {len(df)} маркетов!")

# --- Список маркетов для всех пользователей ---
@dp.message(Command(commands=["markets"]))
async def cmd_markets(message: types.Message):
    cur.execute("SELECT name FROM markets")
    rows = cur.fetchall()
    if not rows:
        await message.answer("Маркетов нет.")
        return
    kb_builder = InlineKeyboardBuilder()
    for (name,) in rows:
        kb_builder.button(text=name, callback_data=f"market:{name}")
    kb = kb_builder.as_markup(row_width=2)
    await message.answer("Выберите маркет:", reply_markup=kb)

# --- Обработка выбора маркетов ---
@dp.callback_query(lambda c: c.data and c.data.startswith("market:"))
async def market_callback(callback: types.CallbackQuery):
    name = callback.data.split("market:")[1]
    cur.execute("SELECT latitude, longitude FROM markets WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        lat, lon = row
        await callback.message.answer(f"{name}\nhttps://www.google.com/maps?q={lat},{lon}")
    await callback.answer()

# --- Старт бота ---
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

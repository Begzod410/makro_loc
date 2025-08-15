import os
import logging
import sqlite3
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram import F

# ---------------------- ЛОГИ ----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------- ПЕРЕМЕННЫЕ ----------------------
TOKEN = os.environ.get("7294777489:AAFMvo3UvtnuOvpYyDIldCi0GuGyrTvyZHM")
ADMINS = os.environ.get("329116625", "866826839")
ADMINS = [int(x.strip()) for x in ADMINS.split(",") if x.strip().isdigit()]

# ---------------------- БАЗА ДАННЫХ ----------------------
conn = sqlite3.connect("markets.db")
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS markets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    latitude REAL,
    longitude REAL
)""")
conn.commit()

# ---------------------- FSM ----------------------
storage = MemoryStorage()

class ImportStates(StatesGroup):
    waiting_file = State()

# ---------------------- БОТ ----------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ---------------------- ФУНКЦИИ ----------------------
def fetch_all_markets():
    cursor.execute("SELECT id, name FROM markets")
    return cursor.fetchall()

def import_markets_from_excel(file_path):
    df = pd.read_excel(file_path)
    cursor.execute("DELETE FROM markets")  # Полное замещение
    for _, row in df.iterrows():
        if pd.isna(row["name"]) or pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
            continue
        cursor.execute(
            "INSERT INTO markets (name, latitude, longitude) VALUES (?, ?, ?)",
            (row["name"], float(row["latitude"]), float(row["longitude"]))
        )
    conn.commit()

def export_markets_to_excel(file_path):
    cursor.execute("SELECT name, latitude, longitude FROM markets")
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=["name", "latitude", "longitude"])
    df.to_excel(file_path, index=False)

def make_market_keyboard():
    markets = fetch_all_markets()
    kb = InlineKeyboardMarkup(row_width=2)
    for _, name in markets:
        kb.add(InlineKeyboardButton(text=name, callback_data=f"market_{name}"))
    return kb

# ---------------------- ХЕНДЛЕРЫ ----------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = make_market_keyboard()
    await message.answer("Выберите маркет:", reply_markup=kb)

@dp.callback_query(F.data.startswith("market_"))
async def market_selected(query: types.CallbackQuery):
    name = query.data.replace("market_", "")
    cursor.execute("SELECT latitude, longitude FROM markets WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        lat, lon = row
        await query.message.answer_location(latitude=lat, longitude=lon)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Да", callback_data="choose_another"))
        await query.message.answer("Хотите выбрать другой маркет?", reply_markup=kb)
    await query.answer()

@dp.callback_query(F.data=="choose_another")
async def choose_another(query: types.CallbackQuery):
    kb = make_market_keyboard()
    await query.message.answer("Выберите маркет:", reply_markup=kb)
    await query.answer()

# ---------------------- АДМИН ----------------------
@dp.message(Command("import"))
async def cmd_import(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Отправьте Excel файл с маркетами (.xlsx)")
    await state.set_state(ImportStates.waiting_file)

@dp.message(F.document, ImportStates.waiting_file)
async def excel_upload(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    file = await message.document.download(destination_dir=".")
    import_markets_from_excel(file.name)
    await message.answer(f"Маркетов импортировано успешно: {len(fetch_all_markets())}")
    await state.clear()

@dp.message(Command("export"))
async def cmd_export(message: Message):
    if message.from_user.id not in ADMINS:
        return
    file_path = "markets_export.xlsx"
    export_markets_to_excel(file_path)
    await message.answer_document(types.InputFile(file_path))

# ---------------------- МЕНЮ ----------------------
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Выбрать маркет", callback_data="choose_another"))
    if message.from_user.id in ADMINS:
        kb.add(InlineKeyboardButton("Импорт маркетов", callback_data="admin_import"))
        kb.add(InlineKeyboardButton("Экспорт маркетов", callback_data="admin_export"))
    await message.answer("Меню:", reply_markup=kb)

# ---------------------- ЗАПУСК ----------------------
if __name__ == "__main__":
    logger.info("Стартуем бота...")
    dp.start_polling(bot)

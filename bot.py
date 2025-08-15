import logging
import sqlite3
import pandas as pd
import os
import asyncio

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import Bot, DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# === Настройки ===
TOKEN = "7294777489:AAFMvo3UvtnuOvpYyDIldCi0GuGyrTvyZHM"
DB_FILE = "markets.db"
EXCEL_FILE = "markets.xlsx"
ADMINS = [329116625, 866826839]  # сюда добавляешь своих админов

# === Логирование ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Бот ===
bot = Bot(
    token=TOKEN,
    session=AiohttpSession(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# === Инициализация базы ===
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    conn.commit()
    conn.close()

# === Проверка администратора ===
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# === Генерация клавиатуры с маркетами ===
def make_menu_keyboard():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM markets ORDER BY name")
    markets = cursor.fetchall()
    conn.close()

    buttons = []
    row = []
    for i, (name,) in enumerate(markets, start=1):
        row.append(InlineKeyboardButton(text=name, callback_data=f"market_{name}"))
        if i % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# === FSM для импорта Excel ===
class ImportStates(StatesGroup):
    waiting_file = State()

# === Импорт из Excel файла ===
def import_from_excel(file_path: str):
    if not os.path.exists(file_path):
        return False
    df = pd.read_excel(file_path)
    if not all(col in df.columns for col in ["name", "latitude", "longitude"]):
        return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM markets")
    for _, row in df.iterrows():
        cursor.execute(
            "INSERT INTO markets (name, latitude, longitude) VALUES (?, ?, ?)",
            (row["name"], row["latitude"], row["longitude"])
        )
    conn.commit()
    conn.close()
    return True

# === Экспорт в Excel ===
def export_to_excel():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT name, latitude, longitude FROM markets", conn)
    conn.close()
    df.to_excel(EXCEL_FILE, index=False)

# === Команды ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if is_admin(message.from_user.id):
        # Меню для админа
        commands_text = (
            "Привет! Дорогой админ.\n\n"
            "Доступные команды для Вас:\n"
            "/menu — список маркетов\n"
            "/import — импорт Excel\n"
            "/export — экспорт в Excel"
        )
    else:
        # Меню для обычного пользователя
        commands_text = (
            "Привет! Дорогой пользователь.\n\n"
            "Доступные команды для Вас:\n"
            "/menu — список маркетов"
        )

    await message.answer(commands_text)

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    kb = make_menu_keyboard()
    await message.answer("Выберите маркет:", reply_markup=kb)

@dp.message(Command("import"))
async def cmd_import(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    await message.answer("Отправьте файл Excel для импорта маркетов (.xlsx)")
    await state.set_state(ImportStates.waiting_file)

@dp.message(Command("export"))
async def cmd_export(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return
    export_to_excel()
    file = FSInputFile(EXCEL_FILE)
    await message.answer_document(file)

# === Обработка присланного Excel файла ===
@dp.message(F.document, ImportStates.waiting_file)
async def excel_upload(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        await state.clear()
        return
    if not message.document.file_name.lower().endswith(".xlsx"):
        await message.answer("❌ Можно отправлять только файлы .xlsx")
        return

    file_info = await bot.get_file(message.document.file_id)
    file_path = f"temp_{message.document.file_name}"
    await bot.download_file(file_info.file_path, destination=file_path)

    if import_from_excel(file_path):
        await message.answer("✅ Импорт завершён!")
        kb = make_menu_keyboard()
        await message.answer("Обновлённый список маркетов:", reply_markup=kb)
    else:
        await message.answer("❌ Ошибка при импорте. Проверьте колонки name, latitude, longitude.")

    os.remove(file_path)
    await state.clear()

# === Обработка выбора маркета ===
@dp.callback_query(F.data.startswith("market_"))
async def process_market(callback: CallbackQuery):
    market_name = callback.data.replace("market_", "")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT latitude, longitude FROM markets WHERE name=?", (market_name,))
    result = cursor.fetchone()
    conn.close()

    if result:
        lat, lon = result
        await callback.message.answer_location(latitude=lat, longitude=lon)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, показать другие маркеты", callback_data="show_menu")]
        ])
        await callback.message.answer("Хотите увидеть другие маркеты?", reply_markup=kb)
    else:
        await callback.message.answer("Маркет не найден.")

    # Убираем старые кнопки
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

# === Обработка кнопки "Показать другие маркеты" ===
@dp.callback_query(F.data == "show_menu")
async def show_menu(callback: CallbackQuery):
    kb = make_menu_keyboard()
    await callback.message.answer("Выберите маркет:", reply_markup=kb)
    await callback.answer()

# === Запуск ===
async def main():
    init_db()
    logger.info("Стартуем бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

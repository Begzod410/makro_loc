import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from dotenv import load_dotenv
from db import init_db, add_shop, get_shops, delete_all_shops, import_from_excel, export_to_excel

# Загружаем .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env")

# Логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())


# === Состояния ===
class AddShop(StatesGroup):
    waiting_for_name = State()
    waiting_for_location = State()


# === Старт ===
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📍 Маркеты")
    if message.from_user.id in ADMINS:
        kb.add("➕ Добавить маркет", "📤 Экспорт", "📥 Импорт")
    await message.answer("Добро пожаловать в бота сети магазинов!", reply_markup=kb)


# === Вывод списка магазинов ===
@dp.message(lambda msg: msg.text == "📍 Маркеты")
async def show_shops(message: types.Message):
    shops = await get_shops()
    if not shops:
        await message.answer("❌ Магазины пока не добавлены")
        return

    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for shop in shops:
        kb.add(KeyboardButton(shop["name"]))
    kb.add("⬅️ Назад")

    await message.answer("📍 Выберите магазин:", reply_markup=kb)


# === Отправка геолокации магазина ===
@dp.message()
async def send_location(message: types.Message):
    shops = await get_shops()
    for shop in shops:
        if message.text == shop["name"]:
            await message.answer_location(latitude=shop["latitude"], longitude=shop["longitude"])
            return


# === Добавление магазина (только для админов) ===
@dp.message(lambda msg: msg.text == "➕ Добавить маркет")
async def add_shop_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")
    await state.set_state(AddShop.waiting_for_name)
    await message.answer("Введите название маркета:")


@dp.message(AddShop.waiting_for_name)
async def add_shop_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddShop.waiting_for_location)
    kb = ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("📍 Отправить локацию", request_location=True)
    )
    await message.answer("Теперь отправьте локацию магазина:", reply_markup=kb)


@dp.message(AddShop.waiting_for_location)
async def add_shop_location(message: types.Message, state: FSMContext):
    if not message.location:
        return await message.answer("❌ Пожалуйста, отправьте локацию кнопкой.")

    data = await state.get_data()
    name = data["name"]
    lat = message.location.latitude
    lon = message.location.longitude

    await add_shop(name, lat, lon)
    await state.clear()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📍 Маркеты")
    if message.from_user.id in ADMINS:
        kb.add("➕ Добавить маркет", "📤 Экспорт", "📥 Импорт")

    await message.answer(f"✅ Маркет <b>{name}</b> добавлен!", reply_markup=kb)


# === Экспорт в Excel (только админы) ===
@dp.message(lambda msg: msg.text == "📤 Экспорт")
async def export_shops(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")

    file_path = await export_to_excel()
    await message.answer_document(types.FSInputFile(file_path))


# === Импорт из Excel (только админы) ===
@dp.message(lambda msg: msg.text == "📥 Импорт")
async def import_shops(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")

    await message.answer("📎 Отправьте Excel-файл с магазинами (xlsx):")


@dp.message(lambda msg: msg.document and msg.from_user.id in ADMINS)
async def handle_import_file(message: types.Message):
    file = await bot.download(message.document)
    await delete_all_shops()
    await import_from_excel(file.name)
    await message.answer("✅ Магазины успешно импортированы (БД полностью заменена)")


# === Запуск ===
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

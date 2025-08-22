import os
import asyncpg
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)


async def init_db():
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL
        )
        """)
    await pool.close()


async def add_shop(name, latitude, longitude):
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO shops (name, latitude, longitude) VALUES ($1, $2, $3)", name, latitude, longitude)
    await pool.close()


async def get_shops():
    pool = await create_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM shops")
    await pool.close()
    return [dict(r) for r in rows]


async def delete_all_shops():
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE shops")
    await pool.close()


async def export_to_excel():
    shops = await get_shops()
    df = pd.DataFrame(shops)
    file_path = "shops_export.xlsx"
    df.to_excel(file_path, index=False)
    return file_path


async def import_from_excel(file_path):
    df = pd.read_excel(file_path)
    pool = await create_pool()
    async with pool.acquire() as conn:
        for _, row in df.iterrows():
            await conn.execute("INSERT INTO shops (name, latitude, longitude) VALUES ($1, $2, $3)",
                               row["name"], row["latitude"], row["longitude"])
    await pool.close()

import os
import asyncio
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        # Ensure using asyncpg driver if not specified
        if self.db_url.startswith("postgresql://"):
             self.db_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://")
             
        self.engine = create_async_engine(self.db_url, echo=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            # Users table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Questions table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    user_name TEXT NOT NULL,
                    presenter_name TEXT NOT NULL,
                    question TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
                )
            """))

            # Presenters table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS presenters (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    title TEXT,
                    start_time TEXT,
                    end_time TEXT
                )
            """))
            
        await self.seed_presenters()

    async def seed_presenters(self):
        presenters_data = [
            {"name": "آیدین طباطبایی", "title": "اوپن‌سورس در توسعه‌ی سرویس‌های ابری", "start_time": "12:00", "end_time": "12:15"},
            {"name": "محمدحسن اکبری", "title": "چگونه در جامعه‌ی متن‌باز مشارکت کنیم؟", "start_time": "12:15", "end_time": "12:45"},
            {"name": "محمد عابدینی", "title": "تفاوت لین BSD و Linux", "start_time": "12:50", "end_time": "13:20"},
            {"name": "امیرعباس قاسمی", "title": "جراحی بدون درد کد با Codemod", "start_time": "14:50", "end_time": "15:20"},
            {"name": "امیرکبیری", "title": "از ایده تا پکیج npm", "start_time": "15:30", "end_time": "16:00"},
            {"name": "وصال ژولانژاد", "title": "چرا و چگونه لینوکس به راست مهاجرت می‌کند؟", "start_time": "16:30", "end_time": "17:00"},
            {"name": "مهدی ملاکی", "title": "چگونگی کشف آسیب‌پذیری نرم‌افزاری در دواپس", "start_time": "17:00", "end_time": "17:30"},
        ]
        
        async with self.engine.begin() as conn:
            for p in presenters_data:
                # Upsert
                await conn.execute(text("""
                    INSERT INTO presenters (name, title, start_time, end_time) 
                    VALUES (:name, :title, :start_time, :end_time)
                    ON CONFLICT (name) DO UPDATE 
                    SET title = EXCLUDED.title, 
                        start_time = EXCLUDED.start_time, 
                        end_time = EXCLUDED.end_time
                """), p)

    async def register_user(self, telegram_id: int, name: str, email: str, is_admin: bool = False) -> bool:
        try:
            async with self.engine.begin() as conn:
                # Check if user exists
                result = await conn.execute(text("SELECT is_admin FROM users WHERE telegram_id = :id"), {"id": telegram_id})
                existing = result.fetchone()

                if existing:
                    await conn.execute(text("""
                        UPDATE users SET name = :name, email = :email WHERE telegram_id = :id
                    """), {"name": name, "email": email, "id": telegram_id})
                else:
                    await conn.execute(text("""
                        INSERT INTO users (telegram_id, name, email, is_admin) 
                        VALUES (:id, :name, :email, :is_admin)
                    """), {"id": telegram_id, "name": name, "email": email, "is_admin": is_admin})
            return True
        except Exception as e:
            print(f"Error registering user: {e}")
            return False

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT telegram_id, name, email, is_admin FROM users WHERE telegram_id = :id
            """), {"id": telegram_id})
            row = result.fetchone()
            
            if row:
                return {
                    "telegram_id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "is_admin": row[3]
                }
            return None

    async def add_presenter(self, name: str, title: str = None, start_time: str = None, end_time: str = None) -> bool:
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO presenters (name, title, start_time, end_time) 
                    VALUES (:name, :title, :start_time, :end_time)
                    ON CONFLICT (name) DO NOTHING
                """), {"name": name, "title": title, "start_time": start_time, "end_time": end_time})
            return True
        except Exception as e:
            print(f"Error adding presenter: {e}")
            return False

    async def get_presenters(self) -> List[Dict]:
        async with self.engine.connect() as conn:
            result = await conn.execute(text("SELECT name, title, start_time, end_time FROM presenters ORDER BY start_time, name"))
            presenters = []
            for row in result.fetchall():
                presenters.append({
                    "name": row[0],
                    "title": row[1],
                    "start_time": row[2],
                    "end_time": row[3]
                })
            return presenters

    async def add_question(self, telegram_id: int, user_name: str, presenter_name: str, question: str) -> bool:
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO questions (telegram_id, user_name, presenter_name, question) 
                    VALUES (:telegram_id, :user_name, :presenter_name, :question)
                """), {
                    "telegram_id": telegram_id, 
                    "user_name": user_name, 
                    "presenter_name": presenter_name, 
                    "question": question
                })
            return True
        except Exception as e:
            print(f"Error adding question: {e}")
            return False

    async def get_questions(self, presenter_name: Optional[str] = None, user_name: Optional[str] = None) -> List[Dict]:
        async with self.engine.connect() as conn:
            query = "SELECT id, user_name, presenter_name, question, created_at FROM questions WHERE 1=1"
            params = {}

            if presenter_name:
                query += " AND presenter_name = :presenter_name"
                params["presenter_name"] = presenter_name

            if user_name:
                query += " AND user_name LIKE :user_name"
                params["user_name"] = f"%{user_name}%"

            query += " ORDER BY created_at DESC"

            result = await conn.execute(text(query), params)
            questions = []
            for row in result.fetchall():
                questions.append({
                    "id": row[0],
                    "user_name": row[1],
                    "presenter_name": row[2],
                    "question": row[3],
                    "created_at": row[4]
                })
            return questions

    async def is_admin(self, telegram_id: int) -> bool:
        user = await self.get_user(telegram_id)
        return user.get('is_admin', False) if user else False

    async def set_admin(self, telegram_id: int, is_admin: bool) -> bool:
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("""
                    UPDATE users SET is_admin = :is_admin WHERE telegram_id = :id
                """), {"is_admin": is_admin, "id": telegram_id})
                return result.rowcount > 0
        except Exception as e:
            print(f"Error setting admin status: {e}")
            return False

    async def get_all_users(self) -> List[Dict]:
        async with self.engine.connect() as conn:
            result = await conn.execute(text("SELECT telegram_id, name, email, is_admin FROM users ORDER BY name"))
            users = []
            for row in result.fetchall():
                users.append({
                    "telegram_id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "is_admin": row[3]
                })
            return users

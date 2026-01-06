import os
import asyncio
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, BigInteger, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    telegram_id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String, unique=True, nullable=False)
    best_rmse = Column(Float, nullable=True, default=float('inf'))
    submission_count = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")

class Submission(Base):
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    rmse = Column(Float, nullable=False)
    file_name = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="submissions")

class Config(Base):
    __tablename__ = 'config'
    key = Column(String, primary_key=True)
    value = Column(String)

class AllowedUser(Base):
    __tablename__ = 'allowed_users'
    full_name = Column(String, primary_key=True)
    added_at = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        # Ensure using asyncpg driver
        if self.db_url.startswith("postgresql://"):
             self.db_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://")
             
        self.engine = create_async_engine(self.db_url, echo=False)
        self.SessionLocal = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # Seed initial whitelist if empty
        async with self.SessionLocal() as session:
            # Check if any AllowedUser exists
            result = await session.execute(select(AllowedUser))
            if not result.scalars().first():
                initial_list = [
                    "محمد هادی گلی بیدگلی", "شایان گنجی", "سهیل نوحی", "مرضیه معتمدنیا", "پارمیدا هدایتی"
                ]
                for name in initial_list:
                    session.add(AllowedUser(full_name=name))
                await session.commit()
            
    async def get_session(self) -> AsyncSession:
        return self.SessionLocal()
        
    async def get_user(self, telegram_id: int) -> Optional[User]:
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            return result.scalars().first()

    async def create_user(self, telegram_id: int, full_name: str, is_admin: bool = False):
        async with self.SessionLocal() as session:
            new_user = User(telegram_id=telegram_id, full_name=full_name, is_admin=is_admin)
            session.add(new_user)
            await session.commit()
            return new_user

    async def add_submission(self, telegram_id: int, rmse: float, file_name: str):
        async with self.SessionLocal() as session:
            # Check for freeze
            config = await session.get(Config, "competition_frozen")
            if config and config.value == "true":
                 raise Exception("Competition is currently frozen.")

            # Add submission
            new_sub = Submission(user_id=telegram_id, rmse=rmse, file_name=file_name)
            session.add(new_sub)
            
            # Update User stats
            user = await session.get(User, telegram_id)
            if user:
                user.submission_count += 1
                if rmse < user.best_rmse:
                    user.best_rmse = rmse
            
            await session.commit()
            return user.best_rmse

    async def get_leaderboard(self, limit: int = 10):
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(User)
                .where(User.best_rmse != float('inf'))
                .order_by(User.best_rmse.asc())
                .limit(limit)
            )
            return result.scalars().all()
            
    async def get_user_rank(self, telegram_id: int):
        async with self.SessionLocal() as session:
            user = await session.get(User, telegram_id)
            if not user or user.best_rmse == float('inf'):
                return None
            query = select(User).where(User.best_rmse < user.best_rmse)
            result = await session.execute(query)
            return len(result.scalars().all()) + 1
            
    async def get_all_users(self):
        async with self.SessionLocal() as session:
            result = await session.execute(select(User))
            return result.scalars().all()

    # --- Admin Config Methods ---
    async def set_config(self, key: str, value: str):
        async with self.SessionLocal() as session:
            conf = await session.get(Config, key)
            if not conf:
                conf = Config(key=key, value=value)
                session.add(conf)
            else:
                conf.value = value
            await session.commit()
            
    async def get_config(self, key: str) -> Optional[str]:
        async with self.SessionLocal() as session:
            conf = await session.get(Config, key)
            return conf.value if conf else None

    # --- Whitelist Methods ---
    async def is_whitelisted(self, full_name: str) -> bool:
        async with self.SessionLocal() as session:
            user = await session.get(AllowedUser, full_name)
            return user is not None
            
    async def add_allowed_user(self, full_name: str):
        async with self.SessionLocal() as session:
            if not await session.get(AllowedUser, full_name):
                session.add(AllowedUser(full_name=full_name))
                await session.commit()

    async def remove_allowed_user(self, full_name: str):
        async with self.SessionLocal() as session:
            user = await session.get(AllowedUser, full_name)
            if user:
                await session.delete(user)
                await session.commit()

# Singleton instance
db = Database()
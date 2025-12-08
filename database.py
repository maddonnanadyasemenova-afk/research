import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict

DATABASE_PATH = "bot_database.db"

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance_rubles INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица исследований
        await db.execute("""
            CREATE TABLE IF NOT EXISTS researches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                research_type TEXT,
                research_name TEXT,
                user_input TEXT,
                result TEXT,
                price_rubles INTEGER,
                status TEXT DEFAULT 'processing',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        """)
        
        # Таблица транзакций
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                amount_rubles INTEGER,
                transaction_type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        """)
        
        await db.commit()

async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, initial_bonus: int = 0) -> Dict:
    """Получить или создать пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Проверяем существование пользователя
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            user = await cursor.fetchone()
        
        if user:
            # Обновляем время последней активности
            await db.execute(
                "UPDATE users SET last_active = ? WHERE telegram_id = ?",
                (datetime.now(), telegram_id)
            )
            await db.commit()
            return dict(user)
        else:
            # Создаем нового пользователя с бонусом
            await db.execute(
                """INSERT INTO users (telegram_id, username, first_name, balance_rubles) 
                   VALUES (?, ?, ?, ?)""",
                (telegram_id, username, first_name, initial_bonus)
            )
            
            # Записываем транзакцию бонуса
            if initial_bonus > 0:
                await db.execute(
                    """INSERT INTO transactions (telegram_id, amount_rubles, transaction_type, description)
                       VALUES (?, ?, ?, ?)""",
                    (telegram_id, initial_bonus, 'bonus', 'Приветственный бонус')
                )
            
            await db.commit()
            
            # Возвращаем созданного пользователя
            async with db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                user = await cursor.fetchone()
                return dict(user)

async def get_user_balance(telegram_id: int) -> int:
    """Получить баланс пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT balance_rubles FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def update_balance(telegram_id: int, amount: int, transaction_type: str, description: str):
    """Обновить баланс пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET balance_rubles = balance_rubles + ? WHERE telegram_id = ?",
            (amount, telegram_id)
        )
        
        await db.execute(
            """INSERT INTO transactions (telegram_id, amount_rubles, transaction_type, description)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, amount, transaction_type, description)
        )
        
        await db.commit()

async def create_research(
    telegram_id: int,
    research_type: str,
    research_name: str,
    user_input: str,
    price_rubles: int
) -> int:
    """Создать новое исследование"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO researches (telegram_id, research_type, research_name, user_input, price_rubles, status)
               VALUES (?, ?, ?, ?, ?, 'processing')""",
            (telegram_id, research_type, research_name, user_input, price_rubles)
        )
        research_id = cursor.lastrowid
        
        # Списываем баллы
        await db.execute(
            "UPDATE users SET balance_rubles = balance_rubles - ? WHERE telegram_id = ?",
            (price_rubles, telegram_id)
        )
        
        await db.execute(
            """INSERT INTO transactions (telegram_id, amount_rubles, transaction_type, description)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, -price_rubles, 'research', f'Исследование: {research_name}')
        )
        
        await db.commit()
        return research_id

async def update_research_result(research_id: int, result: str, status: str = 'completed'):
    """Обновить результат исследования"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE researches 
               SET result = ?, status = ?, completed_at = ?
               WHERE id = ?""",
            (result, status, datetime.now(), research_id)
        )
        await db.commit()

async def get_user_researches(telegram_id: int, limit: int = 10) -> List[Dict]:
    """Получить список исследований пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM researches 
               WHERE telegram_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (telegram_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_research_by_id(research_id: int) -> Optional[Dict]:
    """Получить исследование по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM researches WHERE id = ?", (research_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_transactions(telegram_id: int, limit: int = 10) -> List[Dict]:
    """Получить историю транзакций пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM transactions 
               WHERE telegram_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (telegram_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

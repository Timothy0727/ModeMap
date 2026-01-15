# backend/test_db_connection.py (temporary test file)
import asyncio
from app.db.session import get_db
from sqlalchemy import text
from app.models import Venue

async def test_db():
    async for session in get_db():
        result = await session.execute(text("SELECT COUNT(*) FROM venues"))
        count = result.scalar()
        print(f"✅ Database connected! Venues table exists with {count} rows.")

if __name__ == "__main__":
    asyncio.run(test_db())
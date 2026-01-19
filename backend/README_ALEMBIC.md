# Alembic Setup Guide

Alembic has been configured to work with your async SQLAlchemy models.

## Creating Your First Migration

1. **Make sure your database is running:**
   ```bash
   docker-compose up -d postgres
   ```

2. **Create the initial migration:**
   ```bash
   cd backend
   alembic revision --autogenerate -m "Initial migration"
   ```

   This will:
   - Scan all your models in `app/models/`
   - Compare them to the current database state
   - Generate a migration file in `alembic/versions/`

3. **Review the generated migration:**
   - Check the file in `alembic/versions/` to ensure it looks correct
   - The migration will create tables for: `venues`, `venue_profiles`, `user_events`

4. **Apply the migration:**
   ```bash
   alembic upgrade head
   ```

   This will execute the SQL to create all tables in PostgreSQL.

## Common Commands

- **Create a new migration:** `alembic revision --autogenerate -m "description"`
- **Apply migrations:** `alembic upgrade head`
- **Rollback one migration:** `alembic downgrade -1`
- **Show current revision:** `alembic current`
- **Show migration history:** `alembic history`

## Troubleshooting

- **If models aren't detected:** Make sure all models are imported in `alembic/env.py`
- **If database connection fails:** Check that `DATABASE_URL` in your `.env` or `config.py` is correct
- **If you get async errors:** Make sure you're using the async-compatible Alembic setup (already configured)

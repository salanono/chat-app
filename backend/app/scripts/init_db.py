# backend/app/scripts/init_db.py
import asyncio
from sqlalchemy import select
from app import models
from app.db import engine, AsyncSessionLocal
from app.auth import get_password_hash

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "password"
COMPANY_NAME = "Demo Company"

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    print("✅ DB tables created")

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Company).where(models.Company.name == COMPANY_NAME))
        company = res.scalar_one_or_none()
        if not company:
            company = models.Company(name=COMPANY_NAME)
            db.add(company)
            await db.flush()
            print("✅ created company", company.id)
        else:
            print("↩️ company exists", company.id)

        res = await db.execute(select(models.User).where(models.User.email == ADMIN_EMAIL))
        user = res.scalar_one_or_none()
        if not user:
            user = models.User(
                email=ADMIN_EMAIL,
                password_hash=get_password_hash(ADMIN_PASSWORD),
                display_name="Admin",
                role="ADMIN",
                company_id=company.id,
            )
            db.add(user)
            await db.flush()
            print("✅ created user", user.id)
        else:
            print("↩️ user exists", user.id)

        await db.commit()

if __name__ == "__main__":
    asyncio.run(main())
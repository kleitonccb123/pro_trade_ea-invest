from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL.replace('+aiosqlite', '')  # sync version
engine = create_engine(DATABASE_URL, future=True)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)
    print("? Tabelas criadas com sucesso no SQLite!")

if __name__ == "__main__":
    init_db()
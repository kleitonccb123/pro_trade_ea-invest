import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

# Force SQLite URL
DATABASE_URL = "sqlite:///./dev.db"
engine = create_engine(DATABASE_URL, future=True)
Base = declarative_base()

def init_db():
    # Delete old DB if exists
    if os.path.exists("dev.db"):
        os.remove("dev.db")
        print("??  Old dev.db deleted.")

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("? Tables created successfully in SQLite!")

if __name__ == "__main__":
    init_db()

from app.db import engine
from app.models import Base

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

    for table_name in Base.metadata.tables:
        print(f"- {table_name}")

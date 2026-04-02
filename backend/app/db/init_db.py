from app.db.base_class import Base
from app.db.database import engine

def init_db() -> None:
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
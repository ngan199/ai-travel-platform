from app.db.base_class import Base
from app.db.database import engine

def init_db() -> None:
    import app.models  # load all model classes
    Base.metadata.create_all(bind=engine)

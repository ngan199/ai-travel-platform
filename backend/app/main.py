from fastapi import FastAPI
from contextlib import asynccontextmanager

# Database
from app.db.database import Base, engine

# Models
from app.models import user as user_model

# Routers
from app.api import user as user_router


# Lifespan handler (replaces on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Travel AI Platform...")

    # Startup logic
    Base.metadata.create_all(bind=engine)

    yield

    # Shutdown logic (optional)
    print("🛑 Shutting down Travel AI Platform...")


# Initialize app with lifespan
app = FastAPI(
    title="Travel AI Platform",
    lifespan=lifespan
)


# Routes
@app.get("/")
def root():
    return {"message": "Travel AI Platform is running 🚀"}


# Register routers
app.include_router(user_router.router, prefix="/api", tags=["Users"])
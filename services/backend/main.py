import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend orchestration services for the Smart Campus Agent System.",
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS configuration to allow local Next.js client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open in development; narrow down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API endpoints
app.mount("/api", app)  # Sub-mount api to support /api paths directly
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Campus Ops Backend API."}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

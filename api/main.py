
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Personal Productivity Assistant API",
    description="API interface for the PPA agent.",
    version="1.0.0",
)

# Development origins for the Vite frontend.
# We will replace/configure these through environment
# settings before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "Personal Productivity Assistant",
        "version": "1.0.0",
    }

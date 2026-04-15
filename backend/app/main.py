"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.clip_service import clip_service
from app.config import settings
from app.rate_limit import limiter
from app.routers import admin_settings as admin_settings_router
from app.routers import activity as activity_router
from app.routers import art_of_the_day as art_of_the_day_router
from app.routers import artists as artists_router
from app.routers import artworks as artworks_router
from app.routers import auth as auth_router
from app.routers import challenges as challenges_router
from app.routers import comments as comments_router
from app.routers import favorites as favorites_router
from app.routers import follows as follows_router
from app.routers import homepage as homepage_router
from app.routers import leaderboard as leaderboard_router
from app.routers import messages as messages_router
from app.routers import moderation as moderation_router
from app.routers import neighborhoods as neighborhoods_router
from app.routers import notifications as notifications_router
from app.routers import photos as photos_router
from app.routers import search as search_router
from app.routers import users as users_router
from app.routers import walking_tours as walking_tours_router
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Loads the CLIP model at startup so it is ready for photo upload
    embedding computation and the /api/photos/match endpoint.
    """
    try:
        logger.info("Loading CLIP model (ViT-B-16, laion2b_s34b_b88k)...")
        clip_service.load()
        logger.info("CLIP model loaded successfully.")
    except Exception:
        logger.warning(
            "Failed to load CLIP model. Image matching will be unavailable.",
            exc_info=True,
        )
    yield


app = FastAPI(title="DuvarSanat API", version="0.1.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    """Return a 429 response when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down."},
    )


# CORS - allow configured origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Ensure uploads directory exists and mount it for static file serving
uploads_path = Path(settings.UPLOAD_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# Routers
app.include_router(art_of_the_day_router.router)
app.include_router(homepage_router.router)
app.include_router(neighborhoods_router.router)
app.include_router(auth_router.router)
app.include_router(photos_router.router)
app.include_router(comments_router.router)
app.include_router(favorites_router.router)
app.include_router(follows_router.router)
app.include_router(leaderboard_router.router)
app.include_router(moderation_router.router)
app.include_router(search_router.router)
app.include_router(challenges_router.router)
app.include_router(notifications_router.router)
app.include_router(walking_tours_router.router)
app.include_router(artworks_router.router)
app.include_router(artists_router.router)
app.include_router(activity_router.router)
app.include_router(messages_router.router)
app.include_router(admin_settings_router.router)
app.include_router(users_router.router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

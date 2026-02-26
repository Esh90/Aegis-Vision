"""API route modules."""

from .stream import router as stream_router
from .watchlist import router as watchlist_router
from .video import router as video_router
from .misc import router as misc_router

__all__ = ["stream_router", "watchlist_router", "video_router", "misc_router"]

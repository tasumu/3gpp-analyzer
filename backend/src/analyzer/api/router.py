"""API router aggregation."""

from fastapi import APIRouter

from analyzer.api.documents import router as documents_router
from analyzer.api.internal import router as internal_router_impl
from analyzer.api.streaming import router as streaming_router

# Public API router
api_router = APIRouter()
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(streaming_router, tags=["streaming"])

# Internal API router (not exposed to public)
internal_router = APIRouter()
internal_router.include_router(internal_router_impl, tags=["internal"])

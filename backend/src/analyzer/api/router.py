"""API router aggregation."""

from fastapi import APIRouter

from analyzer.api.analysis import router as analysis_router
from analyzer.api.documents import router as documents_router
from analyzer.api.ftp import router as ftp_router
from analyzer.api.internal import router as internal_router_impl
from analyzer.api.streaming import router as streaming_router

# Public API router
api_router = APIRouter()
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(streaming_router, tags=["streaming"])
api_router.include_router(ftp_router, tags=["ftp"])
api_router.include_router(analysis_router, tags=["analysis"])

# Internal API router (not exposed to public)
internal_router = APIRouter()
internal_router.include_router(internal_router_impl, tags=["internal"])

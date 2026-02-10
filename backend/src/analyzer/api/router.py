"""API router aggregation."""

from fastapi import APIRouter

from analyzer.api.admin import router as admin_router
from analyzer.api.analysis import router as analysis_router
from analyzer.api.auth import router as auth_router
from analyzer.api.custom_analysis import router as custom_analysis_router
from analyzer.api.documents import router as documents_router
from analyzer.api.ftp import router as ftp_router
from analyzer.api.internal import router as internal_router_impl
from analyzer.api.meeting import router as meeting_router
from analyzer.api.qa import router as qa_router
from analyzer.api.report_prompts import router as report_prompts_router
from analyzer.api.streaming import router as streaming_router

# Public API router
api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(streaming_router, tags=["streaming"])
api_router.include_router(ftp_router, tags=["ftp"])
api_router.include_router(analysis_router, tags=["analysis"])
api_router.include_router(custom_analysis_router, tags=["custom-analysis"])
api_router.include_router(report_prompts_router, tags=["report-prompts"])
api_router.include_router(qa_router, tags=["qa"])
api_router.include_router(meeting_router, tags=["meeting"])

# Internal API router (not exposed to public)
internal_router = APIRouter()
internal_router.include_router(internal_router_impl, tags=["internal"])

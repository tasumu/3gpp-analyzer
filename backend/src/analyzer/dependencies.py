"""Dependency injection for FastAPI."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException

from analyzer.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_no_approval_check,
)
from analyzer.config import Settings, get_settings
from analyzer.models.user import User, UserRole
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.firestore_provider import FirestoreEvidenceProvider
from analyzer.providers.storage_client import StorageClient
from analyzer.services.analysis_service import AnalysisService
from analyzer.services.attachment_service import AttachmentService
from analyzer.services.custom_prompt_service import CustomPromptService
from analyzer.services.document_service import DocumentService
from analyzer.services.ftp_sync import FTPSyncService
from analyzer.services.meeting_report_generator import MeetingReportGenerator
from analyzer.services.meeting_service import MeetingService
from analyzer.services.normalizer import NormalizerService
from analyzer.services.processor import ProcessorService
from analyzer.services.qa_service import QAService
from analyzer.services.report_prompt_service import ReportPromptService
from analyzer.services.user_service import UserService
from analyzer.services.vectorizer import VectorizerService


@lru_cache
def get_firestore_client() -> FirestoreClient:
    """Get cached Firestore client."""
    settings = get_settings()
    return FirestoreClient(
        project_id=settings.gcp_project_id,
        use_emulator=settings.use_firebase_emulator,
        emulator_host=settings.firestore_emulator_host,
    )


@lru_cache
def get_storage_client() -> StorageClient:
    """Get cached Storage client."""
    settings = get_settings()
    return StorageClient(
        bucket_name=settings.gcs_bucket_name,
        use_emulator=settings.use_firebase_emulator,
        emulator_host=settings.storage_emulator_host,
    )


def get_evidence_provider(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvidenceProvider:
    """Get EvidenceProvider instance."""
    return FirestoreEvidenceProvider(
        firestore=firestore,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
    )


def get_document_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    storage: Annotated[StorageClient, Depends(get_storage_client)],
) -> DocumentService:
    """Get DocumentService instance."""
    return DocumentService(firestore=firestore, storage=storage)


def get_ftp_sync_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    storage: Annotated[StorageClient, Depends(get_storage_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FTPSyncService:
    """Get FTPSyncService instance."""
    return FTPSyncService(
        firestore=firestore,
        storage=storage,
        host=settings.ftp_host,
        user=settings.ftp_user,
        password=settings.ftp_password,
        base_path=settings.ftp_base_path,
        mock_mode=settings.ftp_mock_mode,
    )


def get_normalizer_service(
    storage: Annotated[StorageClient, Depends(get_storage_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> NormalizerService:
    """Get NormalizerService instance."""
    return NormalizerService(
        storage=storage,
        timeout=settings.libreoffice_timeout,
    )


def get_vectorizer_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorizerService:
    """Get VectorizerService instance."""
    return VectorizerService(
        firestore=firestore,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )


def get_processor_service(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    ftp_sync: Annotated[FTPSyncService, Depends(get_ftp_sync_service)],
    normalizer: Annotated[NormalizerService, Depends(get_normalizer_service)],
    vectorizer: Annotated[VectorizerService, Depends(get_vectorizer_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessorService:
    """Get ProcessorService instance."""
    return ProcessorService(
        document_service=document_service,
        ftp_sync=ftp_sync,
        normalizer=normalizer,
        vectorizer=vectorizer,
        chunk_max_tokens=settings.chunk_max_tokens,
    )


def get_analysis_service(
    evidence_provider: Annotated[EvidenceProvider, Depends(get_evidence_provider)],
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    """Get AnalysisService instance."""
    return AnalysisService(
        evidence_provider=evidence_provider,
        firestore=firestore,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        model=settings.analysis_model,
        strategy_version=settings.analysis_strategy_version,
    )


def get_custom_prompt_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
) -> CustomPromptService:
    """Get CustomPromptService instance."""
    return CustomPromptService(firestore=firestore)


def get_report_prompt_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
) -> ReportPromptService:
    """Get ReportPromptService instance."""
    return ReportPromptService(firestore=firestore)


def get_attachment_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    storage: Annotated[StorageClient, Depends(get_storage_client)],
) -> AttachmentService:
    """Get AttachmentService instance."""
    return AttachmentService(firestore=firestore, storage=storage)


def get_qa_service(
    evidence_provider: Annotated[EvidenceProvider, Depends(get_evidence_provider)],
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    storage: Annotated[StorageClient, Depends(get_storage_client)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QAService:
    """Get QAService instance."""
    return QAService(
        evidence_provider=evidence_provider,
        firestore=firestore,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        model=settings.qa_model,
        document_service=document_service,
        attachment_service=attachment_service,
        storage=storage,
    )


def get_meeting_service(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeetingService:
    """Get MeetingService instance."""
    return MeetingService(
        document_service=document_service,
        analysis_service=analysis_service,
        firestore=firestore,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        pro_model=settings.meeting_pro_model,
        pro_model_location=settings.vertex_ai_location,
        strategy_version=settings.meeting_summary_strategy_version,
    )


def get_meeting_report_generator(
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
    evidence_provider: Annotated[EvidenceProvider, Depends(get_evidence_provider)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
    storage: Annotated[StorageClient, Depends(get_storage_client)],
    attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeetingReportGenerator:
    """Get MeetingReportGenerator instance."""
    return MeetingReportGenerator(
        meeting_service=meeting_service,
        evidence_provider=evidence_provider,
        document_service=document_service,
        firestore=firestore,
        storage=storage,
        project_id=settings.gcp_project_id,
        location=settings.vertex_ai_location,
        model=settings.meeting_pro_model,
        expiration_minutes=settings.review_sheet_expiration_minutes,
        attachment_service=attachment_service,
    )


def get_user_service(
    firestore: Annotated[FirestoreClient, Depends(get_firestore_client)],
) -> UserService:
    """Get UserService instance."""
    return UserService(firestore=firestore)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
FirestoreClientDep = Annotated[FirestoreClient, Depends(get_firestore_client)]
StorageClientDep = Annotated[StorageClient, Depends(get_storage_client)]
EvidenceProviderDep = Annotated[EvidenceProvider, Depends(get_evidence_provider)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
FTPSyncServiceDep = Annotated[FTPSyncService, Depends(get_ftp_sync_service)]
NormalizerServiceDep = Annotated[NormalizerService, Depends(get_normalizer_service)]
VectorizerServiceDep = Annotated[VectorizerService, Depends(get_vectorizer_service)]
ProcessorServiceDep = Annotated[ProcessorService, Depends(get_processor_service)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
CustomPromptServiceDep = Annotated[CustomPromptService, Depends(get_custom_prompt_service)]
ReportPromptServiceDep = Annotated[ReportPromptService, Depends(get_report_prompt_service)]
AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]
QAServiceDep = Annotated[QAService, Depends(get_qa_service)]
MeetingServiceDep = Annotated[MeetingService, Depends(get_meeting_service)]
MeetingReportGeneratorDep = Annotated[MeetingReportGenerator, Depends(get_meeting_report_generator)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]

# Authentication dependencies
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
CurrentUserNoApprovalDep = Annotated[AuthenticatedUser, Depends(get_current_user_no_approval_check)]


async def require_admin(
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
) -> User:
    """
    Require admin privileges.

    Raises:
        HTTPException: 403 if user is not an admin
    """
    user = await user_service.get_user(current_user.uid)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )
    return user


AdminUserDep = Annotated[User, Depends(require_admin)]

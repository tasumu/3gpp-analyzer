"""Dependency injection for FastAPI."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from analyzer.config import Settings, get_settings
from analyzer.providers.base import EvidenceProvider
from analyzer.providers.firestore_client import FirestoreClient
from analyzer.providers.firestore_provider import FirestoreEvidenceProvider
from analyzer.providers.storage_client import StorageClient
from analyzer.services.document_service import DocumentService
from analyzer.services.ftp_sync import FTPSyncService
from analyzer.services.normalizer import NormalizerService
from analyzer.services.processor import ProcessorService
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
        embedding_model=settings.embedding_model,
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
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )


def get_processor_service(
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    normalizer: Annotated[NormalizerService, Depends(get_normalizer_service)],
    vectorizer: Annotated[VectorizerService, Depends(get_vectorizer_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessorService:
    """Get ProcessorService instance."""
    return ProcessorService(
        document_service=document_service,
        normalizer=normalizer,
        vectorizer=vectorizer,
        chunk_max_tokens=settings.chunk_max_tokens,
    )


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

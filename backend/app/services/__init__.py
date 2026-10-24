from app.services.ocr_service import ocr_service, OCRService
from app.services.invoice_extraction_service import invoice_extraction_service, InvoiceExtractionService
from app.services.validation_service import validation_service, ValidationService
from app.services.duplicate_detection_service import duplicate_detection_service, DuplicateDetectionService
from app.services.fraud_detection_service import fraud_detection_service, FraudDetectionService
from app.services.encryption_service import encryption_service, EncryptionService
from app.services.cloud_storage_service import cloud_storage_service, CloudStorageService

__all__ = [
    "ocr_service", "OCRService",
    "invoice_extraction_service", "InvoiceExtractionService",
    "validation_service", "ValidationService",
    "duplicate_detection_service", "DuplicateDetectionService",
    "fraud_detection_service", "FraudDetectionService",
    "encryption_service", "EncryptionService",
    "cloud_storage_service", "CloudStorageService"
]

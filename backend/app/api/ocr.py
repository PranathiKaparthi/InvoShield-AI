from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.api.deps import get_current_user
from app.models.entities import User
from app.services.ocr_service import ocr_service
from app.services.invoice_extraction_service import invoice_extraction_service

router = APIRouter(prefix="/api/ocr", tags=["OCR Processing"])

@router.post("/process")
async def process_ocr(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Direct OCR endpoint returning extracted text, confidence, and parsed fields."""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    text, confidence = ocr_service.extract_text_and_confidence(file_bytes, file.filename)
    extracted = invoice_extraction_service.extract(text, base_confidence=confidence)

    return {
        "filename": file.filename,
        "extracted_text": text,
        "ocr_confidence": confidence,
        "parsed_data": extracted
    }

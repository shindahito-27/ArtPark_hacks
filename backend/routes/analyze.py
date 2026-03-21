from fastapi import APIRouter, File, HTTPException, UploadFile

from ..services.pipeline_service import analyze_resume


router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _get_extension(filename: str) -> str:
    return "." + filename.split(".")[-1].lower() if "." in filename else ""


@router.post("/analyze")
async def analyze(file: UploadFile = File(...), job_description: UploadFile | None = File(None)) -> dict:
    filename = file.filename or ""
    extension = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are allowed.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    jd_filename: str | None = None
    jd_file_bytes: bytes | None = None
    if job_description is not None:
        jd_filename = job_description.filename or ""
        jd_extension = _get_extension(jd_filename)
        if jd_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Job description must be PDF or DOCX.")
        jd_file_bytes = await job_description.read()
        if not jd_file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded job description file is empty.")

    try:
        return analyze_resume(
            filename=filename,
            file_bytes=file_bytes,
            jd_filename=jd_filename,
            jd_file_bytes=jd_file_bytes,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

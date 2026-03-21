import json
import importlib.util
import os
import uuid
from pathlib import Path

from ..utils.parser import build_structured_response

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTPARK_DIR = PROJECT_ROOT
PIPELINE_OUTPUT_DIR = ARTPARK_DIR / "output"
DEFAULT_JD_PATH = ARTPARK_DIR / "Machine-Learning-Engineer.pdf"
TEMP_UPLOADS_DIR = PROJECT_ROOT / "backend" / "uploads"


def _clear_previous_outputs() -> None:
    if not PIPELINE_OUTPUT_DIR.exists():
        return
    for path in PIPELINE_OUTPUT_DIR.rglob("*"):
        if path.is_file():
            path.unlink()


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"Expected output file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_run_pipeline():
    pipeline_script = ARTPARK_DIR / "run_pipeline.py"
    if not pipeline_script.exists():
        raise RuntimeError(f"Pipeline script not found: {pipeline_script}")
    spec = importlib.util.spec_from_file_location("artpark_run_pipeline", pipeline_script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load pipeline module spec.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_pipeline = getattr(module, "run_pipeline", None)
    if run_pipeline is None:
        raise RuntimeError("run_pipeline function not found in run_pipeline.py")
    return run_pipeline


def analyze_resume(
    filename: str,
    file_bytes: bytes,
    jd_filename: str | None = None,
    jd_file_bytes: bytes | None = None,
) -> dict:
    if jd_file_bytes is None and not DEFAULT_JD_PATH.exists():
        raise RuntimeError(f"Default job description not found: {DEFAULT_JD_PATH}")

    TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    upload_path = TEMP_UPLOADS_DIR / unique_name
    upload_path.write_bytes(file_bytes)
    jd_upload_path: Path | None = None
    if jd_file_bytes is not None and jd_filename:
        jd_unique_name = f"{uuid.uuid4().hex}_{jd_filename}"
        jd_upload_path = TEMP_UPLOADS_DIR / jd_unique_name
        jd_upload_path.write_bytes(jd_file_bytes)
    jd_path = jd_upload_path or DEFAULT_JD_PATH

    old_cwd = Path.cwd()
    try:
        _clear_previous_outputs()
        os.chdir(ARTPARK_DIR)
        run_pipeline = _load_run_pipeline()
        run_pipeline(str(upload_path), str(jd_path), "output")
    except Exception as exc:  # pragma: no cover - surfaced through API
        raise RuntimeError(f"Pipeline execution failed: {exc}") from exc
    finally:
        os.chdir(old_cwd)
        if upload_path.exists():
            upload_path.unlink()
        if jd_upload_path and jd_upload_path.exists():
            jd_upload_path.unlink()

    gap_data = _read_json(PIPELINE_OUTPUT_DIR / "module_4" / "gapengine_output.json")
    mapping_data = _read_json(PIPELINE_OUTPUT_DIR / "module_5" / "profession_mapping_output.json")
    roadmap_data = _read_json(PIPELINE_OUTPUT_DIR / "module_6" / "adaptive_path_output.json")
    resources_data = _read_json(PIPELINE_OUTPUT_DIR / "module_7" / "learning_resources_output.json")
    resume_skill_data = _read_json(
        PIPELINE_OUTPUT_DIR / "resume" / "module_2" / "Module_2_combined.json"
    )

    return build_structured_response(
        filename=filename,
        gap_data=gap_data,
        mapping_data=mapping_data,
        roadmap_data=roadmap_data,
        resources_data=resources_data,
        resume_skill_data=resume_skill_data,
    )

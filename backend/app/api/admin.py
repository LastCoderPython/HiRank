import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Cookie
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import csv
import io
import shutil
import asyncio

from app.config import settings
from app.db.supabase import get_user_by_id
from app.retrieval.cutoff_engine import cutoff_engine
from app.services.college_info_service import college_info_service

logger = logging.getLogger("rankroute.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def require_admin(sb_access_token: Optional[str] = Cookie(None)):
    from app.api.auth import verify_jwt, fetch_user_from_supabase
    if not sb_access_token:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    user_id = None
    payload = verify_jwt(sb_access_token)
    if payload:
        user_id = payload.get("sub")
        
    if not user_id:
        user = await fetch_user_from_supabase(sb_access_token)
        if user:
            user_id = user.get("id")
            payload = {"sub": user_id, "role": user.get("role")}
            
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    profile = await get_user_by_id(user_id)
    if not profile or profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload or {"sub": user_id}


VALID_COLLEGE_DATA_TYPES = frozenset({
    "fee_structure", "placement_stats", "facilities",
    "seat_matrix", "colleges_basic_info",
})

COLLEGE_DATA_FILENAMES = {
    "fee_structure": "fee_structure.csv",
    "placement_stats": "placement_stats.csv",
    "facilities": "facilities.csv",
    "seat_matrix": "seat_matrix.csv",
    "colleges_basic_info": "colleges_basic_info.csv",
}

COLLEGE_DATA_COLUMNS = {
    "fee_structure": [
        "college_name", "college_code", "program",
        "tuition_fee_per_sem", "hostel_fee_per_sem",
        "total_per_sem", "total_first_year",
    ],
    "placement_stats": [
        "college_name", "college_code", "branch",
        "avg_package_lpa", "highest_package_lpa",
        "placement_percentage",
    ],
    "facilities": [
        "college_name", "college_code", "campus_area_acres",
        "hostel_boys", "hostel_girls", "total_seats",
    ],
    "seat_matrix": [
        "college_name", "college_code", "branch",
        "total_seats", "govt_seats",
    ],
    "colleges_basic_info": [
        "college_name", "college_code", "location",
        "district", "state", "type", "affiliation", "website",
    ],
}

CUTOFF_RENAME_MAP = {
    "college": "college_name",
    "institute": "college_name",
    "institute_name": "college_name",
    "branch_name": "branch",
    "course": "branch",
    "open_rank": "opening_rank",
    "close_rank": "closing_rank",
    "op_rank": "opening_rank",
    "cl_rank": "closing_rank",
}

CEE_REQUIRED_COLS = [
    "college_name", "college_code", "branch", "category",
    "opening_rank", "closing_rank", "year", "seat_type",
]
JEE_REQUIRED_COLS = CEE_REQUIRED_COLS + ["quota"]

ALLOWED_CSV_MIMES = frozenset({
    "text/csv", "text/x-csv",
    "application/csv", "application/x-csv",
})


# ── CSV Validation ───────────────────────────────────────────────────


def _normalize_cutoff_columns(row: Dict[str, str]) -> Dict[str, str]:
    normalized = {}
    for k, v in row.items():
        cleaned = k.strip().lower()
        mapped = CUTOFF_RENAME_MAP.get(cleaned, cleaned)
        normalized[mapped] = (v or "").strip()
    return normalized


def _validate_cutoff_csv(contents: str, exam: str) -> Dict[str, Any]:
    reader = csv.DictReader(io.StringIO(contents))
    raw_columns = [c.strip().lower() for c in (reader.fieldnames or [])]
    normalized_cols = set()
    for c in raw_columns:
        normalized_cols.add(CUTOFF_RENAME_MAP.get(c, c))

    required = JEE_REQUIRED_COLS if exam.upper() == "JEE" else CEE_REQUIRED_COLS
    missing = [c for c in required if c not in normalized_cols]
    errors = []
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")

    rows_parsed = 0
    preview = []
    for row in reader:
        nr = _normalize_cutoff_columns(row)
        rows_parsed += 1

        try:
            op = int(nr.get("opening_rank", ""))
            if op < 0:
                errors.append(f"Row {rows_parsed}: opening_rank must be non-negative")
        except (ValueError, TypeError):
            errors.append(f"Row {rows_parsed}: opening_rank must be an integer")

        try:
            cl = int(nr.get("closing_rank", ""))
            if cl < 1:
                errors.append(f"Row {rows_parsed}: closing_rank must be positive")
        except (ValueError, TypeError):
            errors.append(f"Row {rows_parsed}: closing_rank must be an integer")

        try:
            yr = int(nr.get("year", ""))
            if yr < 2000 or yr > 2030:
                errors.append(f"Row {rows_parsed}: year must be between 2000 and 2030")
        except (ValueError, TypeError):
            errors.append(f"Row {rows_parsed}: year must be an integer")

        if rows_parsed <= 5:
            preview.append(nr)

    return {
        "valid": len(errors) == 0,
        "rows": rows_parsed,
        "columns": sorted(normalized_cols),
        "errors": errors,
        "preview": preview,
    }


def _validate_college_info_csv(contents: str, data_type: str) -> Dict[str, Any]:
    expected = [c.lower() for c in COLLEGE_DATA_COLUMNS.get(data_type, [])]
    reader = csv.DictReader(io.StringIO(contents))
    raw_columns = [c.strip().lower() for c in (reader.fieldnames or [])]
    missing = [c for c in expected if c not in raw_columns]
    errors = []
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")

    rows_parsed = 0
    preview = []
    for row in reader:
        rows_parsed += 1
        if rows_parsed <= 5:
            preview.append({k.strip(): (v or "").strip() for k, v in row.items()})

    return {
        "valid": len(errors) == 0,
        "rows": rows_parsed,
        "columns": raw_columns,
        "errors": errors,
        "preview": preview,
    }


# ── Backup ───────────────────────────────────────────────────────────


def _save_with_backup(active_path: str, contents: str, admin_id: str) -> Dict[str, Any]:
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    active = Path(active_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
    backup_id = timestamp

    backup_path = None
    if active.exists():
        backup_filename = f"{timestamp}__{active.name}"
        backup_path = backup_dir / backup_filename
        shutil.copy2(str(active), str(backup_path))

        pattern = f"*__{active.name}"
        backups = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[10:]:
            old.unlink()

    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(contents, encoding="utf-8")

    return {
        "backup_id": backup_id,
        "backup_path": str(backup_path) if backup_path else None,
    }


# ── File Read ────────────────────────────────────────────────────────


def _check_csv_mime(content_type: Optional[str]):
    if not content_type:
        return
    ct = content_type.lower().split(";")[0].strip()
    if ct not in ALLOWED_CSV_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Only CSV files are accepted.",
        )


async def _read_upload(file: UploadFile, max_mb: int = 10) -> str:
    _check_csv_mime(file.content_type)
    contents = await file.read()
    if len(contents) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {max_mb} MB.",
        )
    return contents.decode("utf-8-sig")


# ── Endpoints: Upload ────────────────────────────────────────────────


@router.post("/upload/cutoffs")
async def upload_cutoffs(
    file: UploadFile = File(...),
    exam: str = Form("CEE"),
    replace: bool = Form(True),
    sync_chroma: bool = Form(True),
    admin: dict = Depends(require_admin),
):
    if exam.upper() not in ("CEE", "JEE"):
        raise HTTPException(status_code=422, detail="exam must be CEE or JEE")
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=422, detail="File must have .csv extension")

    contents = await _read_upload(file)
    result = _validate_cutoff_csv(contents, exam)
    if not result["valid"]:
        raise HTTPException(status_code=422, detail={
            "message": "CSV validation failed",
            "errors": result["errors"],
        })

    active_path = settings.cee_data_path if exam.upper() == "CEE" else settings.jee_data_path
    admin_id = admin.get("sub", "")
    backup = _save_with_backup(active_path, contents, admin_id)

    stats = cutoff_engine.reload()

    chroma_job_id = None
    if sync_chroma:
        async def _run_chroma_sync(path: str, exam_name: str):
            from app.services.data_ingestor import DataIngestor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                DataIngestor.ingest_from_path,
                path, exam_name, None, replace,
            )
        task = asyncio.create_task(_run_chroma_sync(active_path, exam.upper()))
        chroma_job_id = str(id(task))

    from app.services.log_service import log_service
    log_service.insert("admin_action", "info",
        f"Uploaded {exam.upper()} cutoff CSV: {result['rows']} rows",
        {"filename": file.filename, "rows": result["rows"], "exam": exam.upper(), "chroma": sync_chroma},
        source="admin.csv_upload", actor_id=admin_id, actor_role="admin")

    return {
        "success": True,
        "rows_loaded": result["rows"],
        "columns": result["columns"],
        "backup_id": backup["backup_id"],
        "chroma_job_id": chroma_job_id,
        "reload_stats": stats,
    }


@router.post("/upload/college-info")
async def upload_college_info(
    file: UploadFile = File(...),
    data_type: str = Form(...),
    admin: dict = Depends(require_admin),
):
    if data_type not in VALID_COLLEGE_DATA_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid data_type. Must be one of: {', '.join(sorted(VALID_COLLEGE_DATA_TYPES))}",
        )
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=422, detail="File must have .csv extension")

    contents = await _read_upload(file)
    result = _validate_college_info_csv(contents, data_type)
    if not result["valid"]:
        raise HTTPException(status_code=422, detail={
            "message": "CSV validation failed",
            "errors": result["errors"],
        })

    target_path = college_info_service.data_dir / COLLEGE_DATA_FILENAMES[data_type]
    admin_id = admin.get("sub", "")
    backup = _save_with_backup(str(target_path), contents, admin_id)

    stats = college_info_service.reload_all()

    from app.services.log_service import log_service
    log_service.insert("admin_action", "info",
        f"Uploaded college info CSV ({data_type}): {result['rows']} rows",
        {"filename": file.filename, "data_type": data_type, "rows": result["rows"]},
        source="admin.csv_upload", actor_id=admin_id, actor_role="admin")

    return {
        "success": True,
        "rows_loaded": result["rows"],
        "columns": result["columns"],
        "backup_id": backup["backup_id"],
        "reload_stats": stats,
    }


# ── Endpoints: Validate ──────────────────────────────────────────────


@router.post("/validate/cutoffs")
async def validate_cutoffs(
    file: UploadFile = File(...),
    exam: str = Form("CEE"),
    admin: dict = Depends(require_admin),
):
    if exam.upper() not in ("CEE", "JEE"):
        raise HTTPException(status_code=422, detail="exam must be CEE or JEE")
    contents = await _read_upload(file)
    return _validate_cutoff_csv(contents, exam)


@router.post("/validate/college-info")
async def validate_college_info(
    file: UploadFile = File(...),
    data_type: str = Form(...),
    admin: dict = Depends(require_admin),
):
    if data_type not in VALID_COLLEGE_DATA_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid data_type. Must be one of: {', '.join(sorted(VALID_COLLEGE_DATA_TYPES))}",
        )
    contents = await _read_upload(file)
    return _validate_college_info_csv(contents, data_type)


# ── Endpoints: Backups & Restore ─────────────────────────────────────


@router.get("/backups")
async def list_backups(admin: dict = Depends(require_admin)):
    backup_dir = Path("data/backups")
    if not backup_dir.exists():
        return {"backups": []}

    entries = []
    for fp in sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if fp.is_file():
            stat = fp.stat()
            entries.append({
                "id": fp.stem.split("__")[0] if "__" in fp.stem else fp.stem,
                "filename": fp.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"backups": entries}


BACKUP_TARGET_MAP = {
    "cee_cutoffs.csv": ("cutoff", settings.cee_data_path),
    "jee_cutoffs.csv": ("cutoff", settings.jee_data_path),
    "fee_structure.csv": ("college_info", str(college_info_service.data_dir / "fee_structure.csv")),
    "placement_stats.csv": ("college_info", str(college_info_service.data_dir / "placement_stats.csv")),
    "facilities.csv": ("college_info", str(college_info_service.data_dir / "facilities.csv")),
    "seat_matrix.csv": ("college_info", str(college_info_service.data_dir / "seat_matrix.csv")),
    "colleges_basic_info.csv": ("college_info", str(college_info_service.data_dir / "colleges_basic_info.csv")),
}


@router.post("/restore/{backup_id}")
async def restore_backup(
    backup_id: str,
    admin: dict = Depends(require_admin),
):
    backup_dir = Path("data/backups")
    if not backup_dir.exists():
        raise HTTPException(status_code=404, detail="No backups directory found")

    matches = sorted(
        [p for p in backup_dir.iterdir() if p.is_file() and p.stem.startswith(backup_id)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise HTTPException(status_code=404, detail=f"No backup found with id: {backup_id}")

    backup_file = matches[0]
    parts = backup_file.name.split("__", 1)
    original_filename = parts[1] if len(parts) > 1 else backup_file.name

    target_info = BACKUP_TARGET_MAP.get(original_filename)
    if not target_info:
        raise HTTPException(
            status_code=400,
            detail="Unknown backup target. Cannot restore this file.",
        )

    target_type, target_path = target_info
    contents = backup_file.read_text(encoding="utf-8")

    admin_id = admin.get("sub", "")
    _save_with_backup(target_path, contents, admin_id)

    if target_type == "cutoff":
        stats = cutoff_engine.reload()
        rows = stats.get("cee_rows", 0) + stats.get("jee_rows", 0)
    else:
        stats = college_info_service.reload_all()
        rows = sum(stats.values())

    from app.services.log_service import log_service
    log_service.insert("admin_action", "warning",
        f"Restored backup: {original_filename} ({rows} rows)",
        {"backup_id": backup_id, "original_filename": original_filename, "rows": rows, "target_type": target_type},
        source="admin.restore", actor_id=admin_id, actor_role="admin")

    return {
        "success": True,
        "restored_file": original_filename,
        "rows": rows,
        "reload_stats": stats,
    }


# ── Admin Log Viewer ───────────────────────────────────────────────

@router.get("/logs")
def get_logs(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: Dict[str, Any] = Depends(require_admin),
):
    from app.services.log_service import log_service
    result = log_service.query(
        event_type=event_type,
        severity=severity,
        source=source,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "entries": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "actor_id": e.actor_id,
                "actor_role": e.actor_role,
                "summary": e.summary,
                "details": e.details,
                "source": e.source,
                "created_at": e.created_at,
            }
            for e in result["entries"]
        ],
        "total": result["total"],
        "limit": result["limit"],
        "offset": result["offset"],
    }


@router.get("/logs/stats")
def get_log_stats(
    admin: Dict[str, Any] = Depends(require_admin),
):
    from app.services.log_service import log_service
    return log_service.get_stats()


# ── Cutoff Year Management ─────────────────────────────────────────


@router.get("/cutoffs/status")
def get_cutoff_status(
    admin: Dict[str, Any] = Depends(require_admin),
):
    stats = cutoff_engine.get_stats()
    return {
        "cee": {
            "years": stats.get("cee_years", []),
            "records": stats.get("cee_records", 0),
            "colleges": stats.get("cee_colleges", 0),
        },
        "jee": {
            "years": stats.get("jee_years", []),
            "records": stats.get("jee_records", 0),
            "colleges": stats.get("jee_colleges", 0),
        },
        "data_loaded": stats.get("data_loaded", False),
    }


@router.post("/cutoffs/archive-year")
def archive_cutoff_year(
    exam: str = Form(...),
    year: int = Form(...),
    admin: Dict[str, Any] = Depends(require_admin),
):
    from app.services.log_service import log_service

    if exam.upper() not in ("CEE", "JEE"):
        raise HTTPException(status_code=422, detail="exam must be CEE or JEE")

    admin_id = admin.get("sub", "")
    active_path = settings.cee_data_path if exam.upper() == "CEE" else settings.jee_data_path
    active = Path(active_path)

    if not active.exists():
        raise HTTPException(status_code=404, detail=f"No {exam.upper()} data file found")

    # Read current file
    contents = active.read_text(encoding="utf-8")

    # Archive it with year
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{exam.upper()}_cutoffs_{year}.csv"
    archive_path = backup_dir / archive_name
    archive_path.write_text(contents, encoding="utf-8")

    log_service.insert("admin_action", "info",
        f"Archived {exam.upper()} cutoff year {year}: {archive_name}",
        {"exam": exam.upper(), "year": year, "archive": archive_name},
        source="admin.archive_year", actor_id=admin_id, actor_role="admin")

    return {
        "success": True,
        "archive": archive_name,
        "message": f"{exam.upper()} cutoff data for {year} archived to {archive_name}",
    }

class MaintenanceToggleRequest(BaseModel):
    active: bool

@router.get("/maintenance")
async def get_maintenance_status(payload: dict = Depends(require_admin)):
    from app.middleware.maintenance import _get_redis_client, MAINTENANCE_KEY
    client = _get_redis_client()
    if not client:
        return {"active": False, "error": "Redis unavailable"}
    
    val = client.get(MAINTENANCE_KEY)
    active = val is not None and str(val).lower() == "true"
    return {"active": active}

@router.post("/maintenance")
async def toggle_maintenance(req: MaintenanceToggleRequest, payload: dict = Depends(require_admin)):
    from app.middleware.maintenance import _get_redis_client, MAINTENANCE_KEY
    from app.services.log_service import log_service
    client = _get_redis_client()
    if not client:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    if req.active:
        client.set(MAINTENANCE_KEY, "true")
        status = "enabled"
    else:
        client.delete(MAINTENANCE_KEY)
        status = "disabled"
        
    admin_id = payload.get("sub", "unknown")
    log_service.insert("admin_action", "warning", f"Maintenance mode {status}", 
        {"active": req.active}, source="admin.maintenance", actor_id=admin_id, actor_role="admin")
        
    return {"success": True, "active": req.active}

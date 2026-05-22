from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any

from pydantic import BaseModel

from services.contract_service import _find_soffice_executable, _import_win32_modules

BASE_DIR = Path(__file__).resolve().parents[1]
OFFICE_PREVIEW_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


def normalize_attachment_path(file_path: str) -> str:
    normalized_path = str(file_path or "").strip().replace("\\", "/")
    if not normalized_path:
        return ""
    if normalized_path.startswith("/static/"):
        return normalized_path
    if normalized_path.startswith("static/"):
        return f"/{normalized_path}"
    return normalized_path


def resolve_local_attachment_path(file_path: str, base_dir: Path = BASE_DIR) -> Path:
    normalized_path = normalize_attachment_path(file_path)
    if normalized_path.startswith("/static/"):
        return base_dir / normalized_path.lstrip("/")
    candidate = Path(normalized_path)
    return candidate if candidate.is_absolute() else base_dir / normalized_path


def _convert_with_libreoffice(source_path: Path, output_pdf: Path) -> bool:
    soffice_path = _find_soffice_executable()
    if soffice_path is None:
        return False

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    generated_pdf = output_pdf.parent / f"{source_path.stem}.pdf"
    if generated_pdf.exists():
        try:
            generated_pdf.unlink()
        except OSError:
            pass

    command = [
        str(soffice_path),
        "--headless",
        "--nologo",
        "--nodefault",
        "--norestore",
        "--nolockcheck",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_pdf.parent.resolve()),
        str(source_path.resolve()),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        return False

    if result.returncode != 0 or not generated_pdf.exists():
        return False

    if generated_pdf.resolve() != output_pdf.resolve():
        try:
            if output_pdf.exists():
                output_pdf.unlink()
        except OSError:
            pass
        generated_pdf.replace(output_pdf)

    return output_pdf.exists() and output_pdf.stat().st_size > 0


def _convert_with_word(source_path: Path, output_pdf: Path) -> bool:
    pythoncom, win32 = _import_win32_modules()
    if not pythoncom or not win32:
        return False
    app = None
    document = None
    try:
        pythoncom.CoInitialize()
        app = win32.DispatchEx("Word.Application")
        app.Visible = False
        document = app.Documents.Open(str(source_path.resolve()))
        document.ExportAsFixedFormat(str(output_pdf.resolve()), 17)
        return output_pdf.exists() and output_pdf.stat().st_size > 0
    except Exception:
        return False
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _convert_with_excel(source_path: Path, output_pdf: Path) -> bool:
    pythoncom, win32 = _import_win32_modules()
    if not pythoncom or not win32:
        return False
    app = None
    workbook = None
    try:
        pythoncom.CoInitialize()
        app = win32.DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        workbook = app.Workbooks.Open(str(source_path.resolve()))
        workbook.ExportAsFixedFormat(0, str(output_pdf.resolve()))
        return output_pdf.exists() and output_pdf.stat().st_size > 0
    except Exception:
        return False
    finally:
        if workbook is not None:
            try:
                workbook.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _convert_with_powerpoint(source_path: Path, output_pdf: Path) -> bool:
    pythoncom, win32 = _import_win32_modules()
    if not pythoncom or not win32:
        return False
    app = None
    presentation = None
    try:
        pythoncom.CoInitialize()
        app = win32.DispatchEx("PowerPoint.Application")
        presentation = app.Presentations.Open(str(source_path.resolve()), WithWindow=False)
        presentation.SaveAs(str(output_pdf.resolve()), 32)
        return output_pdf.exists() and output_pdf.stat().st_size > 0
    except Exception:
        return False
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def generate_attachment_preview_file(source_path: Path, base_dir: Path = BASE_DIR) -> str:
    ext = source_path.suffix.lower()
    if ext not in OFFICE_PREVIEW_EXTENSIONS or not source_path.exists():
        return ""

    preview_dir = source_path.parent / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = preview_dir / f"{source_path.stem}_preview.pdf"
    if output_pdf.exists():
        try:
            output_pdf.unlink()
        except OSError:
            pass

    converted = _convert_with_libreoffice(source_path, output_pdf)
    if not converted and ext in {".doc", ".docx"}:
        converted = _convert_with_word(source_path, output_pdf)
    if not converted and ext in {".xls", ".xlsx"}:
        converted = _convert_with_excel(source_path, output_pdf)
    if not converted and ext in {".ppt", ".pptx"}:
        converted = _convert_with_powerpoint(source_path, output_pdf)

    if not converted or not output_pdf.exists():
        return ""

    return f"/{output_pdf.relative_to(base_dir).as_posix()}"


def enrich_attachment_record(
    item: dict[str, Any],
    *,
    base_dir: Path = BASE_DIR,
    generate_missing_preview: bool = False,
) -> dict[str, Any] | None:
    name = str(item.get("name") or item.get("filename") or "").strip()
    file_path = normalize_attachment_path(str(item.get("file_path") or item.get("url") or item.get("path") or "").strip())
    if not name or not file_path:
        return None

    size = item.get("size")
    try:
        size = int(size) if size is not None else None
    except (TypeError, ValueError):
        size = None

    uploaded_at = item.get("uploaded_at")
    if isinstance(uploaded_at, datetime):
        uploaded_at = uploaded_at.isoformat()
    elif uploaded_at is not None:
        uploaded_at = str(uploaded_at)

    preview_file_path = normalize_attachment_path(str(item.get("preview_file_path") or "").strip())
    source_path = resolve_local_attachment_path(file_path, base_dir=base_dir)
    if not preview_file_path:
        preview_candidate = source_path.parent / "preview" / f"{source_path.stem}_preview.pdf"
        if preview_candidate.exists():
            preview_file_path = f"/{preview_candidate.relative_to(base_dir).as_posix()}"
        elif generate_missing_preview:
            preview_file_path = generate_attachment_preview_file(source_path, base_dir=base_dir)

    return {
        "name": name,
        "file_path": file_path,
        "preview_file_path": preview_file_path or "",
        "size": size,
        "uploaded_at": uploaded_at,
    }


def enrich_attachment_list(
    raw_attachments: Any,
    *,
    base_dir: Path = BASE_DIR,
    generate_missing_preview: bool = False,
) -> list[dict[str, Any]]:
    normalized_attachments: list[dict[str, Any]] = []
    for item in raw_attachments or []:
        if isinstance(item, BaseModel):
            data = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        elif isinstance(item, dict):
            data = item
        else:
            continue
        normalized = enrich_attachment_record(
            data,
            base_dir=base_dir,
            generate_missing_preview=generate_missing_preview,
        )
        if normalized:
            normalized_attachments.append(normalized)
    return normalized_attachments

"""Historial local de estudiantes."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_student_id(student: str) -> str:
    """Convierte un nombre de estudiante en un ID seguro para archivo."""
    value = str(student or "usuario").strip().lower()
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return safe or "usuario"


def default_history() -> dict[str, Any]:
    """Estructura base del historial."""
    return {"simulacros": [], "falladas": {}}


def load_history(student: str, historial_dir: Path) -> dict[str, Any]:
    """Carga historial de un estudiante."""
    path = historial_dir / f"{safe_student_id(student)}.json"
    if not path.exists():
        return default_history()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_history()
    if isinstance(data, list):
        return {"simulacros": data, "falladas": {}}
    if not isinstance(data, dict):
        return default_history()
    data.setdefault("simulacros", [])
    data.setdefault("falladas", {})
    return data


def save_history(student: str, history: dict[str, Any], historial_dir: Path) -> Path:
    """Guarda historial de estudiante."""
    historial_dir.mkdir(parents=True, exist_ok=True)
    path = historial_dir / f"{safe_student_id(student)}.json"
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def update_history(
    student: str,
    result: dict[str, Any],
    historial_dir: Path,
) -> dict[str, Any]:
    """Agrega resultado al historial y actualiza preguntas falladas."""
    history = load_history(student, historial_dir)
    record = dict(result)
    record.setdefault("fecha", datetime.now().isoformat(timespec="seconds"))
    history["simulacros"].append(record)

    for error in result.get("errores", []):
        pid = str(error.get("id", ""))
        if not pid:
            continue
        previous = history["falladas"].get(pid, {})
        history["falladas"][pid] = {
            "pregunta_id": pid,
            "area": error.get("area", ""),
            "tema": error.get("tema", ""),
            "subtema": error.get("subtema", ""),
            "errores": int(previous.get("errores", 0)) + 1,
            "ultima_fecha": record["fecha"],
            "recuperada": False,
        }

    for ok in result.get("correctas_detalle", []):
        pid = str(ok.get("id", ""))
        if pid in history["falladas"]:
            history["falladas"][pid]["recuperada"] = True

    save_history(student, history, historial_dir)
    return history

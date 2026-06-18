"""Carga, validación e integración de preguntas."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .ids import asignar_ids_faltantes, integrar_preguntas_por_id

REQUIRED_FIELDS = [
    "id", "area", "tema", "subtema", "competencia", "nivel_dificultad",
    "dificultad_porcentaje", "peso_dificultad", "ponderacion_area", "tipo_pregunta",
    "contexto", "pregunta", "opciones", "respuesta_correcta", "explicacion",
    "diagnostico_por_error", "recomendacion_si_falla",
]


def normalize_uploaded_json(raw_bytes: bytes) -> list[dict[str, Any]]:
    """Normaliza archivo JSON subido a lista de preguntas."""
    text = raw_bytes.decode("utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data, _ = json.JSONDecoder().raw_decode(text)

    if isinstance(data, dict) and isinstance(data.get("preguntas"), list):
        data = data["preguntas"]
    if not isinstance(data, list):
        raise ValueError("El archivo debe ser una lista o un objeto con clave 'preguntas'.")
    return data


def validate_questions(questions: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Valida estructura básica de preguntas."""
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for index, question in enumerate(questions, start=1):
        qid = str(question.get("id") or f"fila-{index}")
        if question.get("id") and qid in seen:
            errors.append(f"{qid}: ID repetido dentro del archivo subido.")
        seen.add(qid)

        for field in REQUIRED_FIELDS:
            if field not in question:
                errors.append(f"{qid}: falta el campo {field}.")

        options = question.get("opciones")
        if not isinstance(options, list) or len(options) != 4:
            errors.append(f"{qid}: debe tener exactamente 4 opciones.")
        else:
            letters = [op.get("letra") for op in options if isinstance(op, dict)]
            if letters != ["A", "B", "C", "D"]:
                errors.append(f"{qid}: las opciones deben ser A, B, C y D en orden.")

        if question.get("respuesta_correcta") not in ["A", "B", "C", "D"]:
            errors.append(f"{qid}: respuesta_correcta debe ser A, B, C o D.")

        try:
            difficulty = float(question.get("dificultad_porcentaje", 0))
            if not 0 <= difficulty <= 100:
                errors.append(f"{qid}: dificultad_porcentaje debe estar entre 0 y 100.")
        except (TypeError, ValueError):
            errors.append(f"{qid}: dificultad_porcentaje debe ser numérico.")

        if question.get("fuente", {}).get("requiere_revision_humana", True):
            warnings.append(f"{qid}: marcada para revisión humana.")

    return errors, warnings


def merge_questions(
    materia_id: str,
    new_questions: list[dict[str, Any]],
    config: dict[str, Any],
    materias_dir: Path,
) -> dict[str, Any]:
    """Integra preguntas en el archivo JSON de la materia."""
    meta = config["materias"][materia_id]
    path = materias_dir / meta["archivo"]
    path.parent.mkdir(parents=True, exist_ok=True)

    current: list[dict[str, Any]] = []
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(current, dict) and isinstance(current.get("preguntas"), list):
            current = current["preguntas"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".backup_{timestamp}.json")
    if path.exists():
        shutil.copy2(path, backup_path)
    else:
        backup_path.write_text("[]", encoding="utf-8")

    con_ids = asignar_ids_faltantes(new_questions, current)
    merged, summary = integrar_preguntas_por_id(current, con_ids, reemplazar_existentes=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "added": summary["added"],
        "replaced": summary["replaced"],
        "total": len(merged),
        "backup": str(backup_path),
    }

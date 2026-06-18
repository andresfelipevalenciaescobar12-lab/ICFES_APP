"""Selección de preguntas, calificación y recomendaciones."""
from __future__ import annotations

import random
from typing import Any


def get_sim_count(meta: dict[str, Any], default: int = 10) -> int:
    """Usa preguntas_simulacro y conserva compatibilidad con preguntas_por_simulacro."""
    return int(meta.get("preguntas_simulacro", meta.get("preguntas_por_simulacro", default)))


def pick_questions(
    banco: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    mode: str,
    materia_id: str | None = None,
    cantidad: int | None = None,
    failed_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Selecciona preguntas para un simulacro."""
    selected: list[dict[str, Any]] = []
    mode = str(mode)

    if mode == "Falladas":
        failed = set(failed_ids or [])
        for questions in banco.values():
            selected.extend([q for q in questions if q.get("id") in failed])
        random.shuffle(selected)
        if cantidad:
            selected = selected[: int(cantidad)]
        return selected

    if mode == "Materia" and materia_id:
        pool = list(banco.get(materia_id, []))
        random.shuffle(pool)
        return pool[: min(int(cantidad or len(pool)), len(pool))]

    if mode == "Corto":
        corto = config.get("simulacro_corto", {})
        for mid, meta in config.get("materias", {}).items():
            name = meta.get("nombre", mid)
            needed = int(corto.get(name, min(5, len(banco.get(mid, [])))))
            pool = list(banco.get(mid, []))
            random.shuffle(pool)
            selected.extend(pool[: min(needed, len(pool))])
        random.shuffle(selected)
        return selected

    for mid, meta in config.get("materias", {}).items():
        needed = get_sim_count(meta)
        pool = list(banco.get(mid, []))
        random.shuffle(pool)
        selected.extend(pool[: min(needed, len(pool))])
    random.shuffle(selected)
    return selected


def calculate_score(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Calcula resultados de un simulacro."""
    correctas = 0
    incorrectas = 0
    saltadas = 0
    errores: list[dict[str, Any]] = []
    correctas_detalle: list[dict[str, Any]] = []
    por_materia: dict[str, dict[str, float]] = {}

    for q in questions:
        qid = str(q.get("id", ""))
        area = q.get("area") or q.get("nombre_materia") or "General"
        por_materia.setdefault(area, {"correctas": 0, "total": 0})
        por_materia[area]["total"] += 1

        user_answer = answers.get(qid, "")
        right = q.get("respuesta_correcta")
        if not user_answer:
            saltadas += 1
            continue
        if user_answer == right:
            correctas += 1
            por_materia[area]["correctas"] += 1
            correctas_detalle.append(q)
        else:
            incorrectas += 1
            errores.append({
                "id": qid,
                "area": area,
                "tema": q.get("tema", ""),
                "subtema": q.get("subtema", ""),
                "pregunta": q.get("pregunta", ""),
                "respuesta_usuario": user_answer,
                "respuesta_correcta": right,
                "explicacion": q.get("explicacion", ""),
                "diagnostico": q.get("diagnostico_por_error", {}).get(user_answer, ""),
                "recomendacion": q.get("recomendacion_si_falla", {}),
            })

    total = len(questions)
    porcentaje = (correctas / total * 100) if total else 0
    puntaje = round(100 + porcentaje * 4)
    puntaje = max(100, min(500, puntaje))

    desempeno = {
        materia: {
            "correctas": data["correctas"],
            "total": data["total"],
            "porcentaje": round((data["correctas"] / data["total"] * 100) if data["total"] else 0, 2),
        }
        for materia, data in por_materia.items()
    }

    return {
        "puntaje": puntaje,
        "correctas": correctas,
        "incorrectas": incorrectas,
        "saltadas": saltadas,
        "total": total,
        "porcentaje": round(porcentaje, 2),
        "desempeno_por_materia": desempeno,
        "errores": errores,
        "correctas_detalle": correctas_detalle,
    }


def generate_recommendations(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Genera recomendaciones locales a partir de errores."""
    grouped: dict[tuple[str, str], int] = {}
    for error in result.get("errores", []):
        key = (error.get("tema", "General"), error.get("subtema", ""))
        grouped[key] = grouped.get(key, 0) + 1

    recommendations: list[dict[str, Any]] = []
    for (tema, subtema), count in sorted(grouped.items(), key=lambda x: x[1], reverse=True):
        priority = "Muy alta" if count >= 3 else "Alta" if count == 2 else "Media"
        recommendations.append({
            "tema": tema,
            "subtema": subtema,
            "prioridad": priority,
            "acciones": [
                "Revisar la explicación de las preguntas falladas.",
                "Practicar ejercicios similares del mismo subtema.",
                "Volver a intentar preguntas falladas en modo repaso.",
            ],
        })
    return recommendations

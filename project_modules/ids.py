"""Gestión de IDs automáticos para preguntas ICFES."""
from __future__ import annotations

import re
from typing import Any

PREFIJOS_AREA = {
    "Matemáticas": "MAT",
    "Lectura Crítica": "LEC",
    "Ciencias Naturales": "NAT",
    "Sociales y Ciudadanas": "SOC",
    "Inglés": "ING",
}


def obtener_prefijo_por_area(area: str) -> str:
    """Devuelve el prefijo de ID según el área."""
    return PREFIJOS_AREA.get(str(area).strip(), "GEN")


def generar_siguiente_id(banco_actual: list[dict[str, Any]], area: str) -> str:
    """Genera el siguiente ID disponible para el área indicada."""
    prefijo = obtener_prefijo_por_area(area)
    numeros: list[int] = []
    patron = re.compile(rf"^{re.escape(prefijo)}-(\d+)$")

    for pregunta in banco_actual or []:
        pregunta_id = str(pregunta.get("id", ""))
        match = patron.match(pregunta_id)
        if match:
            numeros.append(int(match.group(1)))

    return f"{prefijo}-{max(numeros, default=0) + 1:04d}"


def asignar_ids_faltantes(
    preguntas_nuevas: list[dict[str, Any]],
    banco_actual: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Asigna IDs a preguntas cuyo campo id venga vacío, ausente o None."""
    banco_temporal = list(banco_actual or [])
    procesadas: list[dict[str, Any]] = []

    for pregunta in preguntas_nuevas or []:
        if not isinstance(pregunta, dict):
            continue
        if not str(pregunta.get("id", "")).strip():
            pregunta["id"] = generar_siguiente_id(
                banco_temporal,
                str(pregunta.get("area", "")),
            )
        procesadas.append(pregunta)
        banco_temporal.append(pregunta)

    return procesadas


def integrar_preguntas_por_id(
    banco_actual: list[dict[str, Any]],
    preguntas_nuevas: list[dict[str, Any]],
    reemplazar_existentes: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Integra preguntas al banco usando el campo id como clave."""
    por_id: dict[str, dict[str, Any]] = {}
    sin_id: list[dict[str, Any]] = []

    for pregunta in banco_actual or []:
        pid = pregunta.get("id")
        if pid:
            por_id[str(pid)] = pregunta
        else:
            sin_id.append(pregunta)

    added = 0
    replaced = 0
    skipped = 0

    for pregunta in preguntas_nuevas or []:
        pid = pregunta.get("id")
        if not pid:
            skipped += 1
            continue
        pid = str(pid)
        if pid in por_id:
            if reemplazar_existentes:
                por_id[pid] = pregunta
                replaced += 1
            else:
                skipped += 1
        else:
            por_id[pid] = pregunta
            added += 1

    merged = sin_id + list(por_id.values())
    return merged, {
        "added": added,
        "replaced": replaced,
        "skipped": skipped,
        "total": len(merged),
    }


def importar_preguntas_con_ids(
    preguntas_nuevas: list[dict[str, Any]],
    banco_actual: list[dict[str, Any]],
    reemplazar_existentes: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Asigna IDs faltantes e integra preguntas por ID."""
    con_ids = asignar_ids_faltantes(preguntas_nuevas, banco_actual)
    return integrar_preguntas_por_id(banco_actual, con_ids, reemplazar_existentes)

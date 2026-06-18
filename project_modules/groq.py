"""Integración con Groq: revisión de preguntas e IA post-simulacro."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import streamlit as st

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None


def groq_available() -> bool:
    """Indica si Groq está disponible y hay API key."""
    return get_groq_client() is not None


def get_groq_client():
    """Obtiene cliente Groq desde st.secrets o variable de entorno."""
    if Groq is None:
        return None
    api_key = None
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def _extract_json(text: str) -> dict[str, Any]:
    """Extrae un objeto JSON desde la respuesta del modelo."""
    clean = text.strip().replace("```json", "```")
    if clean.startswith("```"):
        clean = clean.strip("`").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def revisar_pregunta_con_groq(question: dict[str, Any]) -> dict[str, Any]:
    """Revisa una pregunta con Groq sin generar preguntas nuevas."""
    client = get_groq_client()
    if client is None:
        return {
            "estado_revision": "sin_ia",
            "calidad": 0,
            "dificultad_sugerida": question.get("nivel_dificultad", ""),
            "peso_dificultad_sugerido": question.get("peso_dificultad", 0),
            "comentarios": "Groq no está configurado.",
            "problemas_detectados": [],
            "sugerencias": ["Configurar GROQ_API_KEY."],
        }

    prompt = f"""
Revisa esta pregunta tipo ICFES Saber 11. No generes preguntas nuevas.
Devuelve solo JSON válido con:
{{
  "estado_revision": "aprobada | dudosa | rechazada",
  "calidad": 0,
  "dificultad_sugerida": "Básica diagnóstica | Media | Alta | Muy alta",
  "peso_dificultad_sugerido": 0,
  "comentarios": "",
  "problemas_detectados": [],
  "sugerencias": []
}}
Pregunta:
{json.dumps(question, ensure_ascii=False, indent=2)}
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Eres un revisor académico ICFES. Responde solo JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        review = _extract_json(response.choices[0].message.content)
    except Exception as exc:
        return {
            "estado_revision": "error_ia",
            "calidad": 0,
            "comentarios": f"Error revisando con Groq: {exc}",
            "problemas_detectados": ["No se pudo completar revisión IA."],
            "sugerencias": ["Revisar manualmente."],
        }

    state = str(review.get("estado_revision", "dudosa")).lower().strip()
    review["estado_revision"] = state if state in {"aprobada", "dudosa", "rechazada"} else "dudosa"
    return review


def revisar_banco_con_groq(
    questions: list[dict[str, Any]],
    limite: int | None = None,
    aplicar_sugerencias: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Revisa una lista de preguntas con Groq."""
    reviewed: list[dict[str, Any]] = []
    summary = {"aprobada": 0, "dudosa": 0, "rechazada": 0, "sin_ia": 0, "error_ia": 0, "total_revisadas": 0}
    total = limite if limite is not None else len(questions)

    for question in questions[:total]:
        review = revisar_pregunta_con_groq(question)
        question["revision_ia"] = review
        question["estado_revision"] = review.get("estado_revision", "dudosa")
        question["calidad_revision_ia"] = review.get("calidad", 0)
        if review.get("dificultad_sugerida"):
            question["dificultad_sugerida_ia"] = review["dificultad_sugerida"]
        if review.get("peso_dificultad_sugerido"):
            question["peso_dificultad_sugerido_ia"] = review["peso_dificultad_sugerido"]
        if aplicar_sugerencias:
            question["nivel_dificultad"] = review.get("dificultad_sugerida", question.get("nivel_dificultad"))
            question["peso_dificultad"] = review.get("peso_dificultad_sugerido", question.get("peso_dificultad"))
        state = question["estado_revision"]
        summary[state] = summary.get(state, 0) + 1
        summary["total_revisadas"] += 1
        reviewed.append(question)

    reviewed.extend(questions[total:])
    return reviewed, summary


def preguntar_groq_post_simulacro(question: str, result: dict[str, Any]) -> str:
    """Responde dudas del usuario después del simulacro."""
    if st.session_state.get("simulacro_en_curso", False):
        return "La IA está bloqueada mientras el simulacro está en curso."
    client = get_groq_client()
    if client is None:
        return "Groq no está configurado. Configura GROQ_API_KEY."
    context = json.dumps(result or {}, ensure_ascii=False, indent=2)
    prompt = f"Resultado del simulacro:\n{context}\n\nPregunta del usuario:\n{question}"
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Eres un tutor ICFES. No generes preguntas. Explica resultados."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
        )
        return response.choices[0].message.content
    except Exception as exc:
        return f"Error consultando Groq: {exc}"


preguntar_ia_post_simulacro = preguntar_groq_post_simulacro

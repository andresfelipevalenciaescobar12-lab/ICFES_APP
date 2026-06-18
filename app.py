# -*- coding: utf-8 -*-
"""ICFES Medicina Coach - versión modular estable."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from project_modules.groq import (
    groq_available,
    preguntar_groq_post_simulacro,
    revisar_banco_con_groq,
)
from project_modules.history import load_history, update_history
from project_modules.scoring import (
    calculate_score,
    generate_recommendations,
    get_sim_count,
    pick_questions,
)
from project_modules.upload import merge_questions, normalize_uploaded_json, validate_questions

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MATERIAS_DIR = DATA_DIR / "materias"
UPLOADS_DIR = DATA_DIR / "uploads"
HISTORIAL_DIR = BASE_DIR / "historial"
REPORTES_DIR = BASE_DIR / "reportes"
CONFIG_PATH = DATA_DIR / "configuracion_examen.json"

for folder in [DATA_DIR, MATERIAS_DIR, UPLOADS_DIR, HISTORIAL_DIR, REPORTES_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="ICFES Medicina Coach", page_icon="🩺", layout="wide")


def save_json(path: Path, data: Any) -> None:
    """Guarda JSON con UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def default_config() -> dict[str, Any]:
    """Configuración por defecto compatible con ICFES."""
    return {
        "materias": {
            "matematicas": {"nombre": "Matemáticas", "archivo": "matematicas.json", "preguntas_simulacro": 50, "ponderacion": 0.25},
            "lectura_critica": {"nombre": "Lectura Crítica", "archivo": "lectura_critica.json", "preguntas_simulacro": 41, "ponderacion": 0.25},
            "ciencias_naturales": {"nombre": "Ciencias Naturales", "archivo": "ciencias_naturales.json", "preguntas_simulacro": 58, "ponderacion": 0.20},
            "sociales_ciudadanas": {"nombre": "Sociales y Ciudadanas", "archivo": "sociales_ciudadanas.json", "preguntas_simulacro": 50, "ponderacion": 0.20},
            "ingles": {"nombre": "Inglés", "archivo": "ingles.json", "preguntas_simulacro": 55, "ponderacion": 0.10},
        },
        "simulacro_corto": {
            "Lectura Crítica": 8,
            "Matemáticas": 10,
            "Sociales y Ciudadanas": 10,
            "Ciencias Naturales": 12,
            "Inglés": 10,
        },
    }


def load_config() -> dict[str, Any]:
    """Carga configuración y normaliza campos antiguos."""
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        config = default_config()
        save_json(CONFIG_PATH, config)

    for meta in config.get("materias", {}).values():
        if "preguntas_simulacro" not in meta:
            meta["preguntas_simulacro"] = meta.get("preguntas_por_simulacro", 10)
    return config


def load_bank(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Carga banco de preguntas por materia."""
    bank: dict[str, list[dict[str, Any]]] = {}
    for materia_id, meta in config.get("materias", {}).items():
        path = MATERIAS_DIR / meta["archivo"]
        if not path.exists():
            bank[materia_id] = []
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        questions = data.get("preguntas", []) if isinstance(data, dict) else data
        for question in questions:
            question["materia_id"] = materia_id
            question["nombre_materia"] = meta["nombre"]
            question["ponderacion_area"] = meta.get("ponderacion", question.get("ponderacion_area", 0))
        bank[materia_id] = questions
    return bank


def question_card(question: dict[str, Any], index: int) -> None:
    """Muestra una pregunta y registra respuesta."""
    qid = str(question.get("id", f"P-{index}"))
    st.markdown(f"### {index}. {question.get('area', question.get('nombre_materia', ''))} - {qid}")
    if question.get("contexto"):
        st.info(question["contexto"])
    st.write(question.get("pregunta", ""))
    options = question.get("opciones", [])
    labels = [f"{op.get('letra')}. {op.get('texto')}" for op in options]
    selected = st.radio("Respuesta", ["Sin responder"] + labels, key=f"ans_{qid}")
    if selected == "Sin responder":
        st.session_state.answers.pop(qid, None)
    else:
        st.session_state.answers[qid] = selected.split(".", 1)[0]


def show_results(student: str, config: dict[str, Any]) -> None:
    """Calcula, muestra y guarda resultados."""
    questions = st.session_state.get("active_questions", [])
    answers = st.session_state.get("answers", {})
    result = calculate_score(questions, answers, config)
    result["recomendaciones"] = generate_recommendations(result)
    st.session_state["ultimo_resultado"] = result
    st.session_state["simulacro_en_curso"] = False
    st.session_state["simulacro_finalizado"] = True
    update_history(student, result, HISTORIAL_DIR)

    st.success(f"Puntaje estimado: {result['puntaje']} / 500")
    st.write(f"Correctas: {result['correctas']} | Incorrectas: {result['incorrectas']} | Saltadas: {result['saltadas']}")
    st.dataframe(pd.DataFrame(result["desempeno_por_materia"]).T, use_container_width=True)

    if result["errores"]:
        st.subheader("Errores")
        for error in result["errores"]:
            with st.expander(f"{error['id']} - {error['tema']}"):
                st.write(error["pregunta"])
                st.write("Tu respuesta:", error["respuesta_usuario"])
                st.write("Correcta:", error["respuesta_correcta"])
                st.write(error.get("explicacion", ""))


def main() -> None:
    """Punto principal de Streamlit."""
    config = load_config()
    banco = load_bank(config)

    st.sidebar.title("🩺 ICFES Medicina Coach")
    student = st.sidebar.text_input("Usuario", value="Usuario")
    page = st.sidebar.radio(
        "Menú",
        ["Dashboard", "Simulacro", "Repasar falladas", "Subir preguntas", "Historial", "IA Groq", "Configuración"],
    )

    if page == "Dashboard":
        st.title("📊 Dashboard del banco")
        rows = []
        total = 0
        for mid, meta in config["materias"].items():
            count = len(banco.get(mid, []))
            total += count
            rows.append({
                "Materia": meta["nombre"],
                "Preguntas": count,
                "Simulacro": get_sim_count(meta),
                "Ponderación": meta["ponderacion"],
            })
        st.metric("Preguntas cargadas", total)
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        hist = load_history(student, HISTORIAL_DIR)
        st.metric("Simulacros guardados", len(hist.get("simulacros", [])))
        pendientes = sum(1 for x in hist.get("falladas", {}).values() if not x.get("recuperada"))
        st.metric("Preguntas falladas pendientes", pendientes)

    elif page == "Simulacro":
        st.title("📝 Simulacro")
        mode = st.selectbox("Tipo de práctica", ["Corto", "Completo", "Materia"])
        materia_id = None
        cantidad = None
        if mode == "Materia":
            materia_options = {meta["nombre"]: mid for mid, meta in config["materias"].items()}
            selected_name = st.selectbox("Materia", list(materia_options.keys()))
            materia_id = materia_options[selected_name]
            max_questions = max(1, len(banco.get(materia_id, [])))
            cantidad = st.number_input("Cantidad de preguntas", min_value=1, max_value=max_questions, value=min(10, max_questions))

        if st.button("Crear simulacro", use_container_width=True):
            st.session_state.active_questions = pick_questions(banco, config, mode, materia_id, int(cantidad) if cantidad else None)
            st.session_state.answers = {}
            st.session_state.simulacro_en_curso = True
            st.session_state.simulacro_finalizado = False

        questions = st.session_state.get("active_questions", [])
        if questions:
            for idx, question in enumerate(questions, start=1):
                question_card(question, idx)
            if st.button("Finalizar simulacro", type="primary", use_container_width=True):
                show_results(student, config)

    elif page == "Repasar falladas":
        st.title("🔁 Repasar preguntas falladas")
        hist = load_history(student, HISTORIAL_DIR)
        pending = [x for x in hist.get("falladas", {}).values() if not x.get("recuperada")]
        st.metric("Falladas pendientes", len(pending))
        if pending:
            st.dataframe(pd.DataFrame(pending), use_container_width=True)
            cantidad = st.number_input("Cantidad a repasar", min_value=1, max_value=len(pending), value=min(10, len(pending)))
            if st.button("Crear práctica con falladas"):
                failed_ids = [x["pregunta_id"] for x in pending]
                st.session_state.active_questions = pick_questions(banco, config, "Falladas", failed_ids=failed_ids, cantidad=int(cantidad))
                st.session_state.answers = {}
                st.success("Ve a Simulacro para responderlas.")
        else:
            st.success("No hay falladas pendientes para este usuario.")

    elif page == "Subir preguntas":
        st.title("⬆️ Subir e integrar nuevas preguntas")
        materia_options = {meta["nombre"]: mid for mid, meta in config["materias"].items()}
        selected_name = st.selectbox("Materia destino", list(materia_options.keys()))
        materia_id = materia_options[selected_name]
        uploaded = st.file_uploader("Archivo .json", type=["json"])
        use_groq = st.checkbox("Pasar por revisión Groq/IA antes de integrar", value=False)

        if uploaded is not None:
            try:
                new_questions = normalize_uploaded_json(uploaded.getvalue())
                errors, warnings = validate_questions(new_questions)
                if errors:
                    st.error(f"Errores: {len(errors)}. Corrige antes de integrar.")
                    st.write(errors[:30])
                    return
                if warnings:
                    st.warning(f"Advertencias: {len(warnings)}. Se puede integrar, pero conviene revisar.")
                st.dataframe(pd.DataFrame([{
                    "id": q.get("id"),
                    "tema": q.get("tema"),
                    "dificultad": q.get("nivel_dificultad"),
                    "peso": q.get("peso_dificultad"),
                } for q in new_questions]).head(20), use_container_width=True)

                if use_groq:
                    st.write("Groq:", "✅ conectado" if groq_available() else "❌ no configurado")

                if st.button("Integrar preguntas al banco", use_container_width=True):
                    questions_to_integrate = new_questions
                    if use_groq and groq_available():
                        with st.spinner("Groq está revisando las preguntas..."):
                            questions_to_integrate, resumen_ia = revisar_banco_con_groq(questions_to_integrate)
                        st.json(resumen_ia)
                        questions_to_integrate = [q for q in questions_to_integrate if q.get("estado_revision") != "rechazada"]
                    if not questions_to_integrate:
                        st.error("No hay preguntas válidas para integrar.")
                    else:
                        result = merge_questions(materia_id, questions_to_integrate, config, MATERIAS_DIR)
                        st.success(f"Integración completa. Agregadas: {result['added']} | Reemplazadas: {result['replaced']} | Total materia: {result['total']}")
                        st.caption(f"Backup: {result['backup']}")
            except Exception as exc:
                st.error(f"No se pudo procesar el archivo: {exc}")

    elif page == "Historial":
        st.title("📚 Historial")
        hist = load_history(student, HISTORIAL_DIR)
        simulacros = hist.get("simulacros", [])
        if simulacros:
            st.dataframe(pd.DataFrame(simulacros), use_container_width=True)
        else:
            st.info("Aún no hay simulacros guardados.")

    elif page == "IA Groq":
        st.title("🤖 IA Groq post-simulacro")
        result = st.session_state.get("ultimo_resultado")
        if not result:
            st.info("Primero finaliza un simulacro.")
        else:
            prompt = st.text_area("Pregunta sobre tus resultados")
            if st.button("Preguntar"):
                st.write(preguntar_groq_post_simulacro(prompt, result))

    elif page == "Configuración":
        st.title("⚙️ Configuración")
        st.json(config)
        st.write("Variable Groq:", "✅ Detectada" if groq_available() else "❌ No detectada")
        st.code('GROQ_API_KEY = "tu_api_key"', language="toml")


if __name__ == "__main__":
    main()

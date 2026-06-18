# Reporte de refactorización - ICFES Medicina Coach

## Problemas estructurales encontrados en el app.py original

El archivo `app.py` recibido estaba estructuralmente dañado por acumulación de parches. Se observaron:

- Bloques duplicados de IDs automáticos.
- Bloques duplicados de Groq post-simulacro.
- Bloques duplicados de revisión Groq.
- Variables usadas antes de definirse: `student`, `config`, `banco`, `page`.
- Funciones llamadas pero no definidas o movidas: `pick_questions`, `calculate_score`, `generate_recommendations`, `update_history`, `safe_student_id`, `groq_available`.
- Errores de sintaxis visibles: diccionarios incompletos, f-strings dañados, `from **future**`, `Path(**file**)`, bloques sin indentación y fragmentos de prompt insertados como código.
- `KeyError` potencial por uso de `preguntas_por_simulacro` en lugar de `preguntas_simulacro`.
- `merge_questions()` incompleta y sin return correcto.

## Correcciones realizadas

Se reconstruyó el proyecto de forma modular:

- `project_modules/ids.py`
  - `obtener_prefijo_por_area`
  - `generar_siguiente_id`
  - `asignar_ids_faltantes`
  - `integrar_preguntas_por_id`
  - `importar_preguntas_con_ids`

- `project_modules/history.py`
  - `safe_student_id`
  - `load_history`
  - `save_history`
  - `update_history`

- `project_modules/scoring.py`
  - `pick_questions`
  - `calculate_score`
  - `generate_recommendations`
  - compatibilidad `preguntas_por_simulacro` → `preguntas_simulacro`

- `project_modules/upload.py`
  - `normalize_uploaded_json`
  - `validate_questions`
  - `merge_questions`
  - return obligatorio:
    `{"added", "replaced", "total", "backup"}`

- `project_modules/groq.py`
  - `groq_available`
  - `revisar_pregunta_con_groq`
  - `revisar_banco_con_groq`
  - `preguntar_groq_post_simulacro`
  - alias `preguntar_ia_post_simulacro`

- `app.py`
  - Interfaz Streamlit limpia.
  - Menú único.
  - Variables definidas en orden correcto.
  - Integración de preguntas con IDs automáticos.
  - Revisión Groq opcional antes de integrar.
  - IA Groq post-simulacro.
  - Historial por usuario.

## Funciones duplicadas eliminadas

Se dejó una sola implementación funcional de:

- `obtener_prefijo_por_area`
- `generar_siguiente_id`
- `asignar_ids_faltantes`
- `integrar_preguntas_por_id`
- `preguntar_ia_post_simulacro`
- `preguntar_groq_post_simulacro`

## Verificación

Se verificó compilación Python con `py_compile` para todos los archivos `.py` generados.

## Posibles bugs restantes

- La calidad del puntaje ICFES es estimada; puede ajustarse a una fórmula más sofisticada.
- Si existen preguntas previas en una ruta distinta a `data/materias`, deben copiarse allí.
- El archivo local `project_modules/groq.py` está dentro de paquete `project_modules`, por lo que no debe interferir con la librería oficial `groq`.

# app.py
# Interfaz de Streamlit para el orientador de plan de estudios (check + botón)
# Nota: mantiene todos los cálculos (costos, créditos, tiempo), pero puede ocultar
# valores numéricos en la UI mediante HIDE_VALUES.

import streamlit as st
import networkx as nx
import time
from courses_data import (
    fisioterapia_courses,
    enfermeria_courses,
    credits_per_semester_fisioterapia,
    credits_per_semester_enfermeria,
    calculate_semester_fisioterapia,
    calculate_semester_enfermeria,
)
try:
    from courses_data import (
        fisioterapia_courses_by_semester,
        enfermeria_courses_by_semester,
    )
except ImportError:
    fisioterapia_courses_by_semester = None
    enfermeria_courses_by_semester = None

from curriculum import (
    build_curriculum_graph,
    generate_full_plan,
    get_intersemestral_options,
)

# ---------------------------
# UI visual toggle: ocultar valores numéricos (costos/créditos/tiempo)
# ---------------------------
HIDE_VALUES = True  # <-- poner False si quieres volver a mostrar todos los números para debug

# ---------- Estado de sesión inicial ----------
if "approved_subjects" not in st.session_state:
    st.session_state.approved_subjects = []
if "semester_options" not in st.session_state:
    st.session_state.semester_options = {}
if "plan" not in st.session_state:
    st.session_state.plan = []
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0
if "previous_approved_subjects" not in st.session_state:
    st.session_state.previous_approved_subjects = []
if "last_program" not in st.session_state:
    st.session_state.last_program = None
if "last_plan_time" not in st.session_state:
    st.session_state.last_plan_time = None  # segundos

st.title("Orientador de Plan de Estudios")

# ---------- Selección del programa y construcción del grafo ----------
with st.spinner("Cargando datos iniciales..."):
    program = st.selectbox("Seleccione su programa", ["Fisioterapia", "Enfermería"])
    courses = fisioterapia_courses if program == "Fisioterapia" else enfermeria_courses
    credits_per_semester = (
        credits_per_semester_fisioterapia
        if program == "Fisioterapia"
        else credits_per_semester_enfermeria
    )
    calculate_semester = (
        calculate_semester_fisioterapia
        if program == "Fisioterapia"
        else calculate_semester_enfermeria
    )
    courses_by_semester = (
        fisioterapia_courses_by_semester
        if program == "Fisioterapia"
        else enfermeria_courses_by_semester
    )

    G = build_curriculum_graph(program, courses)

# Si cambió el programa, limpiar plan / opciones previas para evitar inconsistencias
if st.session_state.last_program is None:
    st.session_state.last_program = program
elif st.session_state.last_program != program:
    st.session_state.plan = []
    st.session_state.total_cost = 0
    st.session_state.semester_options = {}
    st.session_state.approved_subjects = []
    st.session_state.previous_approved_subjects = []
    st.session_state.last_program = program
    st.session_state.last_plan_time = None

# ---------- Helper: calcular semestre actual desde aprobado en estado ----------
def _current_semester_from_approved():
    try:
        total_credits_approved = sum(
            G.nodes[course]["credits"] for course in st.session_state.approved_subjects if course in G.nodes
        )
    except Exception:
        total_credits_approved = 0
    return calculate_semester(total_credits_approved), total_credits_approved

current_semester, total_credits_approved = _current_semester_from_approved()
# Mostrar semestre actual (ocultar créditos si HIDE_VALUES=True)
if HIDE_VALUES:
    st.write(f"**Semestre actual (estimado)**: {current_semester}")
else:
    st.write(f"**Semestre actual (estimado)**: {current_semester} (Créditos aprobados: {total_credits_approved})")

# ---------- Función para generar/actualizar plan (con medición de tiempo) ----------
def update_plan():
    # Recalcular semestre actual a partir del estado (por si cambió approved_subjects)
    sem, _ = _current_semester_from_approved()
    # Inicializar opciones por semestre si faltan
    for semester in range(sem, 11):
        st.session_state.semester_options.setdefault(
            semester,
            {"is_half_time": False, "extra_credits": 0, "intersemestral": None},
        )

    # Medir tiempo de ejecución del cálculo del plan
    try:
        t0 = time.perf_counter()
        plan, total_cost = generate_full_plan(
            G,
            st.session_state.approved_subjects,
            program,
            credits_per_semester,
            calculate_semester,
            st.session_state.semester_options,
        )
        t1 = time.perf_counter()
        elapsed = t1 - t0
    except Exception as e:
        st.error(f"Error al generar el plan: {e}")
        # No sobrescribimos el plan actual si falla
        return

    # Guardar resultados y tiempo en session_state
    st.session_state.plan = plan
    st.session_state.total_cost = total_cost
    st.session_state.previous_approved_subjects = st.session_state.approved_subjects.copy()
    st.session_state.last_plan_time = elapsed

    # Mostrar tiempo si está permitido
    if not HIDE_VALUES:
        st.write(f"⏱️ Tiempo de cálculo del plan: {elapsed:.3f} segundos")

# ---------- Callback de submit: lee LOS ESTADOS REALES de los checkboxes y actualiza ----------
def handle_submit():
    """
    Lee explícitamente el estado de cada checkbox (por sus keys) y actualiza
    st.session_state.approved_subjects con la lista actual. Luego inicializa
    semester_options y llama a update_plan().
    """
    selected = []
    # reconstruir la lista de cursos por semestre (misma lógica usada para construir checkboxes)
    for semester in range(1, 11):
        if courses_by_semester:
            semester_courses = courses_by_semester.get(semester, [])
        else:
            semester_courses = [course for course, info in courses.items() if info.get("semester") == semester]
        for idx, course in enumerate(semester_courses):
            key = f"approved_chk_{program}_{semester}_{idx}_{course}"
            # leer el estado del checkbox desde st.session_state (False por defecto si no existe)
            if st.session_state.get(key, False):
                selected.append(course)

    # Guardar aprobados y asegurar semester_options inicializadas
    st.session_state.approved_subjects = selected
    sem_now, _ = _current_semester_from_approved()
    for s in range(sem_now, 11):
        st.session_state.semester_options.setdefault(s, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})

    # Generar plan
    update_plan()

# ---------- Selección de asignaturas aprobadas via FORM (checkboxes) ----------
st.subheader("Seleccione las asignaturas aprobadas (por semestre)")

# Mostrar un formulario para agrupar la selección y evitar reruns por cada checkbox
with st.form("approved_form"):
    # Para cada semestre, usar un expander (cerrado por defecto salvo el semestre actual)
    for semester in range(1, 11):
        if courses_by_semester:
            semester_courses = courses_by_semester.get(semester, [])
        else:
            semester_courses = [course for course, info in courses.items() if info.get("semester") == semester]

        with st.expander(f"Semestre {semester} ({len(semester_courses)} asignaturas)", expanded=(semester == current_semester)):
            for idx, course in enumerate(semester_courses):
                key = f"approved_chk_{program}_{semester}_{idx}_{course}"
                # default ahora se toma de lo guardado en session_state (para mantener persistencia)
                default = course in st.session_state.approved_subjects
                # cada checkbox escribe su estado en st.session_state[key]
                st.checkbox(course, value=default, key=key)

    # Botón del formulario: al enviarlo actualizamos los aprobados y generamos plan
    # Usamos on_click=handle_submit para leer los estados actuales de todos los checkboxes
    st.form_submit_button("Generar plan de estudios", on_click=handle_submit)

# ---------- Mostrar plan en pestañas (si existe) ----------
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")
    # Mostrar tiempo de la última generación si no ocultamos valores
    if st.session_state.last_plan_time is not None and not HIDE_VALUES:
        st.info(f"Último cálculo: {st.session_state.last_plan_time:.3f} s")

    # Botón para recalcular plan con las opciones actuales (por si el usuario modificó media matrícula/extra/intersemestral)
    if st.button("Recalcular plan con opciones actuales"):
        with st.spinner("Recalculando plan..."):
            update_plan()
        st.success("Plan recalculado ✅")

    # Preparar etiquetas y crear pestañas
    labels = [f"Semestre {p['semester']}{' (repetido)' if p.get('repetition', 1) > 1 else ''}" for p in st.session_state.plan]
    tabs = st.tabs(labels)

    for i, (tab, semester_plan) in enumerate(zip(tabs, st.session_state.plan)):
        with tab:
            semester = semester_plan["semester"]
            effective_semester = min(semester, 10)

            # Asegurar entry en semester_options
            st.session_state.semester_options.setdefault(semester, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})

            # Media matrícula (NO dispara recálculo automático)
            half_time_key = f"half_time_{program}_{semester}_{i}"
            is_half_time = st.checkbox(
                f"Media matrícula (máx {credits_per_semester.get(effective_semester, 0) // 2 - 1} créditos, costo $5,000,000)",
                value=st.session_state.semester_options[semester].get("is_half_time", False),
                key=half_time_key,
            )

            # Créditos extra (slider) (NO dispara recálculo automático)
            max_extra_credits = 1 if is_half_time else max(0, 25 - credits_per_semester.get(effective_semester, 0))
            extra_key = f"extra_credits_{program}_{semester}_{i}"
            extra_credits = st.slider(
                f"Créditos extra a comprar (máx {max_extra_credits}, $800,000 por crédito)",
                0,
                max_extra_credits,
                st.session_state.semester_options[semester].get("extra_credits", 0),
                key=extra_key,
            )

            # Intersemestral: mostrar opciones válidas (NO dispara recálculo automático)
            intersemestral_options = get_intersemestral_options(G, tuple(st.session_state.approved_subjects))
            intersemestral_display_options = ["Ninguno"] + intersemestral_options
            current_inter = st.session_state.semester_options[semester].get("intersemestral")
            default_index = 0
            if current_inter and current_inter in intersemestral_options:
                default_index = intersemestral_display_options.index(current_inter)
            inter_key = f"intersemestral_{program}_{semester}_{i}"
            intersemestral_selected = st.selectbox(
                f"Intersemestral (opcional, $1,500,000)",
                intersemestral_display_options,
                index=default_index,
                key=inter_key,
            )

            # Guardar las opciones del usuario (no se recalcula automáticamente)
            st.session_state.semester_options[semester] = {
                "is_half_time": is_half_time,
                "extra_credits": extra_credits,
                "intersemestral": intersemestral_selected if intersemestral_selected != "Ninguno" else None,
            }

            # Mostrar la info del plan (basada en el último plan calculado)
            # Ocultar números si HIDE_VALUES=True
            if not HIDE_VALUES:
                st.write(f"**Créditos**: {semester_plan.get('credits', 0)} de {credits_per_semester.get(effective_semester, 0)} disponibles (Intersemestral: {semester_plan.get('intersemestral_credits', 0)} créditos)")
                st.write(f"**Costo**: ${semester_plan.get('cost', 0):,.0f}")
                if semester_plan.get("is_half_time"):
                    st.write("**Media matrícula** (recomendada para optimizar costos)")
                if semester_plan.get("extra_credits", 0) > 0:
                    st.write(f"**Créditos extra comprados**: {semester_plan['extra_credits']} (recomendado para reducir semestres)")
                if semester_plan.get("intersemestral"):
                    st.write(f"**Intersemestral**: {semester_plan['intersemestral']} (recomendado para optimizar costos)")
            else:
                # Mensaje minimalista cuando ocultamos valores numéricos
                if semester_plan.get("is_half_time"):
                    st.write("Recomendación: Media matrícula (opción activada).")
                if semester_plan.get("intersemestral"):
                    st.write("Intersemestral recomendado.")
                # No mostramos créditos ni montos monetarios

            st.write("**Asignaturas recomendadas**:")
            for subject in semester_plan.get("subjects", []):
                # Mostrar sólo el nombre de la asignatura (ocultar créditos si HIDE_VALUES)
                if HIDE_VALUES:
                    st.write(f"- {subject}")
                else:
                    credits = G.nodes[subject]["credits"] if subject in G.nodes else "?"
                    st.write(f"- {subject} ({credits} créditos)")

    # Mostrar costo total solo si está permitido
    if not HIDE_VALUES:
        st.write(f"**Costo total estimado**: ${st.session_state.total_cost:,.0f}")
else:
    st.info("No hay plan generado todavía. Seleccione asignaturas aprobadas y pulse 'Generar plan de estudios'.")

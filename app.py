# app.py
# Interfaz de Streamlit para el orientador de plan de estudios

import streamlit as st
import networkx as nx
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

    G = build_curriculum_graph(courses)

# ---------- Selección de asignaturas aprobadas ----------
st.subheader("Seleccione las asignaturas aprobadas")

# Construir lista de opciones "Semestre X: Nombre materia"
options = []
for semester in range(1, 11):
    if courses_by_semester:
        semester_courses = courses_by_semester.get(semester, [])
    else:
        semester_courses = [
            course for course, info in courses.items() if info.get("semester") == semester
        ]
    options.extend([f"Semestre {semester}: {course}" for course in semester_courses])

# Preparar valor por defecto consistente con las opciones
default_selected = []
for course in st.session_state.approved_subjects:
    if course in courses:
        default_selected.append(f"Semestre {courses[course]['semester']}: {course}")

# Multiselect (guardamos texto "Semestre X: Nombre")
approved_selected_texts = st.multiselect(
    "Asignaturas aprobadas",
    options=options,
    default=default_selected,
    key="approved_subjects_multiselect",
)

# Convertir a lista de nombres de asignaturas (solo la parte después de ": ")
approved_subjects = [s.split(": ", 1)[1] for s in approved_selected_texts]
# Guardar en el estado de sesión (lista de strings)
st.session_state.approved_subjects = approved_subjects

# ---------- Calcular semestre actual (manejo seguro) ----------
try:
    total_credits_approved = sum(
        G.nodes[course]["credits"] for course in st.session_state.approved_subjects if course in G.nodes
    )
except Exception:
    total_credits_approved = 0
current_semester = calculate_semester(total_credits_approved)
st.write(f"**Semestre actual**: {current_semester} (Créditos aprobados: {total_credits_approved})")

# ---------- Función para generar/actualizar plan ----------
def update_plan():
    # Recalcular semestre actual a partir del estado (por si cambió aprobado_subjects)
    total_credits = sum(G.nodes[c]["credits"] for c in st.session_state.approved_subjects if c in G.nodes)
    cur_sem = calculate_semester(total_credits)

    # Asegurarse de tener opciones por semestre inicializadas (de cur_sem a 10)
    for semester in range(cur_sem, 11):
        st.session_state.semester_options.setdefault(
            semester,
            {"is_half_time": False, "extra_credits": 0, "intersemestral": None},
        )

    # Generar plan (generate_full_plan no está cacheado porque depende de estado mutable)
    plan, total_cost = generate_full_plan(
        G,
        st.session_state.approved_subjects,
        program,
        credits_per_semester,
        calculate_semester,
        st.session_state.semester_options,
    )
    st.session_state.plan = plan
    st.session_state.total_cost = total_cost


# Si las asignaturas aprobadas cambiaron desde la última vez -> actualizar plan
if sorted(st.session_state.approved_subjects) != sorted(st.session_state.previous_approved_subjects):
    update_plan()
    st.session_state.previous_approved_subjects = st.session_state.approved_subjects.copy()

# ---------- Mostrar plan en pestañas ----------
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")

    # Preparar etiquetas y crear pestañas
    labels = [f"Semestre {p['semester']}{' (repetido)' if p.get('repetition', 1) > 1 else ''}" for p in st.session_state.plan]
    tabs = st.tabs(labels)

    for i, (tab, semester_plan) in enumerate(zip(tabs, st.session_state.plan)):
        with tab:
            semester = semester_plan["semester"]
            effective_semester = min(semester, 10)

            # Asegurar que exista entry en semester_options
            st.session_state.semester_options.setdefault(
                semester, {"is_half_time": False, "extra_credits": 0, "intersemestral": None}
            )

            # Media matrícula
            is_half_time = st.checkbox(
                f"Media matrícula (máx {credits_per_semester[effective_semester] // 2 - 1} créditos, costo $5,000,000)",
                value=st.session_state.semester_options[semester].get("is_half_time", False),
                key=f"half_time_{semester}_{i}",
                on_change=update_plan,
            )

            # Créditos extra: límite robusto y no-negativo
            # Interpretación: cap máximo de créditos extra permitidos (no negativo)
            max_extra_credits = 1 if is_half_time else max(0, 25 - credits_per_semester.get(effective_semester, 0))
            extra_credits = st.slider(
                f"Créditos extra a comprar (máx {max_extra_credits}, $800,000 por crédito)",
                0,
                max_extra_credits,
                st.session_state.semester_options[semester].get("extra_credits", 0),
                key=f"extra_credits_{semester}_{i}",
                on_change=update_plan,
            )

            # Intersemestral
            intersemestral_options = get_intersemestral_options(G, tuple(st.session_state.approved_subjects))
            intersemestral_display_options = ["Ninguno"] + intersemestral_options
            current_inter = st.session_state.semester_options[semester].get("intersemestral")
            default_index = 0
            if current_inter and current_inter in intersemestral_options:
                default_index = intersemestral_display_options.index(current_inter)
            intersemestral = st.selectbox(
                f"Intersemestral (opcional, $1,500,000)",
                intersemestral_display_options,
                index=default_index,
                key=f"intersemestral_{semester}_{i}",
                on_change=update_plan,
            )

            # Guardar las opciones del usuario
            st.session_state.semester_options[semester] = {
                "is_half_time": is_half_time,
                "extra_credits": extra_credits,
                "intersemestral": intersemestral if intersemestral != "Ninguno" else None,
            }

            # Mostrar información del semestre recomendado
            sem_credits = semester_plan.get("credits", 0)
            displayed_capacity = credits_per_semester.get(effective_semester, 0)
            if semester_plan.get("is_half_time"):
                displayed_capacity = displayed_capacity // 2 - 1

            st.write(f"**Créditos**: {sem_credits} de {displayed_capacity} disponibles (Intersemestral: {semester_plan.get('intersemestral_credits', 0)} créditos)")
            st.write(f"**Costo**: ${semester_plan.get('cost', 0):,.0f}")
            if semester_plan.get("is_half_time"):
                st.write("**Media matrícula** (recomendada para optimizar costos)")
            if semester_plan.get("extra_credits", 0) > 0:
                st.write(f"**Créditos extra comprados**: {semester_plan['extra_credits']} (recomendado para reducir semestres)")
            if semester_plan.get("intersemestral"):
                st.write(f"**Intersemestral**: {semester_plan['intersemestral']} (recomendado para optimizar costos)")

            st.write("**Asignaturas recomendadas**:")
            for subject in semester_plan.get("subjects", []):
                credits = G.nodes[subject]["credits"] if subject in G.nodes else "?"
                st.write(f"- {subject} ({credits} créditos)")

    st.write(f"**Costo total estimado**: ${st.session_state.total_cost:,.0f}")
else:
    st.info("No hay plan generado todavía. Seleccione asignaturas aprobadas para generar el plan.")

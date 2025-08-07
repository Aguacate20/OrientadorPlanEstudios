# app.py
# Interfaz de Streamlit para el orientador de plan de estudios

import streamlit as st
import networkx as nx
from courses_data import fisioterapia_courses, enfermeria_courses, credits_per_semester_fisioterapia, credits_per_semester_enfermeria, calculate_semester_fisioterapia, calculate_semester_enfermeria
try:
    from courses_data import fisioterapia_courses_by_semester, enfermeria_courses_by_semester
except ImportError:
    fisioterapia_courses_by_semester = None
    enfermeria_courses_by_semester = None
from curriculum import build_curriculum_graph, generate_full_plan, get_intersemestral_options

# Inicializar estado de sesión
if "approved_subjects" not in st.session_state:
    st.session_state.approved_subjects = []
if "semester_options" not in st.session_state:
    st.session_state.semester_options = {}
if "plan" not in st.session_state:
    st.session_state.plan = None
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0
if "previous_approved_subjects" not in st.session_state:
    st.session_state.previous_approved_subjects = []

st.title("Orientador de Plan de Estudios")

# Selección del programa
with st.spinner("Cargando datos iniciales..."):
    program = st.selectbox("Seleccione su programa", ["Fisioterapia", "Enfermería"])
    courses = fisioterapia_courses if program == "Fisioterapia" else enfermeria_courses
    credits_per_semester = credits_per_semester_fisioterapia if program == "Fisioterapia" else credits_per_semester_enfermeria
    calculate_semester = calculate_semester_fisioterapia if program == "Fisioterapia" else calculate_semester_enfermeria
    courses_by_semester = fisioterapia_courses_by_semester if program == "Fisioterapia" else enfermeria_courses_by_semester

    G = build_curriculum_graph(courses)

# Selección de asignaturas aprobadas
st.subheader("Seleccione las asignaturas aprobadas")
approved_subjects = []
options = []
for semester in range(1, 11):
    if courses_by_semester:
        semester_courses = courses_by_semester.get(semester, [])
    else:
        semester_courses = [course for course, info in courses.items() if info["semester"] == semester]
    options.extend([f"Semestre {semester}: {course}" for course in semester_courses])

approved_subjects = st.multiselect(
    "Asignaturas aprobadas",
    options=options,
    default=[f"Semestre {courses[course]['semester']}: {course}" for course in st.session_state.approved_subjects],
    key="approved_subjects_multiselect"
)
approved_subjects = [s.split(": ")[1] for s in approved_subjects]

# Actualizar asignaturas aprobadas en el estado
st.session_state.approved_subjects = approved_subjects

# Calcular semestre actual
total_credits_approved = sum(G.nodes[course]["credits"] for course in approved_subjects)
current_semester = calculate_semester(total_credits_approved)
st.write(f"**Semestre actual**: {current_semester} (Créditos aprobados: {total_credits_approved})")

# Función para generar o actualizar el plan
def update_plan():
    if not st.session_state.semester_options or not st.session_state.semester_options.get(current_semester):
        st.session_state.semester_options = {}
        for semester in range(current_semester, 11):
            st.session_state.semester_options[semester] = {
                "is_half_time": False,
                "extra_credits": 0,
                "intersemestral": None
            }
    
    with st.spinner("Generando plan de estudios recomendado..."):
        st.session_state.plan, st.session_state.total_cost = generate_full_plan(
            G, st.session_state.approved_subjects, program, credits_per_semester, calculate_semester, st.session_state.semester_options
        )

# Verificar si las asignaturas aprobadas han cambiado
if sorted(st.session_state.approved_subjects) != sorted(st.session_state.previous_approved_subjects):
    update_plan()
    st.session_state.previous_approved_subjects = st.session_state.approved_subjects.copy()

# Mostrar plan en pestañas
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")
    tabs = st.tabs([f"Semestre {p['semester']}{' (repetido)' if p['repetition'] > 1 else ''}" for p in st.session_state.plan])
    for i, (tab, semester_plan) in enumerate(zip(tabs, st.session_state.plan)):
        with tab:
            semester = semester_plan["semester"]
            effective_semester = min(semester, 10)
            
            is_half_time = st.checkbox(
                f"Media matrícula (máximo {credits_per_semester[effective_semester] // 2 - 1} créditos, costo $5,000,000)",
                value=st.session_state.semester_options[semester]["is_half_time"],
                key=f"half_time_{semester}_{i}",
                on_change=update_plan
            )
            max_extra_credits = 1 if is_half_time else 25 - credits_per_semester[effective_semester]
            extra_credits = st.slider(
                f"Créditos extra a comprar (máximo {max_extra_credits}, $800,000 por crédito)",
                0, max_extra_credits, st.session_state.semester_options[semester]["extra_credits"],
                key=f"extra_credits_{semester}_{i}",
                on_change=update_plan
            )
            intersemestral_options = get_intersemestral_options(G, st.session_state.approved_subjects)
            intersemestral = st.selectbox(
                f"Intersemestral (opcional, $1,500,000)",
                ["Ninguno"] + intersemestral_options,
                index=intersemestral_options.index(st.session_state.semester_options[semester]["intersemestral"]) + 1 if st.session_state.semester_options[semester]["intersemestral"] in intersemestral_options else 0,
                key=f"intersemestral_{semester}_{i}",
                on_change=update_plan
            )
            
            st.session_state.semester_options[semester] = {
                "is_half_time": is_half_time,
                "extra_credits": extra_credits,
                "intersemestral": intersemestral if intersemestral != "Ninguno" else None
            }
            
            st.write(f"**Créditos**: {semester_plan['credits']} de {credits_per_semester[effective_semester] if not semester_plan['is_half_time'] else credits_per_semester[effective_semester] // 2 - 1} disponibles (Intersemestral: {semester_plan['intersemestral_credits']} créditos)")
            st.write(f"**Costo**: ${semester_plan['cost']:,.0f}")
            if semester_plan["is_half_time"]:
                st.write("**Media matrícula** (recomendada para optimizar costos)")
            if semester_plan["extra_credits"] > 0:
                st.write(f"**Créditos extra comprados**: {semester_plan['extra_credits']} (recomendado para reducir semestres)")
            if semester_plan["intersemestral"]:
                st.write(f"**Intersemestral**: {semester_plan['intersemestral']} (recomendado para optimizar costos)")
            st.write("**Asignaturas recomendadas**:")
            for subject in semester_plan["subjects"]:
                st.write(f"- {subject} ({G.nodes[subject]['credits']} créditos)")
    
    st.write(f"**Costo total estimado**: ${st.session_state.total_cost:,.0f}")

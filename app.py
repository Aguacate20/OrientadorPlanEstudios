import streamlit as st
import networkx as nx
from courses_data import fisioterapia_courses, enfermeria_courses, credits_per_semester_fisioterapia, credits_per_semester_enfermeria, calculate_semester_fisioterapia, calculate_semester_enfermeria
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
if "update_triggered" not in st.session_state:
    st.session_state.update_triggered = False

st.title("Orientador de Plan de Estudios")

# Selección del programa
program = st.selectbox("Seleccione su programa", ["Fisioterapia", "Enfermería"])
courses = fisioterapia_courses if program == "Fisioterapia" else enfermeria_courses
credits_per_semester = credits_per_semester_fisioterapia if program == "Fisioterapia" else credits_per_semester_enfermeria
calculate_semester = calculate_semester_fisioterapia if program == "Fisioterapia" else calculate_semester_enfermeria

# Construir grafo
G, prereq_cache = build_curriculum_graph(courses)

# Selección de asignaturas aprobadas
st.subheader("Seleccione las asignaturas aprobadas")
approved_subjects = []
for semester in range(1, 11):
    semester_courses = [course for course, info in courses.items() if info["semester"] == semester]
    if semester_courses:
        with st.expander(f"Semestre {semester}"):
            for course in semester_courses:
                key = f"course_{semester}_{course}"
                if key not in st.session_state:
                    st.session_state[key] = course in st.session_state.approved_subjects
                selected = st.checkbox(
                    course,
                    value=st.session_state[key],
                    key=key
                )
                if selected:
                    approved_subjects.append(course)

# Botón para confirmar actualización
if st.button("Actualizar Plan"):
    st.session_state.approved_subjects = approved_subjects
    st.session_state.update_triggered = True

# Calcular semestre actual
total_credits_approved = sum(G.nodes[course]["credits"] for course in st.session_state.approved_subjects)
current_semester = min(calculate_semester(total_credits_approved), 10)
st.write(f"**Semestre actual**: {current_semester} (Créditos aprobados: {total_credits_approved})")

# Función para generar o actualizar el plan
@st.cache_data
def update_plan(_G_tuple, _approved_subjects, _program, _credits_per_semester, _calculate_semester, _semester_options):
    G, prereq_cache = _G_tuple
    # Create a copy of semester_options to avoid mutating cached input
    semester_options_copy = {k: v.copy() for k, v in _semester_options.items()}
    current_semester = min(_calculate_semester(sum(G.nodes[course]["credits"] for course in _approved_subjects)), 10)
    
    # Inicializar opciones por semestre si no existen
    if not semester_options_copy or not semester_options_copy.get(current_semester):
        semester_options_copy = {}
        for semester in range(current_semester, 11):
            semester_options_copy[semester] = {
                "is_half_time": False,
                "extra_credits": 0,
                "intersemestral": None
            }
    
    # Generar el plan
    plan, total_cost = generate_full_plan(
        (G, prereq_cache), _approved_subjects, _program, _credits_per_semester, _calculate_semester, semester_options_copy
    )
    return plan, total_cost, semester_options_copy

# Actualizar plan solo si se presionó el botón y las asignaturas cambiaron
if st.session_state.update_triggered and sorted(st.session_state.approved_subjects) != sorted(st.session_state.previous_approved_subjects):
    st.session_state.plan, st.session_state.total_cost, st.session_state.semester_options = update_plan(
        (G, prereq_cache), st.session_state.approved_subjects, program, credits_per_semester, calculate_semester, st.session_state.semester_options
    )
    st.session_state.previous_approved_subjects = st.session_state.approved_subjects.copy()
    st.session_state.update_triggered = False

# Mostrar plan en pestañas
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")
    tabs = st.tabs([f"Semestre {p['semester']}" for p in st.session_state.plan])
    for i, (tab, semester_plan) in enumerate(zip(tabs, st.session_state.plan)):
        with tab:
            semester = semester_plan["semester"]
            
            # Configuración del semestre
            is_half_time = st.checkbox(
                f"Media matrícula (máximo {credits_per_semester[semester] // 2 - 1} créditos, costo $5,000,000)",
                value=st.session_state.semester_options[semester]["is_half_time"],
                key=f"half_time_{semester}_{i}"
            )
            max_extra_credits = 1 if is_half_time else 25 - credits_per_semester[semester]
            extra_credits = st.slider(
                f"Créditos extra a comprar (máximo {max_extra_credits}, $800,000 por crédito)",
                0, max_extra_credits, st.session_state.semester_options[semester]["extra_credits"],
                key=f"extra_credits_{semester}_{i}"
            )
            intersemestral_options = get_intersemestral_options((G, prereq_cache), st.session_state.approved_subjects)
            intersemestral = st.selectbox(
                f"Intersemestral (opcional, $1,500,000)",
                ["Ninguno"] + intersemestral_options,
                index=intersemestral_options.index(st.session_state.semester_options[semester]["intersemestral"]) + 1 if st.session_state.semester_options[semester]["intersemestral"] in intersemestral_options else 0,
                key=f"intersemestral_{semester}_{i}"
            )
            
            # Actualizar opciones en el estado
            if st.session_state.semester_options[semester]["is_half_time"] != is_half_time or \
               st.session_state.semester_options[semester]["extra_credits"] != extra_credits or \
               st.session_state.semester_options[semester]["intersemestral"] != (intersemestral if intersemestral != "Ninguno" else None):
                st.session_state.semester_options[semester] = {
                    "is_half_time": is_half_time,
                    "extra_credits": extra_credits,
                    "intersemestral": intersemestral if intersemestral != "Ninguno" else None
                }
                st.session_state.plan, st.session_state.total_cost, st.session_state.semester_options = update_plan(
                    (G, prereq_cache), st.session_state.approved_subjects, program, credits_per_semester, calculate_semester, st.session_state.semester_options
                )
            
            # Mostrar detalles del semestre
            st.write(f"**Créditos**: {semester_plan['credits']} de {credits_per_semester[semester_plan['semester']] if not semester_plan['is_half_time'] else credits_per_semester[semester_plan['semester']] // 2 - 1} disponibles (Intersemestral: {semester_plan['intersemestral_credits']} créditos)")
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

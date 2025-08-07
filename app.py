# app.py
# Interfaz de Streamlit para el orientador de plan de estudios

import streamlit as st
import networkx as nx
from courses_data import fisioterapia_courses, enfermeria_courses, credits_per_semester_fisioterapia, credits_per_semester_enfermeria, calculate_semester_fisioterapia, calculate_semester_enfermeria
from curriculum import build_curriculum_graph, generate_full_plan, get_intersemestral_options

st.title("Orientador de Plan de Estudios")

# Selección del programa
program = st.selectbox("Seleccione su programa", ["Fisioterapia", "Enfermería"])
courses = fisioterapia_courses if program == "Fisioterapia" else enfermeria_courses
credits_per_semester = credits_per_semester_fisioterapia if program == "Fisioterapia" else credits_per_semester_enfermeria
calculate_semester = calculate_semester_fisioterapia if program == "Fisioterapia" else calculate_semester_enfermeria

# Construir grafo
G = build_curriculum_graph(courses)

# Selección de asignaturas aprobadas
st.subheader("Seleccione las asignaturas aprobadas")
approved_subjects = []
for semester in range(1, 11):
    semester_courses = [course for course, info in courses.items() if info["semester"] == semester]
    if semester_courses:
        st.write(f"Semestre {semester}")
        selected = st.multiselect(f"Asignaturas aprobadas del semestre {semester}", semester_courses, key=f"sem_{semester}")
        approved_subjects.extend(selected)

# Calcular semestre actual
total_credits_approved = sum(G.nodes[course]["credits"] for course in approved_subjects)
current_semester = calculate_semester(total_credits_approved)
st.write(f"**Semestre actual**: {current_semester} (Créditos aprobados: {total_credits_approved})")

# Opciones por semestre
st.subheader("Configuración de semestres")
semester_options = {}
for semester in range(current_semester, 11):
    with st.expander(f"Semestre {semester}"):
        is_half_time = st.checkbox(f"Media matrícula (máximo {credits_per_semester[semester] // 2 - 1} créditos)", key=f"half_time_{semester}")
        max_extra_credits = 1 if is_half_time else 25 - credits_per_semester[semester]
        extra_credits = st.slider(f"Créditos extra a comprar (máximo {max_extra_credits})", 0, max_extra_credits, 0, key=f"extra_credits_{semester}")
        intersemestral_options = get_intersemestral_options(G, approved_subjects)
        intersemestral = st.selectbox(f"Intersemestral (opcional)", ["Ninguno"] + intersemestral_options, key=f"intersemestral_{semester}")
        semester_options[semester] = {
            "is_half_time": is_half_time,
            "extra_credits": extra_credits,
            "intersemestral": intersemestral if intersemestral != "Ninguno" else None
        }

# Generar plan
if st.button("Generar plan de estudios"):
    plan, total_cost = generate_full_plan(G, approved_subjects, program, credits_per_semester, calculate_semester, semester_options)
    st.subheader("Plan de estudios recomendado")
    
    # Usar pestañas para cada semestre
    tabs = st.tabs([f"Semestre {p['semester']}" for p in plan])
    for i, (tab, semester_plan) in enumerate(zip(tabs, plan)):
        with tab:
            st.write(f"**Créditos**: {semester_plan['credits']} (Intersemestral: {semester_plan['intersemestral_credits']} créditos)")
            st.write(f"**Costo**: ${semester_plan['cost']:,.0f}")
            if semester_plan["is_half_time"]:
                st.write("**Media matrícula**")
            if semester_plan["extra_credits"] > 0:
                st.write(f"**Créditos extra comprados**: {semester_plan['extra_credits']}")
            if semester_plan["intersemestral"]:
                st.write(f"**Intersemestral**: {semester_plan['intersemestral']}")
            st.write("**Asignaturas recomendadas**:")
            for subject in semester_plan["subjects"]:
                st.write(f"- {subject} ({G.nodes[subject]['credits']} créditos)")
    
    st.write(f"**Costo total estimado**: ${total_cost:,.0f}")

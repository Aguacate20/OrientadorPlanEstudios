# app.py
# Interfaz de Streamlit para el orientador de plan de estudios (check + botón)
# Mejora: si hay muchas pestañas, mostramos un selectbox para garantizar acceso a semestres altos.

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
# UI visual toggle: ocultar valores numéricos financieros (costos/tiempos)
# NOTA: créditos SIEMPRE se muestran.
# ---------------------------
HIDE_VALUES = True  # <-- poner False si quieres ver también costs/time para debug (no afecta créditos)

# ---------- Ajuste visual ----------
TAB_MAX = 8  # si hay más de TAB_MAX entradas en el plan, usamos selector en lugar de pestañas

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

    # build_curriculum_graph recibe program como primer argumento
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
# Mostrar semestre actual y créditos aprobados
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

    # Sincronizar recomendaciones para que aparezcan marcadas en semester_options
    for sem_entry in plan:
        sem = sem_entry.get("semester")
        if sem is None:
            continue
        st.session_state.semester_options.setdefault(sem, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})
        st.session_state.semester_options[sem]["is_half_time"] = bool(sem_entry.get("is_half_time", False))
        st.session_state.semester_options[sem]["extra_credits"] = int(sem_entry.get("extra_credits", 0))
        st.session_state.semester_options[sem]["intersemestral"] = sem_entry.get("intersemestral")

    # Mostrar tiempo si no está oculto
    if not HIDE_VALUES:
        st.write(f"⏱️ Tiempo de cálculo del plan: {elapsed:.3f} segundos")

# ---------- Callback de submit: lee LOS ESTADOS REALES de los checkboxes y actualiza ----------
def handle_submit():
    selected = []
    for semester in range(1, 11):
        if courses_by_semester:
            semester_courses = courses_by_semester.get(semester, [])
        else:
            semester_courses = [course for course, info in courses.items() if info.get("semester") == semester]
        for idx, course in enumerate(semester_courses):
            key = f"approved_chk_{program}_{semester}_{idx}_{course}"
            if st.session_state.get(key, False):
                selected.append(course)

    st.session_state.approved_subjects = selected
    sem_now, _ = _current_semester_from_approved()
    for s in range(sem_now, 11):
        st.session_state.semester_options.setdefault(s, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})

    update_plan()

# ---------- Selección de asignaturas aprobadas via FORM (checkboxes) ----------
st.subheader("Seleccione las asignaturas aprobadas (por semestre)")

with st.form("approved_form"):
    for semester in range(1, 11):
        if courses_by_semester:
            semester_courses = courses_by_semester.get(semester, [])
        else:
            semester_courses = [course for course, info in courses.items() if info.get("semester") == semester]

        with st.expander(f"Semestre {semester} ({len(semester_courses)} asignaturas)", expanded=(semester == current_semester)):
            for idx, course in enumerate(semester_courses):
                key = f"approved_chk_{program}_{semester}_{idx}_{course}"
                default = course in st.session_state.approved_subjects
                st.checkbox(course, value=default, key=key)

    st.form_submit_button("Generar plan de estudios", on_click=handle_submit)

# ---------- Helper para renderizar el contenido de un semestre (reutilizable) ----------
def render_semester_content(i: int, semester_plan: Dict[str, Any]):
    """
    i: índice en la lista plan (usa para generar keys únicas)
    semester_plan: diccionario con keys: semester, subjects, credits, intersemestral, intersemestral_credits, is_half_time, extra_credits, cost, ...
    """
    semester = semester_plan["semester"]
    effective_semester = min(semester, 10)

    st.session_state.semester_options.setdefault(semester, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})

    half_time_key = f"half_time_{program}_{semester}_{i}"
    is_half_time = st.checkbox(
        f"Media matrícula (máx {credits_per_semester.get(effective_semester, 0) // 2 - 1} créditos)",
        value=st.session_state.semester_options[semester].get("is_half_time", False),
        key=half_time_key,
    )

    max_extra_credits = 1 if is_half_time else max(0, 25 - credits_per_semester.get(effective_semester, 0))
    extra_key = f"extra_credits_{program}_{semester}_{i}"
    extra_credits = st.slider(
        f"Créditos extra a comprar (máx {max_extra_credits})",
        0,
        max_extra_credits,
        st.session_state.semester_options[semester].get("extra_credits", 0),
        key=extra_key,
    )

    temp_approved_for_inter = set(st.session_state.approved_subjects)
    rec_subjects_for_this_sem = semester_plan.get("subjects", [])
    temp_approved_for_inter.update(rec_subjects_for_this_sem)

    intersemestral_options = get_intersemestral_options(G, tuple(temp_approved_for_inter))
    rec_inter = semester_plan.get("intersemestral")
    intersemestral_display_options = ["Ninguno"] + intersemestral_options
    if rec_inter and rec_inter not in intersemestral_display_options:
        intersemestral_display_options.append(rec_inter)

    current_inter = st.session_state.semester_options[semester].get("intersemestral")
    default_index = 0
    if current_inter and current_inter in intersemestral_display_options:
        default_index = intersemestral_display_options.index(current_inter)
    inter_key = f"intersemestral_{program}_{semester}_{i}"
    intersemestral_selected = st.selectbox(
        f"Intersemestral (opcional)",
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

    # ------------------ Mostrar créditos (SIEMPRE) ------------------
    base_cap = credits_per_semester.get(effective_semester, 0)
    opts = st.session_state.semester_options.get(semester, {})
    cap_effective = base_cap
    if opts.get("is_half_time"):
        cap_effective = max(0, base_cap // 2 - 1)
    cap_effective += int(opts.get("extra_credits", 0)) if opts else 0

    credits_recommended = semester_plan.get("credits", 0)
    inter_credits = semester_plan.get("intersemestral_credits", 0)

    st.markdown("**Resumen de créditos (ajustables con opciones actuales):**")
    st.write(f"- Capacidad efectiva del semestre: **{cap_effective}** créditos")
    st.write(f"- Créditos recomendados por el plan en este semestre: **{credits_recommended}** créditos")
    if inter_credits:
        st.write(f"- Créditos intersemestrales recomendados (serán considerados como aprobados si se activan): **{inter_credits}** créditos")
    gap = max(0, cap_effective - (credits_recommended + (inter_credits if inter_credits else 0)))
    st.write(f"- Hueco (capacidad restante si se aceptan las recomendaciones): **{gap}** créditos")

    st.write("**Asignaturas recomendadas (con créditos):**")
    for subject in semester_plan.get("subjects", []):
        credits = G.nodes[subject]["credits"] if subject in G.nodes else "?"
        st.write(f"- {subject} — **{credits}** créditos")

    if semester_plan.get("intersemestral"):
        intername = semester_plan.get("intersemestral")
        intercr = G.nodes[intername]["credits"] if intername in G.nodes else 0
        st.write(f"**Intersemestral recomendado por el plan:** {intername} — **{intercr}** créditos")

    if not HIDE_VALUES:
        st.write(f"**Costo**: ${semester_plan.get('cost', 0):,.0f}")
        if semester_plan.get("is_half_time"):
            st.write("**Media matrícula** (recomendada para optimizar costos)")
        if semester_plan.get("extra_credits", 0) > 0:
            st.write(f"**Créditos extra recomendados**: {semester_plan['extra_credits']}")

# ---------- Mostrar plan en pestañas o selector (según tamaño) ----------
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")
    if st.session_state.last_plan_time is not None and not HIDE_VALUES:
        st.info(f"Último cálculo: {st.session_state.last_plan_time:.3f} s")

    if st.button("Recalcular plan con opciones actuales"):
        with st.spinner("Recalculando plan..."):
            update_plan()
        st.success("Plan recalculado ✅")

    labels = [f"Semestre {p['semester']}{' (repetido)' if p.get('repetition', 1) > 1 else ''}" for p in st.session_state.plan]

    if len(labels) <= TAB_MAX:
        # Usamos pestañas cuando no son muchas
        tabs = st.tabs(labels)
        for i, (tab, semester_plan) in enumerate(zip(tabs, st.session_state.plan)):
            with tab:
                render_semester_content(i, semester_plan)
    else:
        # Mostramos un selectbox para navegar (asegura acceso incluso en pantallas estrechas)
        sel = st.selectbox("Seleccionar semestre a visualizar", options=labels, index=0)
        sel_idx = labels.index(sel)
        # mostramos el contenido del semestre seleccionado
        render_semester_content(sel_idx, st.session_state.plan[sel_idx])

    # No mostramos costo total si HIDE_VALUES True
    if not HIDE_VALUES:
        st.write(f"**Costo total estimado**: ${st.session_state.total_cost:,.0f}")
else:
    st.info("No hay plan generado todavía. Seleccione asignaturas aprobadas y pulse 'Generar plan de estudios'.")

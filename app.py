# app.py
# Interfaz de Streamlit para el orientador de plan de estudios (check + botón)
# Muestra créditos por semestre y añade barra horizontal desplazable con resumen por semestre.
# No muestra valores financieros.

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
# UI visual toggle: ocultar valores monetarios (costos/tiempos)
# ---------------------------
# Nota: los CRÉDITOS se mostrarán siempre (según tu petición). HIDE_VALUES solo controla tiempos/costos debug.
HIDE_VALUES = True  # poner False si quieres ver tiempo/costos (pero no se muestran créditos)

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

    # build_curriculum_graph recibe program como primer argumento (asegura grafos separados)
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
# Mostrar semestre actual (ocultar créditos si HIDE_VALUES sigue True, pero igual mostramos semestre)
st.write(f"**Semestre actual (estimado)**: {current_semester}")

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

    # Sincronizar recomendaciones con la UI: aplicar las sugerencias en semester_options
    for sem_entry in plan:
        sem = sem_entry.get("semester")
        if sem is None:
            continue
        st.session_state.semester_options.setdefault(sem, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})
        st.session_state.semester_options[sem]["is_half_time"] = bool(sem_entry.get("is_half_time", False))
        st.session_state.semester_options[sem]["extra_credits"] = int(sem_entry.get("extra_credits", 0))
        st.session_state.semester_options[sem]["intersemestral"] = sem_entry.get("intersemestral")

    # Mostramos tiempo solo si HIDE_VALUES=False (debug)
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

    # Generar plan (y sincronizar recomendaciones con las opciones UI)
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
                default = course in st.session_state.approved_subjects
                st.checkbox(course, value=default, key=key)

    # Botón del formulario: al enviarlo actualizamos los aprobados y generamos plan
    st.form_submit_button("Generar plan de estudios", on_click=handle_submit)

# ---------- Mostrar plan en pestañas (si existe) ----------
if st.session_state.plan:
    st.subheader("Plan de estudios recomendado")

    # Barra horizontal desplazable resumen por semestre (resumen compacto)
    # Construimos HTML con overflow-x:auto; cada tarjeta es inline-block
    cards_html = []
    for sem_entry in st.session_state.plan:
        sem = sem_entry.get("semester")
        cap_base = credits_per_semester.get(min(sem, 10), 0)
        opts = st.session_state.semester_options.get(sem, {})
        if opts.get("is_half_time"):
            cap_eff = max(0, cap_base // 2 - 1)
        else:
            cap_eff = cap_base
        cap_eff += int(opts.get("extra_credits", 0) or 0)
        credits_taken = sem_entry.get("credits", 0)
        inter_credits = sem_entry.get("intersemestral_credits", 0)
        # compact list of subjects with credits (comma-separated)
        subj_list = ", ".join([f"{s} ({G.nodes[s]['credits']}c)" for s in sem_entry.get("subjects", [])])
        if sem_entry.get("intersemestral"):
            subj_list = f"{subj_list}, [+{sem_entry.get('intersemestral')} ({inter_credits}c)]" if subj_list else f"{sem_entry.get('intersemestral')} ({inter_credits}c)"
        card = f"""
            <div class="sem-card" style="
                display:inline-block;
                border:1px solid #ddd;
                border-radius:8px;
                padding:8px;
                margin-right:8px;
                min-width:220px;
                max-width:320px;
                vertical-align:top;
                background:#fafafa;
            ">
                <div style="font-weight:600;">Sem {sem}</div>
                <div style="font-size:13px;">Créditos recomendados: <strong>{credits_taken}</strong> / {cap_eff}</div>
                <div style="font-size:12px; margin-top:6px; color:#222;">{subj_list}</div>
            </div>
        """
        cards_html.append(card)

    scroll_wrapper = f"""
    <div style="overflow-x:auto; padding:6px 4px; border-bottom:1px solid #eee; margin-bottom:12px; white-space:nowrap;">
        {''.join(cards_html)}
    </div>
    """
    st.markdown(scroll_wrapper, unsafe_allow_html=True)

    # Mostrar tiempo de la última generación si no ocultamos (debug)
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

            # Mostrar CRÉDITOS: capacidad efectiva según opciones actuales
            base_cap = credits_per_semester.get(effective_semester, 0)
            opts = st.session_state.semester_options.get(semester, {})
            if opts.get("is_half_time"):
                cap_eff = max(0, base_cap // 2 - 1)
                st.write("**Media matrícula activada para este semestre**")
            else:
                cap_eff = base_cap
            cap_eff += int(opts.get("extra_credits", 0) or 0)

            credits_recommended = semester_plan.get("credits", 0)
            inter_credits = semester_plan.get("intersemestral_credits", 0)

            # Mostrar créditos (siempre visible, como pediste). No mostrar valores monetarios.
            st.write(f"**Créditos recomendados para este semestre**: {credits_recommended} (Capacidad efectiva: {cap_eff})")
            if inter_credits:
                st.write(f"**Créditos intersemestral incluidos**: {inter_credits}")

            # Media matrícula checkbox (estado viene de semester_options)
            half_time_key = f"half_time_{program}_{semester}_{i}"
            is_half_time = st.checkbox(
                f"Media matrícula (máx {credits_per_semester.get(effective_semester, 0) // 2 - 1} créditos)",
                value=st.session_state.semester_options[semester].get("is_half_time", False),
                key=half_time_key,
            )

            # Créditos extra (slider)
            max_extra_credits = 1 if is_half_time else max(0, 25 - credits_per_semester.get(effective_semester, 0))
            extra_key = f"extra_credits_{program}_{semester}_{i}"
            extra_credits = st.slider(
                f"Créditos extra a comprar (máx {max_extra_credits})",
                0,
                max_extra_credits,
                st.session_state.semester_options[semester].get("extra_credits", 0),
                key=extra_key,
            )

            # Intersemestral: opciones calculadas considerando las materias recomendadas de este semestre
            temp_approved_for_inter = set(st.session_state.approved_subjects)
            temp_approved_for_inter.update(semester_plan.get("subjects", []))
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

            # Mostrar las asignaturas recomendadas con CRÉDITOS por asignatura
            st.write("**Asignaturas recomendadas (con créditos)**:")
            for subject in semester_plan.get("subjects", []):
                credits = G.nodes[subject]["credits"] if subject in G.nodes else "?"
                st.write(f"- {subject} — {credits} créditos")

            if semester_plan.get("intersemestral"):
                ic = semester_plan.get("intersemestral_credits", 0)
                st.write(f"**Intersemestral recomendado:** {semester_plan.get('intersemestral')} — {ic} créditos")

    # Mostrar resumen total de créditos (no mostrar costos financieros)
    total_credits_all = sum(p.get("credits", 0) + p.get("intersemestral_credits", 0) for p in st.session_state.plan)
    st.write(f"**Créditos totales recomendados en el plan:** {total_credits_all}")

else:
    st.info("No hay plan generado todavía. Seleccione asignaturas aprobadas y pulse 'Generar plan de estudios'.")

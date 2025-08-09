# app.py
# Interfaz de Streamlit para el orientador de plan de estudios (check + botón)
# Cambios:
# - Mostrar siempre créditos (totales del semestre, créditos recomendados, créditos por asignatura).
# - Añadir resumen horizontal scrollable (tarjetas por semestre) para poder ver semestres altos.

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
# UI visual toggle: ocultar valores monetarios (pero mostrar créditos)
# ---------------------------
# Si quieres ver también valores monetarios para debug pon False
HIDE_FINANCIALS = True

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

    # build_curriculum_graph(program, courses) - la función espera program como primer argumento
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
# Mostrar semestre actual (si quieres ocultar créditos elimina la segunda parte)
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

    # Sincronizar recomendaciones con las opciones UI (marca las sugerencias)
    for sem_entry in plan:
        sem = sem_entry.get("semester")
        if sem is None:
            continue
        st.session_state.semester_options.setdefault(sem, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})
        # Sobrescribimos opciones con recomendación (usuario podrá cambiarlas y recalcular)
        st.session_state.semester_options[sem]["is_half_time"] = bool(sem_entry.get("is_half_time", False))
        st.session_state.semester_options[sem]["extra_credits"] = int(sem_entry.get("extra_credits", 0))
        st.session_state.semester_options[sem]["intersemestral"] = sem_entry.get("intersemestral")

    # Mostrar tiempo solo si no estamos ocultando valores
    if not HIDE_FINANCIALS:
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

    # Generar plan (y esto además sincronizará las recomendaciones con las opciones UI)
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
    # Mostrar tiempo de la última generación si no ocultamos valores financieros
    if st.session_state.last_plan_time is not None and not HIDE_FINANCIALS:
        st.info(f"Último cálculo: {st.session_state.last_plan_time:.3f} s")

    # Botón para recalcular plan con las opciones actuales (por si el usuario modificó media matrícula/extra/intersemestral)
    if st.button("Recalcular plan con opciones actuales"):
        with st.spinner("Recalculando plan..."):
            update_plan()
        st.success("Plan recalculado ✅")

    # ----------------------------
    # Resumen Horizontal (scrollable) - tarjeta por semestre
    # ----------------------------
    # Construimos HTML simple con overflow-x para permitir scroll horizontal con mouse
    plan = st.session_state.plan
    # solo renderizar el resumen si hay 2 o más semestres (o si quieres siempre)
    if plan:
        cards_html = """
        <div style="overflow-x:auto; white-space:nowrap; padding:8px 4px; margin-bottom:12px;">
        """
        for p in plan:
            sem = p.get("semester")
            credits = p.get("credits", 0)
            inter_credits = p.get("intersemestral_credits", 0)
            subjects = p.get("subjects", [])
            # card: inline-block
            card = f"""
            <div style="
                display:inline-block;
                vertical-align:top;
                width:320px;
                min-width:240px;
                margin-right:12px;
                padding:10px;
                border-radius:8px;
                box-shadow:0 1px 4px rgba(0,0,0,0.08);
                background:#ffffff;
                border:1px solid #eee;
                ">
                <div style="font-weight:600; margin-bottom:6px;">Semestre {sem}</div>
                <div style="font-size:14px; margin-bottom:6px;">
                    Créditos recomendados: <strong>{credits}</strong>
                    {"&nbsp;&middot;&nbsp;Intersemestral: <strong>" + str(inter_credits) + "</strong>" if inter_credits else ""}
                </div>
                <div style="font-size:13px; color:#111; margin-bottom:6px;">Asignaturas:</div>
                <ul style="padding-left:16px; margin:0; font-size:13px;">
            """
            for s in subjects:
                cr = G.nodes[s]["credits"] if s in G.nodes else "?"
                # escape minimal (replace < and >)
                safe_s = s.replace("<", "&lt;").replace(">", "&gt;")
                card += f"<li>{safe_s} ({cr} cr.)</li>"
            card += "</ul></div>"
            cards_html += card
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    # Preparar etiquetas y crear pestañas (interactividad detallada debajo)
    labels = [f"Semestre {p['semester']}{' (repetido)' if p.get('repetition', 1) > 1 else ''}" for p in plan]
    tabs = st.tabs(labels)

    for i, (tab, semester_plan) in enumerate(zip(tabs, plan)):
        with tab:
            semester = semester_plan["semester"]
            effective_semester = min(semester, 10)

            # Asegurar entry en semester_options
            st.session_state.semester_options.setdefault(semester, {"is_half_time": False, "extra_credits": 0, "intersemestral": None})

            # Media matrícula (NO dispara recálculo automático) - el estado viene de semester_options
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

            # Intersemestral: calculado teniendo en cuenta las materias recomendadas para este semestre
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

            # ---------- MOSTRAR CRÉDITOS SIEMPRE (sin mostrar monetario) ----------
            credits_shown = semester_plan.get('credits', 0)
            capacity_shown = credits_per_semester.get(effective_semester, 0)
            inter_credits_shown = semester_plan.get('intersemestral_credits', 0)

            # si el usuario activó media matrícula u otros, nos interesa reflejar el límite real
            opts = st.session_state.semester_options.get(semester, {})
            # calcular capacidad efectiva según las reglas (consistente con generate_full_plan)
            if opts.get("is_half_time"):
                effective_cap = max(0, capacity_shown // 2 - 1)
            else:
                effective_cap = capacity_shown
            effective_cap += int(opts.get("extra_credits", 0)) if opts else 0

            st.write(f"**Créditos recomendados en este semestre**: {credits_shown}  —  **Límite disponible**: {effective_cap} (Intersemestral: {inter_credits_shown})")

            # Mostrar las asignaturas recomendadas con créditos en todas circunstancias
            st.write("**Asignaturas recomendadas**:")
            for subject in semester_plan.get("subjects", []):
                credits = G.nodes[subject]["credits"] if subject in G.nodes else "?"
                st.write(f"- {subject} ({credits} créditos)")

            # Mostrar si hay intersemestral recomendado
            if semester_plan.get("intersemestral"):
                st.write(f"**Intersemestral recomendado**: {semester_plan['intersemestral']} ({semester_plan.get('intersemestral_credits',0)} créditos)")

            # Mostrar nota sobre media matrícula (sin mostrar montos)
            if semester_plan.get("is_half_time"):
                st.write("**Recomendación**: Media matrícula (opción activada).")

    # Mostrar costo total solo si no ocultamos valores financieros
    if not HIDE_FINANCIALS:
        st.write(f"**Costo total estimado**: ${st.session_state.total_cost:,.0f}")
else:
    st.info("No hay plan generado todavía. Seleccione asignaturas aprobadas y pulse 'Generar plan de estudios'.")

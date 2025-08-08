# curriculum.py
# Lógica para construir el grafo y generar recomendaciones
# Versión con MILP (PuLP) para generar plan óptimo (minimizar makespan)
# y con fallback heurístico si PuLP no está disponible.

import networkx as nx
import streamlit as st
import gc
import math
from typing import Iterable, List, Tuple, Dict, Any
import re
import os
import shutil
import subprocess
import stat

from courses_data import (
    fisioterapia_courses,
    enfermeria_courses,
    credits_per_semester_fisioterapia,
    credits_per_semester_enfermeria,
    calculate_semester_fisioterapia,
    calculate_semester_enfermeria,
)

# Intentamos importar pulp; si no está, lo capturamos y usaremos fallback
try:
    import pulp
    PULP_AVAILABLE = True
except Exception:
    PULP_AVAILABLE = False

@st.cache_resource
def build_curriculum_graph(_courses: Dict[str, Dict[str, Any]]) -> nx.DiGraph:
    """
    Construye un grafo dirigido con nodos = materias y aristas = prerequisitos/corequisitos.
    """
    G = nx.DiGraph()
    for course, info in _courses.items():
        credits = info.get("credits", 0)
        semester = info.get("semester", 0)
        G.add_node(course, credits=credits, semester=semester)
        for prereq in info.get("prerequisites", []):
            # prereq -> course
            G.add_edge(prereq, course, type="prerequisite")
        for coreq in info.get("corerequisites", []):
            # coreq -> course, marcado como corequisite
            G.add_edge(coreq, course, type="corequisite")
    return G


def _normalize_approved(approved_subjects: Iterable[str]) -> Tuple[str, ...]:
    """Convierte a tupla inmutable para evitar problemas con caché y comparar más fácil."""
    if approved_subjects is None:
        return tuple()
    if isinstance(approved_subjects, tuple):
        return approved_subjects
    return tuple(approved_subjects)


def get_available_subjects(_G: nx.DiGraph, approved_subjects: Tuple[str, ...], current_semester: int) -> List[str]:
    """
    Devuelve la lista de asignaturas disponibles (cumplen prereqs y coreqs) hasta el semestre current_semester+1.
    Nota: NO usa caching directo aquí para evitar problemas con objetos no-hashables.
    """
    approved = set(approved_subjects)
    available: List[str] = []

    # Identificadores "mandatorios"/prioritarios basados en nombres
    def is_mandatory_name(name: str) -> bool:
        return ("Inglés" in name) or ("Core Currículum" in name) or ("Core Curriculum" in name)

    # Recorremos nodos una sola vez, resolviendo prereqs y coreqs de forma eficiente
    for course in _G.nodes:
        if course in approved:
            continue

        # obtener predecesores y distinguir coreq/prereq
        preds = list(_G.predecessors(course))
        prereqs = [p for p in preds if _G[p][course].get("type") != "corequisite"]
        coreqs = [p for p in preds if _G[p][course].get("type") == "corequisite"]

        # revisar prereqs
        ok_prereqs = True
        for pr in prereqs:
            if pr not in approved:
                ok_prereqs = False
                break
        if not ok_prereqs:
            continue

        # revisar coreqs: permitimos si ya están aprobados o están en available (tomándose en el mismo semestre)
        ok_coreqs = True
        for cr in coreqs:
            if (cr not in approved) and (cr not in available):
                ok_coreqs = False
                break
        if not ok_coreqs:
            continue

        # filtro por semestre (permitimos hasta current_semester + 1)
        course_sem = _G.nodes[course].get("semester", 99)
        if is_mandatory_name(course) and course_sem <= current_semester:
            available.insert(0, course)
        elif course_sem <= current_semester + 1:
            available.append(course)

    return available


def get_intersemestral_options(_G: nx.DiGraph, approved_subjects: Tuple[str, ...]) -> List[str]:
    """
    Devuelve una lista de materias susceptibles de ser cursadas en intersemestral
    (por ahora: materias tipo Inglés y Precálculo) si se cumplen prerequisitos.
    """
    approved = set(approved_subjects)
    intersemestral = []
    for course in _G.nodes:
        # condiciones: nombre tipo Inglés o Precálculo
        name_ok = course.startswith("Inglés") or course == "Precálculo" or ("Inglés" in course)
        if not name_ok:
            continue
        if course in approved:
            continue
        preds = list(_G.predecessors(course))
        if all(pr in approved for pr in preds):
            intersemestral.append(course)
    return intersemestral


def recommend_subjects(
    G: nx.DiGraph,
    approved_subjects: Iterable[str],
    current_semester: int,
    credits_per_semester: Dict[int, int],
    is_half_time: bool = False,
    intersemestral: str = None,
    available_subjects: List[str] = None,
) -> Tuple[List[str], int, int, int]:
    """
    Heurística greedy local (mantuvimos para fallback y para uso modular).
    Devuelve (selected_subjects, total_credits, intersemestral_credits, semester_cost)
    """
    approved_tuple = _normalize_approved(approved_subjects)
    if available_subjects is None:
        available_subjects = get_available_subjects(G, approved_tuple, current_semester)

    effective_semester = min(current_semester, 10)
    credit_limit = credits_per_semester.get(effective_semester, 0)
    if is_half_time:
        credit_limit = max(0, credit_limit // 2 - 1)

    # Priorizar "mandatorias" (Inglés / Core Currículum) y luego por créditos desc + semestre asc
    mandatory = [s for s in available_subjects if ("Inglés" in s) or ("Core Currículum" in s) or ("Core Curriculum" in s)]
    optional = [s for s in available_subjects if s not in mandatory]
    optional.sort(key=lambda s: (-G.nodes[s].get("credits", 0), G.nodes[s].get("semester", 99)))

    selected_subjects = []
    total_credits = 0
    # añadir mandatorias primero si caben
    for s in mandatory:
        c = G.nodes[s].get("credits", 0)
        if total_credits + c <= credit_limit:
            selected_subjects.append(s)
            total_credits += c

    # luego opcionales
    for s in optional:
        c = G.nodes[s].get("credits", 0)
        if total_credits + c <= credit_limit:
            selected_subjects.append(s)
            total_credits += c

    # intersemestral (si el usuario lo seleccionó)
    intersemestral_credits = 0
    if intersemestral:
        if intersemestral not in selected_subjects and intersemestral in G.nodes:
            selected_subjects.append(intersemestral)
            intersemestral_credits = G.nodes[intersemestral].get("credits", 0)

    # coste por semestre
    semester_cost = 5000000 if is_half_time else 10000000
    if intersemestral:
        semester_cost += 1500000

    return selected_subjects, total_credits, intersemestral_credits, semester_cost


def estimate_remaining_semesters(
    G: nx.DiGraph,
    approved_subjects: Iterable[str],
    total_credits_required: int,
    credits_per_semester: Dict[int, int],
    is_half_time: bool = False,
) -> int:
    """
    Estima cuántos semestres faltan bajo un promedio de créditos por semestre.
    """
    approved_sum = sum(G.nodes[c]["credits"] for c in approved_subjects if c in G.nodes)
    remaining_credits = max(0, total_credits_required - approved_sum)
    avg_credits_per_sem = sum(credits_per_semester.get(s, 0) for s in range(1, 11)) / 10.0
    if is_half_time:
        avg_credits_per_sem = max(1.0, avg_credits_per_sem / 2.0 - 1.0)
    if avg_credits_per_sem <= 0:
        return max(1, int(remaining_credits))
    return max(1, math.ceil(remaining_credits / avg_credits_per_sem))


def _deepcopy_semester_options(semester_options: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Copia defensiva para no mutar la estructura pasada desde Streamlit (por seguridad)."""
    return {k: dict(v) for k, v in semester_options.items()}


def _build_capacity_by_semester(credits_per_semester: Dict[int, int], semester_options: Dict[int, Dict[str, Any]], semester_range: List[int]) -> Dict[int, int]:
    """
    Calcula la capacidad de créditos por semestre teniendo en cuenta semester_options.
    """
    capacities = {}
    for s in semester_range:
        base = credits_per_semester.get(min(s, 10), 0)
        opts = semester_options.get(s, {}) if semester_options else {}
        if opts.get("is_half_time"):
            cap = max(0, base // 2 - 1)
        else:
            cap = base
        extra = opts.get("extra_credits", 0) if opts else 0
        cap = max(0, cap + int(extra))
        capacities[s] = cap
    return capacities

def _sanitize_name(name: str, maxlen: int = 40) -> str:
    """
    Convierte un nombre arbitrario en un identificador seguro para usar en nombres
    de variables de PuLP: elimina caracteres no alfanuméricos (los sustituye por '_'),
    colapsa guiones bajos repetidos, evita que empiece por dígito y acorta a maxlen.
    """
    if name is None:
        return "course"
    # Reemplaza cualquier secuencia de caracteres no alfanuméricos por un guion bajo
    s = re.sub(r'[^0-9A-Za-z]+', '_', name)
    # Colapsa varios '_' consecutivos y quita '_' al inicio/fin
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        s = "course"
    # Si empieza con dígito, anteponer prefijo
    if s[0].isdigit():
        s = "c_" + s
    # Limitar longitud para evitar nombres excesivamente largos
    return s[:maxlen]

def _find_working_solver(time_limit_seconds: int = 30):
    """
    Intentar localizar un solver usable:
     1. Probar binario incluido en pulp.
     2. Probar 'cbc' en PATH.
     3. Probar GLPK en PATH.
    Devuelve un (solver_name, solver_obj) o (None, None) si no hay solver apto.
    """
    # 1) binario incluido por pulp (ruta que viste en el error)
    try:
        import pulp
        bundled = os.path.join(os.path.dirname(pulp.__file__), "solverdir", "cbc", "linux", "i64", "cbc")
        if os.path.exists(bundled) and os.access(bundled, os.X_OK):
            return "cbc_bundled", pulp.PULP_CBC_CMD(path=bundled, msg=False, timeLimit=time_limit_seconds)
        # si existe pero no es ejecutable, intentar poner ejecutable (si se puede)
        if os.path.exists(bundled) and not os.access(bundled, os.X_OK):
            try:
                os.chmod(bundled, os.stat(bundled).st_mode | stat.S_IXUSR)
                if os.access(bundled, os.X_OK):
                    return "cbc_bundled", pulp.PULP_CBC_CMD(path=bundled, msg=False, timeLimit=time_limit_seconds)
            except Exception:
                pass
    except Exception:
        pass

    # 2) cbc en PATH
    cbc_path = shutil.which("cbc")
    if cbc_path:
        try:
            return "cbc_path", pulp.PULP_CBC_CMD(path=cbc_path, msg=False, timeLimit=time_limit_seconds)
        except Exception:
            pass

    # 3) GLPK en PATH
    glpk_path = shutil.which("glpsol")
    if glpk_path:
        try:
            return "glpk", pulp.GLPK_CMD(path=glpk_path, msg=False, options=[f'--tmlim={time_limit_seconds}'])
        except Exception:
            pass

    return None, None

def _milp_generate_plan(
    G: nx.DiGraph,
    approved_subjects: Iterable[str],
    current_semester: int,
    program: str,
    credits_per_semester: Dict[int, int],
    semester_options: Dict[int, Dict[str, Any]],
    time_limit_seconds: int = 30,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Genera plan usando MILP (PuLP). Minimiza el semestre máximo usado (makespan).
    Devuelve (plan, total_cost).
    """
    if not PULP_AVAILABLE:
        raise RuntimeError("PuLP no disponible en este entorno.")

    approved = set(approved_subjects or [])
    remaining_courses = [c for c in G.nodes if c not in approved]

    # Si no quedan materias (o aprobó suficientes créditos), salir rápido
    approved_credits = sum(G.nodes[c]["credits"] for c in approved if c in G.nodes)
    total_required = 180 if program == "Fisioterapia" else 189
    if approved_credits >= total_required:
        return [], 0

    # Semestres posibles: desde current_semester hasta 10 (permitimos 10)
    semesters = list(range(current_semester, 11))
    if len(semesters) == 0:
        semesters = [current_semester]

    # Capacidades por semestre (considerando semester_options)
    capacities = _build_capacity_by_semester(credits_per_semester, semester_options or {}, semesters)

    # Crear problema
    prob = pulp.LpProblem("PlanCurricular", pulp.LpMinimize)

    # Variables x[c,s] = 1 si se toma curso c en semestre s
    x = {}
    for c in remaining_courses:
        c_sem = G.nodes[c].get("semester", 1)
        for s in semesters:
            # restringimos: no agendar antes del semestre nominal del curso
            if s < c_sem:
                continue
            x[(c, s)] = pulp.LpVariable(f"x_{_sanitize_name(c)}_{s}", cat="Binary")

    # z_s = 1 si hay al menos una materia tomada en semestre s
    z = {s: pulp.LpVariable(f"z_{s}", cat="Binary") for s in semesters}

    # M = makespan (entero), límite superior 10
    M = pulp.LpVariable("M", lowBound=0, upBound=10, cat="Integer")

    # Restricción: si se toma una materia, z_s =1
    for (c, s), var in x.items():
        prob += var <= z[s]

    # Relacionar M con z: M >= s * z_s para cada s
    for s in semesters:
        prob += M >= s * z[s]

    # Capacidad por semestre (créditos)
    for s in semesters:
        lhs = pulp.lpSum(G.nodes[c]["credits"] * x[(c, s)]
                         for c in remaining_courses if (c, s) in x)
        prob += lhs <= capacities.get(s, 0)

    # Cada curso puede tomarse a lo sumo una vez
    for c in remaining_courses:
        vars_for_c = [x[(c, s)] for s in semesters if (c, s) in x]
        if vars_for_c:
            prob += pulp.lpSum(vars_for_c) <= 1

    # Restricción de prerrequisitos: si tomas c en s, sus prereqs deben estar aprobados previamente o tomados en semestre < s
    for c in remaining_courses:
        prereqs = [p for p in G.predecessors(c) if G[p][c].get("type") != "corequisite"]
        if not prereqs:
            continue
        for s in semesters:
            if (c, s) not in x:
                continue
            # sum over prereq taken in t <= s-1 OR prereq already approved
            rhs_terms = []
            for p in prereqs:
                if p in approved:
                    # If prereq already approved, it's satisfied; we can effectively add 1
                    rhs_terms.append(1)
                else:
                    # sum of x[p,t] for t <= s-1
                    prs = [x[(p, t)] for t in semesters if (p, t) in x and t <= s - 1]
                    if prs:
                        rhs_terms.append(pulp.lpSum(prs))
                    else:
                        # prereq cannot be satisfied before s (because p can't be scheduled earlier) so force infeasible -> set rhs 0
                        rhs_terms.append(0)
            # Build RHS as sum of the terms (if any prereq satisfied gives >= number_of_prereqs)
            # We ensure: x[c,s] <= min_over_prereqs( satisfied ) but linearize as:
            # For every prereq pr: x[c,s] <= (1 if pr in approved) + sum_{t<=s-1} x[pr,t]
            for p in prereqs:
                if p in approved:
                    prob += x[(c, s)] <= 1
                else:
                    sum_pr = pulp.lpSum(x[(p, t)] for t in semesters if (p, t) in x and t <= s - 1)
                    # If sum_pr is empty (prereq cannot be scheduled earlier), this constraint will force x[c,s] <= 0
                    prob += x[(c, s)] <= sum_pr

    # Restricción de corequisitos: si c se toma en s, coreq debe estar aprobado o tomado en t <= s (mismo semestre o antes)
    for c in remaining_courses:
        coreqs = [p for p in G.predecessors(c) if G[p][c].get("type") == "corequisite"]
        if not coreqs:
            continue
        for s in semesters:
            if (c, s) not in x:
                continue
            for p in coreqs:
                if p in approved:
                    prob += x[(c, s)] <= 1
                else:
                    sum_core = pulp.lpSum(x[(p, t)] for t in semesters if (p, t) in x and t <= s)
                    prob += x[(c, s)] <= sum_core

    # Requerimiento global: alcanzar créditos totales (incluyendo aprobados)
    lhs_total = approved_credits + pulp.lpSum(G.nodes[c]["credits"] * x[(c, s)]
                                              for (c, s) in x)
    prob += lhs_total >= total_required

    # Objetivo: minimizar M (makespan), y como tie-breaker minimizar suma(s * x[c,s])
    tie_breaker = pulp.lpSum(s * x[(c, s)] for (c, s) in x)
    prob += M * 10000 + tie_breaker  # peso grande a M para priorizar minimización del semestre máximo

    # Resolver con límite de tiempo
    solver_name, solver_obj = _find_working_solver(time_limit_seconds)
    if solver_obj is None:
        raise RuntimeError("No se encontró un solver externo funcional (CBC/GLPK). Comprueba instalación de coinor-cbc o glpk.")
    # opcional: si quieres mostrar qué solver se usó
    # st.info(f"Usando solver: {solver_name}")

    result = prob.solve(solver_obj)

    if pulp.LpStatus[result] not in ("Optimal", "Not Solved", "Feasible", "Optimal (within gap)"):
        # Si no encontró solución factible, lanzar excepción para fallback
        raise RuntimeError(f"Solver status: {pulp.LpStatus[result]}")

    # Extraer solución: por semestre, listar materias
    plan = []
    semester_counts = {}
    total_cost = 0
    # Para cada semestre s en orden ascendente, recoger las materias donde x=1
    for s in semesters:
        subjects = [c for c in remaining_courses if (c, s) in x and pulp.value(x[(c, s)]) >= 0.5]
        if not subjects:
            continue
        credits_s = sum(G.nodes[c]["credits"] for c in subjects)
        # determinar costos según semester_options (si aplica)
        opts = semester_options.get(s, {}) if semester_options else {}
        is_half_time = opts.get("is_half_time", False)
        inter = opts.get("intersemestral", None)
        inter_credits = G.nodes[inter]["credits"] if inter in G.nodes else 0 if inter else 0
        sem_cost = 5000000 if is_half_time else 10000000
        if inter:
            sem_cost += 1500000

        semester_counts[s] = semester_counts.get(s, 0) + 1
        plan.append({
            "semester": s,
            "repetition": semester_counts[s],
            "subjects": subjects,
            "credits": credits_s,
            "intersemestral_credits": inter_credits,
            "is_half_time": is_half_time,
            "extra_credits": opts.get("extra_credits", 0),
            "intersemestral": inter,
            "cost": sem_cost,
        })
        total_cost += sem_cost

    return plan, total_cost


def generate_full_plan(
    _G: nx.DiGraph,
    approved_subjects: Iterable[str],
    program: str,
    _credits_per_semester: Dict[int, int],
    _calculate_semester,
    semester_options: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Genera el plan completo:
    - Intentará resolver el MILP (rápido y óptimo para makespan) si PuLP está disponible.
    - Si PuLP no está disponible o el MILP falla, cae a una heurística greedy iterativa (fallback).
    """
    approved = list(approved_subjects) if approved_subjects is not None else []
    total_credits_approved = sum(_G.nodes[c]["credits"] for c in approved if c in _G.nodes)
    current_semester = _calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189

    # Si ya cumplió, devolver vacío
    if total_credits_approved >= total_credits_required:
        return [], 0

    # Intentar MILP
    if PULP_AVAILABLE:
        try:
            plan, total_cost = _milp_generate_plan(
                _G,
                approved,
                current_semester,
                program,
                _credits_per_semester,
                semester_options or {},
                time_limit_seconds=30,  # límite de tiempo para el solver
            )
            # Si MILP produjo un plan útil (no vacío), devolver
            if plan:
                return plan, total_cost
            # Si plan vacío (p. ej. porque solver puso todo en approved), seguir a fallback
        except Exception as e:
            # No queremos que el fallo del solver rompa la app; caeremos al método heurístico.
            st.warning(f"Advertencia: MILP no pudo producir una solución óptima (fallback heurístico). Detalle: {e}")

    # --- Fallback heurístico (iterativo) ---
    # Copia del algoritmo anterior, pero asegurando no quedarnos en bucle infinito
    semester_options_local = _deepcopy_semester_options(semester_options or {})
    plan = []
    approved_local = list(approved)
    total_credits_local = total_credits_approved
    current_sem = current_semester
    total_cost = 0
    semester_counts = {}
    max_iterations = 30  # tope de seguridad

    while total_credits_local < total_credits_required and max_iterations > 0:
        max_iterations -= 1
        available_subjects = get_available_subjects(_G, tuple(approved_local), current_sem)
        intersemestral_options = get_intersemestral_options(_G, tuple(approved_local))
        best_intersemestral = None
        if intersemestral_options:
            best_intersemestral = max(intersemestral_options, key=lambda s: _G.nodes[s]["credits"] / 1500000, default=None)

        best_cost = float("inf")
        best_config = None
        for is_half_time in [False, True]:
            inter = best_intersemestral if is_half_time and best_intersemestral else None
            subjects, credits, inter_credits, semester_cost = recommend_subjects(
                _G, approved_local, current_sem, _credits_per_semester, is_half_time, inter, available_subjects
            )
            temp_approved = approved_local + subjects
            if inter:
                temp_approved.append(inter)
            remaining_semesters = estimate_remaining_semesters(_G, temp_approved, total_credits_required, _credits_per_semester, is_half_time)
            projected_cost = semester_cost + remaining_semesters * (5000000 if is_half_time else 10000000)
            if projected_cost < best_cost:
                best_cost = projected_cost
                best_config = {
                    "subjects": subjects,
                    "credits": credits,
                    "intersemestral_credits": inter_credits,
                    "semester_cost": semester_cost,
                    "is_half_time": is_half_time,
                    "extra_credits": 0,
                    "intersemestral": inter
                }

        if not best_config or (not best_config["subjects"] and not best_config["intersemestral"]):
            # Si no se logró seleccionar materias (callejón), salimos para evitar bucle.
            break

        semester_counts[current_sem] = semester_counts.get(current_sem, 0) + 1
        plan.append({
            "semester": current_sem,
            "repetition": semester_counts[current_sem],
            "subjects": best_config["subjects"],
            "credits": best_config["credits"],
            "intersemestral_credits": best_config["intersemestral_credits"],
            "is_half_time": best_config["is_half_time"],
            "extra_credits": best_config["extra_credits"],
            "intersemestral": best_config["intersemestral"],
            "cost": best_config["semester_cost"]
        })
        approved_local.extend(best_config["subjects"])
        total_credits_local += best_config["credits"] + best_config["intersemestral_credits"]
        if best_config["intersemestral"]:
            approved_local.append(best_config["intersemestral"])
        total_cost += best_config["semester_cost"]
        current_sem = _calculate_semester(total_credits_local)

        gc.collect()

    return plan, total_cost

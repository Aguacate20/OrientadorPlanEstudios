# curriculum.py
# Lógica para construir el grafo y generar recomendaciones
# Versión optimizada: eliminados cacheos problemáticos y reducidas recomputaciones.

import networkx as nx
import streamlit as st
import gc
import math
from typing import Iterable, List, Tuple, Dict, Any

from courses_data import (
    fisioterapia_courses,
    enfermeria_courses,
    credits_per_semester_fisioterapia,
    credits_per_semester_enfermeria,
    calculate_semester_fisioterapia,
    calculate_semester_enfermeria,
)


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
    Recomienda materias para un semestre dado:
    - Devuelve (selected_subjects, total_credits, intersemestral_credits, semester_cost)
    Se puede pasar available_subjects para evitar recomputarlo.
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


def generate_full_plan(
    _G: nx.DiGraph,
    approved_subjects: Iterable[str],
    program: str,
    _credits_per_semester: Dict[int, int],
    _calculate_semester,
    semester_options: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Genera el plan completo (iterativo) hasta completar los créditos requeridos.
    Optimizado evitando recomputaciones innecesarias.
    """
    approved = list(approved_subjects) if approved_subjects is not None else []
    semester_options_local = _deepcopy_semester_options(semester_options or {})

    plan = []
    total_credits_approved = sum(_G.nodes[c]["credits"] for c in approved if c in _G.nodes)
    current_semester = _calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189
    total_cost = 0
    semester_counts = {}

    # guard clause: si ya cumplió
    if total_credits_approved >= total_credits_required:
        return plan, total_cost

    # ciclo principal: añadir semestres hasta completar
    while total_credits_approved < total_credits_required:
        best_cost = float("inf")
        best_config = None

        # calcular available_subjects una sola vez por semestre
        available_subjects = get_available_subjects(_G, tuple(approved), current_semester)

        intersemestral_options = get_intersemestral_options(_G, tuple(approved))
        best_intersemestral = None
        if intersemestral_options:
            best_intersemestral = max(intersemestral_options, key=lambda s: _G.nodes[s].get("credits", 0) / 1500000.0)

        # probar configuraciones media matrícula si la opción existe
        for is_half_time in [False, True]:
            intersemestral_candidate = best_intersemestral if best_intersemestral else None

            subjects, credits, intersemestral_credits, semester_cost = recommend_subjects(
                _G, tuple(approved), current_semester, _credits_per_semester, is_half_time, intersemestral_candidate, available_subjects
            )

            # material temporal de aprobadas si tomara esas materias
            temp_approved = approved + list(subjects)
            if intersemestral_candidate:
                temp_approved.append(intersemestral_candidate)

            remaining_semesters = estimate_remaining_semesters(
                _G, temp_approved, total_credits_required, _credits_per_semester, is_half_time
            )
            projected_cost = semester_cost + remaining_semesters * (5000000 if is_half_time else 10000000)

            if projected_cost < best_cost:
                best_cost = projected_cost
                best_config = {
                    "subjects": subjects,
                    "credits": credits,
                    "intersemestral_credits": intersemestral_credits,
                    "semester_cost": semester_cost,
                    "is_half_time": is_half_time,
                    "extra_credits": 0,
                    "intersemestral": intersemestral_candidate,
                }

        # registrar repetición de semestre
        semester_counts[current_semester] = semester_counts.get(current_semester, 0) + 1

        plan.append(
            {
                "semester": current_semester,
                "repetition": semester_counts[current_semester],
                "subjects": best_config["subjects"],
                "credits": best_config["credits"],
                "intersemestral_credits": best_config["intersemestral_credits"],
                "is_half_time": best_config["is_half_time"],
                "extra_credits": best_config["extra_credits"],
                "intersemestral": best_config["intersemestral"],
                "cost": best_config["semester_cost"],
            }
        )

        # actualizar aprobadas y totales
        approved.extend(best_config["subjects"])
        total_credits_approved += best_config["credits"] + best_config["intersemestral_credits"]
        total_cost += best_config["semester_cost"]
        if best_config["intersemestral"]:
            approved.append(best_config["intersemestral"])

        # actualizar semestre actual
        current_semester = _calculate_semester(total_credits_approved)

        # si hay opciones por semestre pasadas desde UI, actualizar localmente (no mutar la original)
        if current_semester in semester_options_local:
            semester_options_local[current_semester]["is_half_time"] = best_config["is_half_time"]
            semester_options_local[current_semester]["extra_credits"] = best_config["extra_credits"]
            semester_options_local[current_semester]["intersemestral"] = best_config["intersemestral"]

        gc.collect()

    return plan, total_cost

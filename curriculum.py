# curriculum.py
# Versión que sustituye el MILP por una heurística Greedy con lookahead (1-2 semestres).
# El objetivo principal es optimizar el *tiempo* (minimizar semestres restantes) en milisegundos,
# sin dependencias externas (sin PuLP ni solver externo).

import networkx as nx
import streamlit as st
import gc
import math
import re
from typing import Iterable, List, Tuple, Dict, Any, Set

# --------------------------------------------------
# Construcción del grafo y utilidades básicas
# --------------------------------------------------

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


# reutilizamos las funciones de disponibilidad ya probadas
def get_available_subjects(_G: nx.DiGraph, approved_subjects: Tuple[str, ...], current_semester: int) -> List[str]:
    """
    Devuelve la lista de asignaturas disponibles (cumplen prereqs y coreqs) hasta el semestre current_semester+1.
    """
    approved = set(approved_subjects)
    available: List[str] = []

    def is_mandatory_name(name: str) -> bool:
        return ("Inglés" in name) or ("Core Currículum" in name) or ("Core Curriculum" in name)

    for course in _G.nodes:
        if course in approved:
            continue

        preds = list(_G.predecessors(course))
        prereqs = [p for p in preds if _G[p][course].get("type") != "corequisite"]
        coreqs = [p for p in preds if _G[p][course].get("type") == "corequisite"]

        # prereqs
        ok_prereqs = True
        for pr in prereqs:
            if pr not in approved:
                ok_prereqs = False
                break
        if not ok_prereqs:
            continue

        # coreqs: permitimos si ya están aprobados o están en available (tomándose en el mismo semestre)
        ok_coreqs = True
        for cr in coreqs:
            if (cr not in approved) and (cr not in available):
                ok_coreqs = False
                break
        if not ok_coreqs:
            continue

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
        name_ok = course.startswith("Inglés") or course == "Precálculo" or ("Inglés" in course)
        if not name_ok:
            continue
        if course in approved:
            continue
        preds = list(_G.predecessors(course))
        if all(pr in approved for pr in preds):
            intersemestral.append(course)
    return intersemestral


# --------------------------------------------------
# Helpers para la estrategia greedy con lookahead
# --------------------------------------------------


def _build_capacity_by_semester(credits_per_semester: Dict[int, int], semester_options: Dict[int, Dict[str, Any]], semester_range: List[int]) -> Dict[int, int]:
    """
    Calcula la capacidad de créditos por semestre teniendo en cuenta semester_options.
    Igual que la versión anterior pero simplificada para la heurística.
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


def _estimate_remaining_semesters_simulation(
    G: nx.DiGraph,
    approved_subjects: Iterable[str],
    total_credits_required: int,
    credits_per_semester: Dict[int, int],
    semester_options: Dict[int, Dict[str, Any]],
    start_semester: int,
    max_semester: int = 20,
) -> int:
    """
    Estima cuántos semestres hacen falta simulando la capacidad por semestre
    (más precisa que dividir por promedio).
    """
    approved_sum = sum(G.nodes[c]["credits"] for c in approved_subjects if c in G.nodes)
    remaining = max(0, total_credits_required - approved_sum)
    if remaining == 0:
        return 0

    sem = start_semester
    sems = 0
    while remaining > 0 and sem <= max_semester:
        base = credits_per_semester.get(min(sem, 10), 0)
        opts = semester_options.get(sem, {}) if semester_options else {}
        if opts.get("is_half_time"):
            cap = max(0, base // 2 - 1)
        else:
            cap = base
        cap += int(opts.get("extra_credits", 0)) if opts else 0
        cap = max(0, cap)
        # si no hay capacidad real, evitamos bucle infinito
        if cap <= 0:
            sem += 1
            sems += 1
            continue
        remaining -= cap
        sem += 1
        sems += 1
    return sems if remaining <= 0 else sems + math.ceil(remaining / max(1, credits_per_semester.get(10, base)))


def _collect_coreqs_to_take(G: nx.DiGraph, course: str, approved_set: Set[str], available_this_sem: Set[str]) -> Set[str]:
    """
    Devuelve el conjunto de corequisitos (directos) que deberían tomarse junto con `course` en el mismo semestre,
    siempre que estén listados en available_this_sem. No seguimos coreqs recursivos profundos (simplificación razonable).
    """
    coreqs = set()
    preds = list(G.predecessors(course))
    for p in preds:
        if G[p][course].get("type") == "corequisite":
            if p not in approved_set and p in available_this_sem:
                coreqs.add(p)
    return coreqs


def greedy_select_with_lookahead(
    G: nx.DiGraph,
    approved: List[str],
    available_subjects: List[str],
    current_sem: int,
    credits_limit: int,
    lookahead: int = 2,
) -> Tuple[List[str], int]:
    """
    Selección greedy para un semestre con lookahead=1 o 2.
    Prioriza materias cuya inclusión "desbloquea" más asignaturas en los próximos semestres.

    Algoritmo (resumen):
      - iterativamente selecciona la materia con mejor ratio (beneficio incremental / créditos) hasta llenar el cupo.
      - beneficio calculado simulando 1 o 2 semestres hacia adelante: cuántas materias adicionales estarían disponibles.
    """
    approved_set = set(approved)
    available_set = list(available_subjects)  # copia

    selected: List[str] = []
    total_credits = 0

    # Precomputar baseline para lookahead: sin tomar nada ahora, qué estará disponible en sem+1 y sem+2
    baseline_next = set(get_available_subjects(G, tuple(approved_set), current_sem + 1))
    baseline_next2 = set(get_available_subjects(G, tuple(approved_set.union(baseline_next)), current_sem + 2)) if lookahead >= 2 else set()

    # Mientras haya capacidad y materias candidatas
    iterations_guard = 0
    while total_credits < credits_limit and iterations_guard < 500:
        iterations_guard += 1
        candidates = [c for c in available_set if c not in selected]
        if not candidates:
            break

        best_score = -1.0
        best_choice = None
        best_choice_full_set: Set[str] = set()
        best_choice_credits = 0

        for cand in candidates:
            # calcular qué coreqs habría que tomar también
            coreqs = _collect_coreqs_to_take(G, cand, approved_set.union(selected), set(available_set))
            need_set = {cand} | coreqs
            need_credits = sum(G.nodes[n].get("credits", 0) for n in need_set)
            # si no cabe en lo que queda, saltar
            if total_credits + need_credits > credits_limit:
                continue

            # simular aprobación temporal
            temp_approved = set(approved_set) | set(selected) | need_set

            # disponibilidad en sem+1 y sem+2
            next_avail = set(get_available_subjects(G, tuple(temp_approved), current_sem + 1))
            next2_avail = set(get_available_subjects(G, tuple(temp_approved.union(next_avail)), current_sem + 2)) if lookahead >= 2 else set()

            # beneficio incremental respecto al baseline
            inc1 = len(next_avail - baseline_next)
            inc2 = len(next2_avail - baseline_next2) if lookahead >= 2 else 0
            # ponderación: damos más peso al primer semestre (desbloqueo inmediato)
            benefit = inc1 * 2 + inc2

            # score por unidad de crédito (evitar seleccionar materias grandes sin beneficio)
            score = (benefit / max(1, need_credits))

            # desempate: mayor cantidad de beneficio absoluto
            if score > best_score or (abs(score - best_score) < 1e-9 and benefit > 0 and best_choice is not None and need_credits > best_choice_credits):
                best_score = score
                best_choice = cand
                best_choice_full_set = need_set
                best_choice_credits = need_credits

        # Si no encontramos un candidato con beneficio (score <= 0), entonces rellenamos por créditos: materias más grandes primero
        if best_choice is None or best_score <= 0:
            # intentar llenar por créditos (orden por créditos desc, semestre asc)
            remaining = credits_limit - total_credits
            optional = sorted([c for c in candidates if G.nodes[c].get("credits", 0) <= remaining], key=lambda s: (-G.nodes[s].get("credits", 0), G.nodes[s].get("semester", 99)))
            if not optional:
                break
            pick = optional[0]
            coreqs = _collect_coreqs_to_take(G, pick, approved_set.union(selected), set(available_set))
            pick_set = {pick} | coreqs
            pick_credits = sum(G.nodes[n].get("credits", 0) for n in pick_set)
            if total_credits + pick_credits > credits_limit:
                break
            selected.extend([x for x in pick_set if x not in selected])
            total_credits += pick_credits
            continue

        # aplicar la mejor elección encontrada
        for n in best_choice_full_set:
            if n not in selected:
                selected.append(n)
        total_credits += best_choice_credits

    return selected, total_credits


# --------------------------------------------------
# Interfaz principal: generar plan completo usando greedy lookahead
# --------------------------------------------------


def generate_full_plan(
    _G: nx.DiGraph,
    approved_subjects: Iterable[str],
    program: str,
    _credits_per_semester: Dict[int, int],
    _calculate_semester,
    semester_options: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Genera el plan completo usando la heurística greedy con lookahead.
    El criterio principal es minimizar el número de semestres restantes (tiempo).

    Devuelve (plan, total_cost).
    """
    approved = list(approved_subjects) if approved_subjects is not None else []
    total_credits_approved = sum(_G.nodes[c]["credits"] for c in approved if c in _G.nodes)
    current_semester = _calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189

    # Si ya cumplió, devolver vacío
    if total_credits_approved >= total_credits_required:
        return [], 0

    # parámetros de la heurística
    lookahead = 2
    plan = []
    approved_local = list(approved)
    total_credits_local = total_credits_approved
    current_sem = current_semester
    total_cost = 0
    semester_counts = {}
    max_iterations = 40

    # vamos iterando semestre a semestre
    while total_credits_local < total_credits_required and max_iterations > 0:
        max_iterations -= 1

        # calcular capacidad para este semestre (teniendo en cuenta opciones puntuales)
        base_capacity = _credits_per_semester.get(min(current_sem, 10), 0)
        opts = semester_options.get(current_sem, {}) if semester_options else {}
        if opts.get("is_half_time"):
            capacity = max(0, base_capacity // 2 - 1)
        else:
            capacity = base_capacity
        capacity += int(opts.get("extra_credits", 0)) if opts else 0
        capacity = max(0, capacity)

        # materias disponibles hoy
        available_subjects = get_available_subjects(_G, tuple(approved_local), current_sem)
        intersemestral_options = get_intersemestral_options(_G, tuple(approved_local))

        # Decidir si medio-tiempo o full-time: probamos ambas opciones y elegimos la que minimice semestres restantes
        best_sem_config = None
        best_remaining_semesters = float('inf')

        for is_half_time in [False, True]:
            # configurar capacidad temporal
            cap_tmp = capacity
            if is_half_time:
                cap_tmp = max(0, base_capacity // 2 - 1)
            else:
                cap_tmp = base_capacity
            cap_tmp += int(opts.get("extra_credits", 0)) if opts else 0

            # Selección greedy con lookahead
            subjects_selected, credits_selected = greedy_select_with_lookahead(
                _G, approved_local, available_subjects, current_sem, cap_tmp, lookahead=lookahead
            )

            # considerar intersemestral si aplica (añadir como opción si cabe)
            inter_choice = None
            inter_credits = 0
            if intersemestral_options:
                # elegir la de mayor crédito que quepa
                for ic in sorted(intersemestral_options, key=lambda s: -_G.nodes[s].get('credits', 0)):
                    if credits_selected + _G.nodes[ic].get('credits', 0) <= cap_tmp:
                        inter_choice = ic
                        inter_credits = _G.nodes[ic].get('credits', 0)
                        break

            # construir conjunto temporal de aprobadas y estimar semestres restantes
            temp_approved = set(approved_local) | set(subjects_selected)
            if inter_choice:
                temp_approved.add(inter_choice)

            remaining_after = _estimate_remaining_semesters_simulation(
                _G, temp_approved, total_credits_required, _credits_per_semester, semester_options, current_sem + 1
            )

            # total semestres esperados = 1 (este semestre) + remaining_after
            total_estimated = 1 + remaining_after

            # preferir menor tiempo; si empate, preferir mayor carga de créditos ahora
            if total_estimated < best_remaining_semesters or (total_estimated == best_remaining_semesters and credits_selected + inter_credits > (best_sem_config or {}).get('credits', -1)):
                best_remaining_semesters = total_estimated
                best_sem_config = {
                    'is_half_time': is_half_time,
                    'subjects': subjects_selected,
                    'credits': credits_selected,
                    'intersemestral': inter_choice,
                    'intersemestral_credits': inter_credits,
                    'capacity': cap_tmp,
                }

        # Si no encontramos config viable (calles), salimos
        if not best_sem_config or (not best_sem_config['subjects'] and not best_sem_config['intersemestral']):
            break

        # Aplicar la mejor configuración para este semestre
        semester_counts[current_sem] = semester_counts.get(current_sem, 0) + 1
        sem_cost = 5000000 if best_sem_config['is_half_time'] else 10000000
        if best_sem_config['intersemestral']:
            sem_cost += 1500000

        plan.append({
            'semester': current_sem,
            'repetition': semester_counts[current_sem],
            'subjects': best_sem_config['subjects'],
            'credits': best_sem_config['credits'],
            'intersemestral_credits': best_sem_config['intersemestral_credits'],
            'is_half_time': best_sem_config['is_half_time'],
            'extra_credits': opts.get('extra_credits', 0) if opts else 0,
            'intersemestral': best_sem_config['intersemestral'],
            'cost': sem_cost,
        })

        # actualizar aprobadas y crédito total
        approved_local.extend(best_sem_config['subjects'])
        if best_sem_config['intersemestral']:
            approved_local.append(best_sem_config['intersemestral'])
        total_credits_local += best_sem_config['credits'] + best_sem_config['intersemestral_credits']
        total_cost += sem_cost

        # avanzar semestre en función de créditos totales usando el _calculate_semester proporcionado
        current_sem = _calculate_semester(total_credits_local)

        gc.collect()

    return plan, total_cost


# Fin de archivo

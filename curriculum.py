# curriculum.py
# Versión Greedy con lookahead (1-2 semestres) — criterio actualizado:
# 1) Priorizar que en **cada semestre** se cumpla (o se aproxime lo máximo posible) la capacidad de créditos.
# 2) Si hay empate/compromiso, minimizar COSTOS (intersemestral, media matrícula, compra de créditos).
# 3) Finalmente, minimizar NÚMERO DE SEMESTRES restantes.
# No usa PuLP ni solvers externos — rápido y reproducible en Streamlit Cloud.

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
            G.add_edge(prereq, course, type="prerequisite")
        for coreq in info.get("corerequisites", []):
            G.add_edge(coreq, course, type="corequisite")
    return G


def _normalize_approved(approved_subjects: Iterable[str]) -> Tuple[str, ...]:
    if approved_subjects is None:
        return tuple()
    if isinstance(approved_subjects, tuple):
        return approved_subjects
    return tuple(approved_subjects)


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

        ok_prereqs = True
        for pr in prereqs:
            if pr not in approved:
                ok_prereqs = False
                break
        if not ok_prereqs:
            continue

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
        if cap <= 0:
            sem += 1
            sems += 1
            continue
        remaining -= cap
        sem += 1
        sems += 1
    return sems if remaining <= 0 else sems + math.ceil(remaining / max(1, credits_per_semester.get(10, base)))


def _collect_coreqs_to_take(G: nx.DiGraph, course: str, approved_set: Set[str], available_this_sem: Set[str]) -> Set[str]:
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
    favor_fill: bool = True,
) -> Tuple[List[str], int]:
    """
    Selección greedy con lookahead.
    - Si favor_fill=True, prioriza llenar la capacidad del semestre (primer criterio del usuario).
    - Luego usa desbloqueo en próximos semestres como factor secundario dentro del semestre.
    """
    approved_set = set(approved)
    available_set = list(available_subjects)

    selected: List[str] = []
    total_credits = 0

    baseline_next = set(get_available_subjects(G, tuple(approved_set), current_sem + 1))
    baseline_next2 = set(get_available_subjects(G, tuple(approved_set.union(baseline_next)), current_sem + 2)) if lookahead >= 2 else set()

    iterations_guard = 0
    while total_credits < credits_limit and iterations_guard < 500:
        iterations_guard += 1
        candidates = [c for c in available_set if c not in selected]
        if not candidates:
            break

        best_score = -float('inf')
        best_choice = None
        best_choice_full_set: Set[str] = set()
        best_choice_credits = 0

        for cand in candidates:
            coreqs = _collect_coreqs_to_take(G, cand, approved_set.union(selected), set(available_set))
            need_set = {cand} | coreqs
            need_credits = sum(G.nodes[n].get("credits", 0) for n in need_set)
            if total_credits + need_credits > credits_limit:
                continue

            temp_approved = set(approved_set) | set(selected) | need_set
            next_avail = set(get_available_subjects(G, tuple(temp_approved), current_sem + 1))
            next2_avail = set(get_available_subjects(G, tuple(temp_approved.union(next_avail)), current_sem + 2)) if lookahead >= 2 else set()

            inc1 = len(next_avail - baseline_next)
            inc2 = len(next2_avail - baseline_next2) if lookahead >= 2 else 0
            benefit = inc1 * 2 + inc2

            # Scoring: si favor_fill, priorizamos créditos (reduce gap) y luego el beneficio por desbloqueo
            if favor_fill:
                # darle más peso a necesidad de crédito: preferir elementos que aumenten total_credits
                score = (0.8 * need_credits) + (0.2 * (benefit / max(1, need_credits)))
            else:
                score = (benefit / max(1, need_credits)) + 0.02 * need_credits

            # desempate por mayor beneficio absoluto y después mayor crédito
            if score > best_score or (abs(score - best_score) < 1e-9 and (benefit > 0 and need_credits > best_choice_credits)):
                best_score = score
                best_choice = cand
                best_choice_full_set = need_set
                best_choice_credits = need_credits

        # Si no encontramos candidata, intentar llenar por créditos grandes
        if best_choice is None or best_score == -float('inf'):
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

        for n in best_choice_full_set:
            if n not in selected:
                selected.append(n)
        total_credits += best_choice_credits

    return selected, total_credits


# --------------------------------------------------
# Generar plan completo con la nueva priorización
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
    Genera el plan completo con criterio actualizado:
      1) llenar/Acercarse lo máximo posible a la capacidad de cada semestre
      2) minimizar costo proyectado
      3) minimizar semestres restantes
    """
    approved = list(approved_subjects) if approved_subjects is not None else []
    total_credits_approved = sum(_G.nodes[c]["credits"] for c in approved if c in _G.nodes)
    current_semester = _calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189

    if total_credits_approved >= total_credits_required:
        return [], 0

    lookahead = 2
    plan = []
    approved_local = list(approved)
    total_credits_local = total_credits_approved
    current_sem = current_semester
    total_cost = 0
    semester_counts = {}
    max_iterations = 40

    while total_credits_local < total_credits_required and max_iterations > 0:
        max_iterations -= 1

        base_capacity = _credits_per_semester.get(min(current_sem, 10), 0)
        opts = semester_options.get(current_sem, {}) if semester_options else {}
        if opts.get("is_half_time"):
            capacity = max(0, base_capacity // 2 - 1)
        else:
            capacity = base_capacity
        capacity += int(opts.get("extra_credits", 0)) if opts else 0
        capacity = max(0, capacity)

        available_subjects = get_available_subjects(_G, tuple(approved_local), current_sem)
        intersemestral_options = get_intersemestral_options(_G, tuple(approved_local))

        best_sem_config = None
        # Metric lexicográfica ahora: (gap_after_fill, projected_cost, estimated_semesters)
        # gap_after_fill = capacity - credits_taken (queremos minimizarlo)
        best_metric = (float('inf'), float('inf'), float('inf'))

        for is_half_time in [False, True]:
            if is_half_time:
                cap_tmp = max(0, base_capacity // 2 - 1)
            else:
                cap_tmp = base_capacity
            cap_tmp += int(opts.get("extra_credits", 0)) if opts else 0

            # En primer criterio favorecemos llenar capacidad => favor_fill=True
            subjects_selected, credits_selected = greedy_select_with_lookahead(
                _G, approved_local, available_subjects, current_sem, cap_tmp, lookahead=lookahead, favor_fill=True
            )

            inter_candidates = [None]
            if intersemestral_options:
                inter_candidates.extend(sorted(intersemestral_options, key=lambda s: -_G.nodes[s].get('credits', 0))[:2])

            for inter_choice in inter_candidates:
                inter_credits = _G.nodes[inter_choice].get('credits', 0) if inter_choice else 0
                # respetar capacidad
                if credits_selected + inter_credits > cap_tmp:
                    continue

                temp_approved = set(approved_local) | set(subjects_selected)
                if inter_choice:
                    temp_approved.add(inter_choice)

                remaining_after = _estimate_remaining_semesters_simulation(
                    _G, temp_approved, total_credits_required, _credits_per_semester, semester_options, current_sem + 1
                )

                per_sem_cost = 5000000 if is_half_time else 10000000
                current_sem_cost = per_sem_cost + (1500000 if inter_choice else 0)
                projected_total_cost = current_sem_cost + remaining_after * per_sem_cost
                total_estimated_semesters = 1 + remaining_after

                gap_after = cap_tmp - (credits_selected + inter_credits)
                # preferir gap pequeño (pero no negativo), luego menor costo, luego menos semestres
                metric = (gap_after, projected_total_cost, total_estimated_semesters)

                if metric < best_metric:
                    best_metric = metric
                    best_sem_config = {
                        'is_half_time': is_half_time,
                        'subjects': subjects_selected,
                        'credits': credits_selected,
                        'intersemestral': inter_choice,
                        'intersemestral_credits': inter_credits,
                        'capacity': cap_tmp,
                        'projected_total_cost': projected_total_cost,
                        'estimated_semesters': total_estimated_semesters,
                        'current_sem_cost': current_sem_cost,
                    }

        # Si no encontramos config viable (calles), salimos
        if not best_sem_config or (not best_sem_config['subjects'] and not best_sem_config['intersemestral']):
            break

        semester_counts[current_sem] = semester_counts.get(current_sem, 0) + 1
        sem_cost = best_sem_config['current_sem_cost']

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

        approved_local.extend(best_sem_config['subjects'])
        if best_sem_config['intersemestral']:
            approved_local.append(best_sem_config['intersemestral'])
        total_credits_local += best_sem_config['credits'] + best_sem_config['intersemestral_credits']
        total_cost += sem_cost

        current_sem = _calculate_semester(total_credits_local)

        gc.collect()

    return plan, total_cost


# Fin de archivo

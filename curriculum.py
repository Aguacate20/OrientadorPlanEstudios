# curriculum.py
# Versión Greedy con lookahead (1-2 semestres) — criterio actualizado según preferencias del usuario:
# 1) Priorizar que en cada semestre se cumpla o se aproxime lo máximo posible la capacidad de créditos.
# 2) Si hay empate/compromiso, minimizar COSTOS (media matrícula, intersemestral, compra de créditos).
# 3) Finalmente, minimizar NÚMERO DE SEMESTRES restantes.
# Reglas extras aplicadas por preferencia del usuario:
# - Priorizar materias del semestre nominal cuando estén disponibles (salvo que "desbloquear" mucho más compense).
# - Intersemestrales solo se usan si reducen el número total de semestres.
# - Evitar media matrícula si con full-time es posible llenar el semestre.
# - Penalidad por gap de créditos: $800.000 por crédito no tomado del cupo.

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
    """
    Devuelve las materias susceptibles de ser cursadas en intersemestral
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
    nominal_bonus_threshold: int = 3,
) -> Tuple[List[str], int]:
    """
    Selección greedy con lookahead.
    - favor_fill=True prioriza llenar la capacidad del semestre.
    - Se añade un pequeño bonus a materias del semestre nominal para preferir "normalidad".

    Nueva regla importante: si todas las materias nominales disponibles (las del semestre nominal) caben en la capacidad,
    las seleccionamos todas inmediatamente (prioridad por normalidad). Esto evita reordenamientos raros cuando el usuario
    ya aprobó el semestre anterior y quiere ver el plan nominal.
    """
    approved_set = set(approved)
    available_set = list(available_subjects)

    # --- Nueva verificación rápida: si las materias nominales disponibles caben todas, retornarlas ---
    nominal_available = [c for c in available_set if G.nodes[c].get("semester") == current_sem]
    if nominal_available:
        # incluir coreqs necesarios para nominales si están disponibles
        nominal_full_set = set()
        for c in nominal_available:
            coreqs = _collect_coreqs_to_take(G, c, approved_set, set(available_set))
            nominal_full_set.add(c)
            nominal_full_set.update(coreqs)
        nominal_total_credits = sum(G.nodes[n].get("credits", 0) for n in nominal_full_set)
        if nominal_total_credits <= credits_limit:
            # devolver todas las nominales (y sus coreqs) — prioridad explícita por "normalidad"
            return list(nominal_full_set), nominal_total_credits

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

            # Nominal bonus: favorecemos materias que correspondan al semestre nominal
            sem_nominal = G.nodes[cand].get("semester", None)
            nominal_bonus = 0.0
            if sem_nominal == current_sem:
                nominal_bonus = 0.25 * need_credits  # peso razonable para preferir normalidad

            if favor_fill:
                # Score: priorizar créditos (llenar) y luego desbloqueo, y aplicar bonus nominal
                score = (0.75 * need_credits) + (0.25 * (benefit / max(1, need_credits))) + nominal_bonus
            else:
                score = (benefit / max(1, need_credits)) + 0.02 * need_credits + nominal_bonus

            if score > best_score or (abs(score - best_score) < 1e-9 and (benefit > 0 and need_credits > best_choice_credits)):
                best_score = score
                best_choice = cand
                best_choice_full_set = need_set
                best_choice_credits = need_credits

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
    Genera el plan completo con criterio:
      1) llenar/Acercarse lo máximo posible a la capacidad de cada semestre
      2) minimizar costo proyectado
      3) minimizar semestres restantes

    Reglas específicas implementadas según tus respuestas:
    - Priorizar materias nominales (bonus moderado) salvo que desbloquear mucho más compense.
    - Intersemestrales solo considerados si reducen el número total de semestres.
    - Evitar media matrícula cuando full-time puede llenar el semestre.
    - Penalidad por gap: $800.000 por crédito no tomado del cupo.
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

    # parámetros económicos
    FULL_COST = 10000000
    HALF_COST = 5000000
    INTER_COST = 1500000
    GAP_PENALTY_PER_CREDIT = 800000

    while total_credits_local < total_credits_required and max_iterations > 0:
        max_iterations -= 1

        base_capacity = _credits_per_semester.get(min(current_sem, 10), 0)
        opts = semester_options.get(current_sem, {}) if semester_options else {}
        # capacity without considering extra credits user may buy (we'll consider extra_credits option via opts when applying)
        if opts.get("is_half_time"):
            capacity = max(0, base_capacity // 2 - 1)
        else:
            capacity = base_capacity
        capacity += int(opts.get("extra_credits", 0)) if opts else 0
        capacity = max(0, capacity)

        available_subjects = get_available_subjects(_G, tuple(approved_local), current_sem)
        intersemestral_options = get_intersemestral_options(_G, tuple(approved_local))

        best_sem_config = None
        # Métrica lexicográfica: (gap_after_fill, projected_cost_with_gap_penalty, estimated_semesters)
        best_metric = (float('inf'), float('inf'), float('inf'))

        # Primero evaluar full-time — si full-time llena el semestre (gap==0) lo preferimos y no consideramos medio-tiempo
        def eval_configuration(is_half_time_flag, allow_inter=True):
            if is_half_time_flag:
                cap_tmp = max(0, base_capacity // 2 - 1)
            else:
                cap_tmp = base_capacity
            cap_tmp += int(opts.get("extra_credits", 0)) if opts else 0

            subjects_selected, credits_selected = greedy_select_with_lookahead(
                _G, approved_local, available_subjects, current_sem, cap_tmp, lookahead=lookahead, favor_fill=True
            )

            temp_approved_no_inter = set(approved_local) | set(subjects_selected)
            remaining_no_inter = _estimate_remaining_semesters_simulation(
                _G, temp_approved_no_inter, total_credits_required, _credits_per_semester, semester_options, current_sem + 1
            )
            est_semesters_no_inter = 1 + remaining_no_inter

            inter_candidates = [None]
            if allow_inter and intersemestral_options:
                inter_candidates.extend(sorted(intersemestral_options, key=lambda s: -_G.nodes[s].get('credits', 0))[:2])

            results = []
            for inter_choice in inter_candidates:
                inter_credits = _G.nodes[inter_choice].get('credits', 0) if inter_choice else 0
                if credits_selected + inter_credits > cap_tmp:
                    continue

                if inter_choice:
                    temp_approved_with_inter = set(approved_local) | set(subjects_selected) | {inter_choice}
                    remaining_with_inter = _estimate_remaining_semesters_simulation(
                        _G, temp_approved_with_inter, total_credits_required, _credits_per_semester, semester_options, current_sem + 1
                    )
                    est_semesters_with_inter = 1 + remaining_with_inter
                    if est_semesters_with_inter >= est_semesters_no_inter:
                        continue
                else:
                    est_semesters_with_inter = est_semesters_no_inter

                per_sem_cost = HALF_COST if is_half_time_flag else FULL_COST
                current_sem_cost = per_sem_cost + (INTER_COST if inter_choice else 0)
                gap_after = cap_tmp - (credits_selected + inter_credits)
                if gap_after < 0:
                    gap_after = 0
                gap_penalty = gap_after * GAP_PENALTY_PER_CREDIT
                projected_total_cost = current_sem_cost + gap_penalty + remaining_no_inter * per_sem_cost

                results.append({
                    'is_half_time': is_half_time_flag,
                    'subjects': subjects_selected,
                    'credits': credits_selected,
                    'intersemestral': inter_choice,
                    'intersemestral_credits': inter_credits,
                    'capacity': cap_tmp,
                    'projected_total_cost': projected_total_cost,
                    'estimated_semesters': est_semesters_with_inter,
                    'current_sem_cost': current_sem_cost + gap_penalty,
                    'gap_after': gap_after,
                })
            return results

        # evaluar full-time primero
        full_results = eval_configuration(False, allow_inter=True)
        if full_results:
            for r in full_results:
                metric = (r['gap_after'], r['projected_total_cost'], r['estimated_semesters'])
                if metric < best_metric:
                    best_metric = metric
                    best_sem_config = r
        if best_sem_config and best_sem_config['gap_after'] == 0:
            pass
        else:
            half_results = eval_configuration(True, allow_inter=True)
            for r in half_results:
                metric = (r['gap_after'], r['projected_total_cost'], r['estimated_semesters'])
                if metric < best_metric:
                    best_metric = metric
                    best_sem_config = r

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

# curriculum.py
# Versión corregida: prioridad absoluta a materias mandatorias (Inglés / Core Currículum)
# Las demás reglas previas se mantienen: llenar semestre, minimizar costo, luego semestres.
# Se priorizan mandatorias en selección y en packing final.

import networkx as nx
import streamlit as st
import gc
import math
from typing import Iterable, List, Tuple, Dict, Any, Set

# -------------------------
# Helper: nombre mandatorio
# -------------------------
def is_mandatory_name(name: str) -> bool:
    """True si la materia es Inglés o Core Currículum (prioridad especial)."""
    return ("Inglés" in name) or ("Core Currículum" in name) or ("Core Curriculum" in name)

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
        # mandar mandatorias al frente (para darle prioridad visual y semántica)
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


def _pack_additional_courses(G: nx.DiGraph, approved_set: Set[str], selected: List[str], available_set: List[str], remaining: int, current_sem: int) -> Tuple[List[str], int]:
    """
    Intentar llenar la capacidad restante 'remaining' añadiendo materias pequeñas disponibles.
    Prioridad: mandatorias (Inglés/Core) primero, luego nominales, luego mayor crédito.
    Devuelve (selected_updated, added_credits).
    """
    if remaining <= 0:
        return selected, 0

    added = 0
    pack_candidates = []
    for c in available_set:
        if c in selected or c in approved_set:
            continue
        coreqs = _collect_coreqs_to_take(G, c, approved_set.union(selected), set(available_set))
        need_set = {c} | coreqs
        need_credits = sum(G.nodes[n].get("credits", 0) for n in need_set)
        if need_credits <= remaining:
            is_mand = 1 if is_mandatory_name(c) else 0
            is_nominal = 1 if G.nodes[c].get("semester") == current_sem else 0
            pack_candidates.append((is_mand, is_nominal, need_credits, c, need_set))
    # ordenar: mandatorias primero, luego nominales, luego mayor créditos, luego semestre asc
    pack_candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], G.nodes[x[3]].get("semester", 99)))
    for is_mand, is_nom, need_credits, c, need_set in pack_candidates:
        if need_credits <= remaining:
            for n in need_set:
                if n not in selected:
                    selected.append(n)
            remaining -= need_credits
            added += need_credits
        if remaining <= 0:
            break
    return selected, added


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
    - Las materias 'mandatorias' reciben una bonificación fuerte para que siempre sean preferidas.
    - Incluye packing interno para reducir huecos.
    """
    approved_set = set(approved)
    available_set = list(available_subjects)

    # si todas las materias nominales disponibles caben, devolverlas (prioridad por normalidad)
    nominal_available = [c for c in available_set if G.nodes[c].get("semester") == current_sem]
    if nominal_available:
        nominal_full_set = set()
        for c in nominal_available:
            coreqs = _collect_coreqs_to_take(G, c, approved_set, set(available_set))
            nominal_full_set.add(c)
            nominal_full_set.update(coreqs)
        nominal_total_credits = sum(G.nodes[n].get("credits", 0) for n in nominal_full_set)
        if nominal_total_credits <= credits_limit:
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

            # prioridad mandatoria (muy alta)
            mand_bonus = 0.5 * need_credits if is_mandatory_name(cand) else 0.0
            # nominal bonus (moderado)
            nominal_bonus = 0.25 * need_credits if G.nodes[cand].get("semester") == current_sem else 0.0

            if favor_fill:
                # Score: priorizar créditos (llenar), luego desbloqueo, y aplicar bonificaciones
                score = (0.7 * need_credits) + (0.2 * (benefit / max(1, need_credits))) + nominal_bonus + mand_bonus
            else:
                score = (benefit / max(1, need_credits)) + 0.02 * need_credits + nominal_bonus + mand_bonus

            if score > best_score or (abs(score - best_score) < 1e-9 and need_credits > best_choice_credits):
                best_score = score
                best_choice_full_set = need_set
                best_choice_credits = need_credits

        if not best_choice_full_set:
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

    # packing interno para llenar restantes
    remaining = credits_limit - total_credits
    if remaining > 0:
        selected, added = _pack_additional_courses(G, approved_set, selected, available_set, remaining, current_sem)
        total_credits += added

    return selected, total_credits


# --------------------------------------------------
# Generar plan completo con la priorización solicitada
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
      2) minimizar costo proyectado (incluye penalidad por gap)
      3) minimizar semestres restantes

    Además:
    - Intersemestrales solo considerados si reducen semestres totales.
    - Evitar media matrícula cuando full-time puede llenar.
    - Post-pack final para llenar huecos pequeños, con prioridad mandatorias.
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
        if opts.get("is_half_time"):
            capacity = max(0, base_capacity // 2 - 1)
        else:
            capacity = base_capacity
        capacity += int(opts.get("extra_credits", 0)) if opts else 0
        capacity = max(0, capacity)

        available_subjects = get_available_subjects(_G, tuple(approved_local), current_sem)
        intersemestral_options = get_intersemestral_options(_G, tuple(approved_local))

        best_sem_config = None
        best_metric = (float('inf'), float('inf'), float('inf'))  # (gap, cost, sems)

        def eval_configuration(is_half_time_flag, allow_inter=True):
            if is_half_time_flag:
                cap_tmp = max(0, base_capacity // 2 - 1)
            else:
                cap_tmp = base_capacity
            cap_tmp += int(opts.get("extra_credits", 0)) if opts else 0

            subjects_selected, credits_selected = greedy_select_with_lookahead(
                _G, approved_local, available_subjects, current_sem, cap_tmp, lookahead=lookahead, favor_fill=True
            )

            # post-pack tentativo para evaluación
            subjects_packed = list(subjects_selected)
            credits_packed = credits_selected
            remaining_tmp = cap_tmp - credits_packed
            if remaining_tmp > 0:
                subjects_packed, added = _pack_additional_courses(_G, set(approved_local), subjects_packed, available_subjects, remaining_tmp, current_sem)
                credits_packed += added

            temp_approved_no_inter = set(approved_local) | set(subjects_packed)
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
                if credits_packed + inter_credits > cap_tmp:
                    continue

                if inter_choice:
                    temp_approved_with_inter = set(approved_local) | set(subjects_packed) | {inter_choice}
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
                gap_after = cap_tmp - (credits_packed + inter_credits)
                if gap_after < 0:
                    gap_after = 0
                gap_penalty = gap_after * GAP_PENALTY_PER_CREDIT
                projected_total_cost = current_sem_cost + gap_penalty + remaining_no_inter * per_sem_cost

                results.append({
                    'is_half_time': is_half_time_flag,
                    'subjects': subjects_packed,
                    'credits': credits_packed,
                    'intersemestral': inter_choice,
                    'intersemestral_credits': inter_credits,
                    'capacity': cap_tmp,
                    'projected_total_cost': projected_total_cost,
                    'estimated_semesters': est_semesters_with_inter,
                    'current_sem_cost': current_sem_cost + gap_penalty,
                    'gap_after': gap_after,
                })
            return results

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

        # POST-PACK final: asegurar que usamos huecos pequeños y privilegiamos mandatorias
        chosen_subjects = list(best_sem_config['subjects'])
        chosen_credits = best_sem_config['credits']
        cap_chosen = best_sem_config['capacity']
        remaining_final = cap_chosen - chosen_credits
        if remaining_final > 0:
            chosen_subjects, added_final = _pack_additional_courses(_G, set(approved_local), chosen_subjects, available_subjects, remaining_final, current_sem)
            chosen_credits += added_final
            gap_after = cap_chosen - chosen_credits
            if gap_after < 0:
                gap_after = 0
            gap_penalty = gap_after * GAP_PENALTY_PER_CREDIT
            per_sem_cost = HALF_COST if best_sem_config['is_half_time'] else FULL_COST
            current_sem_cost = per_sem_cost + (INTER_COST if best_sem_config['intersemestral'] else 0) + gap_penalty
            best_sem_config['subjects'] = chosen_subjects
            best_sem_config['credits'] = chosen_credits
            best_sem_config['current_sem_cost'] = current_sem_cost
            best_sem_config['gap_after'] = gap_after

        semester_counts[current_sem] = semester_counts.get(current_sem, 0) + 1
        sem_cost = best_sem_config['current_sem_cost']

        plan.append({
            'semester': current_sem,
            'repetition': semester_counts[current_sem],
            'subjects': best_sem_config['subjects'],
            'credits': best_sem_config['credits'],
            'intersemestral_credits': best_sem_config.get('intersemestral_credits', 0),
            'is_half_time': best_sem_config['is_half_time'],
            'extra_credits': opts.get('extra_credits', 0) if opts else 0,
            'intersemestral': best_sem_config['intersemestral'],
            'cost': sem_cost,
        })

        approved_local.extend(best_sem_config['subjects'])
        if best_sem_config['intersemestral']:
            approved_local.append(best_sem_config['intersemestral'])
        total_credits_local += best_sem_config['credits'] + best_sem_config.get('intersemestral_credits', 0)
        total_cost += sem_cost

        current_sem = _calculate_semester(total_credits_local)

        gc.collect()

    return plan, total_cost

# Fin de archivo

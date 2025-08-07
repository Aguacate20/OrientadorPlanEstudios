# curriculum.py
# Lógica para construir el grafo y generar recomendaciones

import networkx as nx
from itertools import combinations
from courses_data import fisioterapia_courses, enfermeria_courses, credits_per_semester_fisioterapia, credits_per_semester_enfermeria, calculate_semester_fisioterapia, calculate_semester_enfermeria

def build_curriculum_graph(courses):
    G = nx.DiGraph()
    for course, info in courses.items():
        G.add_node(course, credits=info["credits"], semester=info["semester"])
        if "prerequisites" in info:
            for prereq in info["prerequisites"]:
                G.add_edge(prereq, course)
        if "corerequisites" in info:
            for coreq in info["corerequisites"]:
                G.add_edge(coreq, course, type="corequisite")
    return G

def get_available_subjects(G, approved_subjects, current_semester):
    available = []
    mandatory = [course for course in G.nodes if "Inglés" in course or "Core Currículum" in course]
    
    for course in G.nodes:
        # Excluir asignaturas ya aprobadas
        if course in approved_subjects:
            continue
        # Verificar prerrequisitos
        prereqs = [p for p in G.predecessors(course) if G[p][course].get("type") != "corequisite"]
        if all(prereq in approved_subjects for prereq in prereqs):
            # Verificar correquisitos
            coreqs = [c for c in G.predecessors(course) if G[c][course].get("type") == "corequisite"]
            if all(coreq in approved_subjects or coreq in available for coreq in coreqs):
                # Priorizar asignaturas obligatorias en su semestre sugerido
                if course in mandatory and G.nodes[course]["semester"] <= current_semester:
                    available.insert(0, course)
                elif G.nodes[course]["semester"] <= current_semester + 1:  # Permitir asignaturas del siguiente semestre
                    available.append(course)
    return available

def get_intersemestral_options(G, approved_subjects):
    intersemestral = []
    for course in G.nodes:
        if course.startswith("Inglés") or course == "Precálculo":
            # Excluir intersemestrales ya aprobados
            if course in approved_subjects:
                continue
            prereqs = list(G.predecessors(course))
            if all(prereq in approved_subjects for prereq in prereqs):
                intersemestral.append(course)
    return intersemestral

def recommend_subjects(G, approved_subjects, current_semester, credits_per_semester, is_half_time=False, extra_credits=0, intersemestral=None):
    available_subjects = get_available_subjects(G, approved_subjects, current_semester)
    credit_limit = credits_per_semester[current_semester] // 2 - 1 if is_half_time else credits_per_semester[current_semester]
    credit_limit = min(credit_limit + extra_credits, 25)  # Máximo 25 créditos
    if is_half_time and extra_credits > 1:  # Validar máximo 1 crédito extra con media matrícula
        extra_credits = 1
        credit_limit = min(credit_limit + extra_credits, 25)
    
    # Separar asignaturas obligatorias y no obligatorias
    mandatory = [s for s in available_subjects if "Inglés" in s or "Core Currículum" in s]
    optional = [s for s in available_subjects if s not in mandatory]
    
    # Calcular créditos obligatorios
    mandatory_credits = sum(G.nodes[s]["credits"] for s in mandatory if s not in approved_subjects)
    selected_subjects = mandatory.copy()
    total_credits = mandatory_credits
    
    # Optimizar asignaturas opcionales para acercarse al límite de créditos
    best_combination = []
    max_credits = total_credits
    remaining_limit = credit_limit - total_credits
    
    # Probar combinaciones de asignaturas opcionales
    for r in range(1, len(optional) + 1):
        for combo in combinations(optional, r):
            combo_credits = sum(G.nodes[s]["credits"] for s in combo)
            if combo_credits <= remaining_limit and combo_credits > max_credits - mandatory_credits:
                max_credits = mandatory_credits + combo_credits
                best_combination = list(combo)
    
    # Agregar la mejor combinación
    selected_subjects.extend(best_combination)
    total_credits = max_credits
    
    # Incluir intersemestral si aplica (sin contar en el límite de créditos)
    intersemestral_credits = 0
    if intersemestral:
        selected_subjects.append(intersemestral)
        intersemestral_credits = G.nodes[intersemestral]["credits"]
    
    # Calcular costo
    cost = 10000000  # Costo fijo por semestre
    if total_credits > credits_per_semester[current_semester]:
        extra_credits_used = total_credits - credits_per_semester[current_semester]
        cost += extra_credits_used * 800000  # Costo por crédito extra
    
    return selected_subjects, total_credits, intersemestral_credits, cost

def generate_full_plan(G, approved_subjects, program, credits_per_semester, calculate_semester, semester_options):
    plan = []
    current_approved = approved_subjects.copy()
    total_credits_approved = sum(G.nodes[course]["credits"] for course in current_approved)
    current_semester = calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189
    total_cost = 0
    
    while total_credits_approved < total_credits_required:
        # Obtener opciones del usuario o usar valores predeterminados
        is_half_time = semester_options.get(current_semester, {}).get("is_half_time", False)
        extra_credits = semester_options.get(current_semester, {}).get("extra_credits", 0)
        intersemestral = semester_options.get(current_semester, {}).get("intersemestral", None)
        
        # Simular plan con y sin media matrícula
        plan_full_time, cost_full_time = simulate_plan(G, current_approved, program, credits_per_semester, calculate_semester, current_semester, False, extra_credits, intersemestral)
        plan_half_time, cost_half_time = simulate_plan(G, current_approved, program, credits_per_semester, calculate_semester, current_semester, True, extra_credits, intersemestral)
        
        # Elegir la opción con menos semestres
        semesters_full_time = len(plan_full_time)
        semesters_half_time = len(plan_half_time)
        if semesters_half_time < semesters_full_time:
            is_half_time = True
        elif semesters_half_time == semesters_full_time:
            # Si el número de semestres es igual, elegir media matrícula si usa menos créditos extra
            extra_credits_full = sum(p["extra_credits"] for p in plan_full_time)
            extra_credits_half = sum(p["extra_credits"] for p in plan_half_time)
            is_half_time = extra_credits_half < extra_credits_full
        
        # Generar recomendaciones para el semestre actual
        subjects, credits, intersemestral_credits, semester_cost = recommend_subjects(
            G, current_approved, current_semester, credits_per_semester, is_half_time, extra_credits, intersemestral
        )
        plan.append({
            "semester": current_semester,
            "subjects": subjects,
            "credits": credits,
            "intersemestral_credits": intersemestral_credits,
            "is_half_time": is_half_time,
            "extra_credits": extra_credits,
            "intersemestral": intersemestral,
            "cost": semester_cost
        })
        current_approved.extend(subjects)
        total_credits_approved += credits + intersemestral_credits
        total_cost += semester_cost
        if intersemestral:
            current_approved.append(intersemestral)
        current_semester = calculate_semester(total_credits_approved)
    
    return plan, total_cost

def simulate_plan(G, approved_subjects, program, credits_per_semester, calculate_semester, start_semester, is_half_time, extra_credits, intersemestral):
    plan = []
    current_approved = approved_subjects.copy()
    total_credits_approved = sum(G.nodes[course]["credits"] for course in current_approved)
    current_semester = start_semester
    total_credits_required = 180 if program == "Fisioterapia" else 189
    total_cost = 0
    
    while total_credits_approved < total_credits_required:
        subjects, credits, intersemestral_credits, semester_cost = recommend_subjects(
            G, current_approved, current_semester, credits_per_semester, is_half_time, extra_credits, intersemestral
        )
        plan.append({
            "semester": current_semester,
            "subjects": subjects,
            "credits": credits,
            "intersemestral_credits": intersemestral_credits,
            "is_half_time": is_half_time,
            "extra_credits": extra_credits,
            "intersemestral": intersemestral,
            "cost": semester_cost
        })
        current_approved.extend(subjects)
        total_credits_approved += credits + intersemestral_credits
        total_cost += semester_cost
        if intersemestral:
            current_approved.append(intersemestral)
        current_semester = calculate_semester(total_credits_approved)
    
    return plan, total_cost

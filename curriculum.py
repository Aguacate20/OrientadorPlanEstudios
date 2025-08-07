# curriculum.py
# Lógica para construir el grafo y generar recomendaciones

import networkx as nx
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
    selected_subjects = []
    total_credits = 0
    
    # Priorizar asignaturas obligatorias
    mandatory = [s for s in available_subjects if "Inglés" in s or "Core Currículum" in s]
    for subject in mandatory:
        if total_credits + G.nodes[subject]["credits"] <= credit_limit:
            selected_subjects.append(subject)
            total_credits += G.nodes[subject]["credits"]
    
    # Agregar otras asignaturas disponibles
    for subject in available_subjects:
        if subject not in selected_subjects and total_credits + G.nodes[subject]["credits"] <= credit_limit:
            selected_subjects.append(subject)
            total_credits += G.nodes[subject]["credits"]
    
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
        is_half_time = semester_options.get(current_semester, {}).get("is_half_time", False)
        extra_credits = semester_options.get(current_semester, {}).get("extra_credits", 0)
        intersemestral = semester_options.get(current_semester, {}).get("intersemestral", None)
        
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

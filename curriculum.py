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
        if course in approved_subjects:
            continue
        prereqs = [p for p in G.predecessors(course) if G[p][course].get("type") != "corequisite"]
        if all(prereq in approved_subjects for prereq in prereqs):
            coreqs = [c for c in G.predecessors(course) if G[c][course].get("type") == "corequisite"]
            if all(coreq in approved_subjects or coreq in available for coreq in coreqs):
                if course in mandatory and G.nodes[course]["semester"] <= current_semester:
                    available.insert(0, course)
                elif G.nodes[course]["semester"] <= current_semester + 1:
                    available.append(course)
    return available

def get_intersemestral_options(G, approved_subjects):
    intersemestral = []
    for course in G.nodes:
        if course.startswith("Inglés") or course == "Precálculo":
            if course in approved_subjects:
                continue
            prereqs = list(G.predecessors(course))
            if all(prereq in approved_subjects for prereq in prereqs):
                intersemestral.append(course)
    return intersemestral

def recommend_subjects(G, approved_subjects, current_semester, credits_per_semester, is_half_time=False, extra_credits=0, intersemestral=None):
    available_subjects = get_available_subjects(G, approved_subjects, current_semester)
    credit_limit = credits_per_semester[current_semester] // 2 - 1 if is_half_time else credits_per_semester[current_semester]
    credit_limit = min(credit_limit + extra_credits, 25)
    if is_half_time and extra_credits > 1:
        extra_credits = 1
        credit_limit = min(credit_limit + extra_credits, 25)
    
    # Separar asignaturas obligatorias y no obligatorias
    mandatory = [s for s in available_subjects if "Inglés" in s or "Core Currículum" in s]
    optional = [s for s in available_subjects if s not in mandatory]
    
    # Ordenar opcionales por créditos descendentes y semestre sugerido
    optional.sort(key=lambda s: (-G.nodes[s]["credits"], G.nodes[s]["semester"]))
    
    # Seleccionar asignaturas obligatorias
    selected_subjects = mandatory.copy()
    total_credits = sum(G.nodes[s]["credits"] for s in mandatory)
    
    # Agregar asignaturas opcionales para maximizar créditos
    for subject in optional:
        subject_credits = G.nodes[subject]["credits"]
        if total_credits + subject_credits <= credit_limit:
            selected_subjects.append(subject)
            total_credits += subject_credits
    
    # Incluir intersemestral si aplica
    intersemestral_credits = 0
    if intersemestral:
        selected_subjects.append(intersemestral)
        intersemestral_credits = G.nodes[intersemestral]["credits"]
    
    # Calcular costo
    semester_cost = 5000000 if is_half_time else 10000000
    if total_credits > credits_per_semester[current_semester]:
        extra_credits_used = total_credits - credits_per_semester[current_semester]
        semester_cost += extra_credits_used * 800000
    if intersemestral:
        semester_cost += 1500000
    
    return selected_subjects, total_credits, intersemestral_credits, semester_cost, extra_credits

def estimate_remaining_semesters(G, approved_subjects, total_credits_required, credits_per_semester, current_semester, is_half_time=False):
    remaining_credits = total_credits_required - sum(G.nodes[c]["credits"] for c in approved_subjects)
    avg_credits_per_semester = credits_per_semester[current_semester] // 2 - 1 if is_half_time else credits_per_semester[current_semester]
    return max(1, (remaining_credits + avg_credits_per_semester - 1) // avg_credits_per_semester)

def generate_full_plan(G, approved_subjects, program, credits_per_semester, calculate_semester, semester_options):
    plan = []
    current_approved = approved_subjects.copy()
    total_credits_approved = sum(G.nodes[course]["credits"] for course in current_approved)
    current_semester = calculate_semester(total_credits_approved)
    total_credits_required = 180 if program == "Fisioterapia" else 189
    total_cost = 0
    
    while total_credits_approved < total_credits_required:
        best_cost = float('inf')
        best_config = None
        intersemestral_options = get_intersemestral_options(G, current_approved)
        
        # Probar combinaciones de media matrícula, créditos extra e intersemestrales
        for is_half_time in [False, True]:
            max_extra_credits = 1 if is_half_time else 5  # Límite razonable
            for extra_credits in range(max_extra_credits + 1):
                for intersemestral in [None] + intersemestral_options:
                    # Generar recomendación para esta configuración
                    subjects, credits, intersemestral_credits, semester_cost, extra_credits_used = recommend_subjects(
                        G, current_approved, current_semester, credits_per_semester, is_half_time, extra_credits, intersemestral
                    )
                    temp_approved = current_approved + subjects
                    if intersemestral:
                        temp_approved.append(intersemestral)
                    remaining_semesters = estimate_remaining_semesters(
                        G, temp_approved, total_credits_required, credits_per_semester, current_semester + 1, is_half_time
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
                            "extra_credits": extra_credits_used,
                            "intersemestral": intersemestral
                        }
        
        # Aplicar la mejor configuración
        plan.append({
            "semester": current_semester,
            "subjects": best_config["subjects"],
            "credits": best_config["credits"],
            "intersemestral_credits": best_config["intersemestral_credits"],
            "is_half_time": best_config["is_half_time"],
            "extra_credits": best_config["extra_credits"],
            "intersemestral": best_config["intersemestral"],
            "cost": best_config["semester_cost"]
        })
        current_approved.extend(best_config["subjects"])
        total_credits_approved += best_config["credits"] + best_config["intersemestral_credits"]
        total_cost += best_config["semester_cost"]
        if best_config["intersemestral"]:
            current_approved.append(best_config["intersemestral"])
        current_semester = calculate_semester(total_credits_approved)
        
        # Actualizar opciones del usuario si existen
        if current_semester in semester_options:
            semester_options[current_semester]["is_half_time"] = best_config["is_half_time"]
            semester_options[current_semester]["extra_credits"] = best_config["extra_credits"]
            semester_options[current_semester]["intersemestral"] = best_config["intersemestral"]
    
    return plan, total_cost

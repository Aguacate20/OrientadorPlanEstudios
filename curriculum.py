import networkx as nx
from functools import lru_cache
from courses_data import fisioterapia_courses, enfermeria_courses, credits_per_semester_fisioterapia, credits_per_semester_enfermeria, calculate_semester_fisioterapia, calculate_semester_enfermeria

def build_curriculum_graph(courses):
    G = nx.DiGraph()
    prereq_cache = {}  # Cache for prerequisites and corequisites
    for course, info in courses.items():
        G.add_node(course, credits=info["credits"], semester=info["semester"])
        prereqs = info.get("prerequisites", [])
        coreqs = info.get("corerequisites", [])
        prereq_cache[course] = {"prerequisites": prereqs, "corerequisites": coreqs}
        for prereq in prereqs:
            G.add_edge(prereq, course)
        for coreq in coreqs:
            G.add_edge(coreq, course, type="corequisite")
    return G, prereq_cache

@lru_cache(maxsize=1000)
def get_available_subjects(G_tuple, approved_subjects_tuple, current_semester):
    G, prereq_cache = G_tuple  # Unpack graph and cache
    approved_subjects = list(approved_subjects_tuple)  # Convert tuple back to list
    available = []
    mandatory = [course for course in G.nodes if "Inglés" in course or "Core Currículum" in course]
    
    for course in G.nodes:
        if course in approved_subjects:
            continue
        prereqs = prereq_cache[course]["prerequisites"]
        if all(prereq in approved_subjects for prereq in prereqs):
            coreqs = prereq_cache[course]["corerequisites"]
            if all(coreq in approved_subjects or coreq in available for coreq in coreqs):
                if course in mandatory and G.nodes[course]["semester"] <= current_semester:
                    available.insert(0, course)
                elif G.nodes[course]["semester"] <= current_semester + 1:
                    available.append(course)
    return tuple(available)  # Return tuple for caching

def get_intersemestral_options(G_tuple, approved_subjects):
    G, prereq_cache = G_tuple
    intersemestral = []
    for course in G.nodes:
        if course.startswith("Inglés") or course == "Precálculo":
            if course in approved_subjects:
                continue
            prereqs = prereq_cache[course]["prerequisites"]
            if all(prereq in approved_subjects for prereq in prereqs):
                intersemestral.append(course)
    # Limit to at most 2 intersemestral options
    return intersemestral[:2]

def recommend_subjects(G_tuple, approved_subjects, current_semester, credits_per_semester, is_half_time=False, extra_credits=0, intersemestral=None):
    G, prereq_cache = G_tuple
    available_subjects = get_available_subjects((G, prereq_cache), tuple(approved_subjects), current_semester)
    available_subjects = list(available_subjects)  # Convert back to list
    semester_key = min(current_semester, 10)
    credit_limit = credits_per_semester[semester_key] // 2 - 1 if is_half_time else credits_per_semester[semester_key]
    credit_limit = min(credit_limit + extra_credits, 25)
    if is_half_time and extra_credits > 1:
        extra_credits = 1
        credit_limit = min(credit_limit + extra_credits, 25)
    
    mandatory = [s for s in available_subjects if "Inglés" in s or "Core Currículum" in s]
    optional = [s for s in available_subjects if s not in mandatory]
    optional.sort(key=lambda s: (-G.nodes[s]["credits"], G.nodes[s]["semester"]))
    
    selected_subjects = mandatory.copy()
    total_credits = sum(G.nodes[s]["credits"] for s in mandatory)
    
    for subject in optional:
        subject_credits = G.nodes[subject]["credits"]
        if total_credits + subject_credits <= credit_limit:
            selected_subjects.append(subject)
            total_credits += subject_credits
    
    intersemestral_credits = 0
    if intersemestral:
        selected_subjects.append(intersemestral)
        intersemestral_credits = G.nodes[intersemestral]["credits"]
    
    semester_cost = 5000000 if is_half_time else 10000000
    if total_credits > credits_per_semester[semester_key]:
        extra_credits_used = total_credits - credits_per_semester[semester_key]
        semester_cost += extra_credits_used * 800000
    if intersemestral:
        semester_cost += 1500000
    
    return selected_subjects, total_credits, intersemestral_credits, semester_cost, extra_credits

def estimate_remaining_semesters(G_tuple, approved_subjects, total_credits_required, credits_per_semester, current_semester, is_half_time=False):
    G, _ = G_tuple
    remaining_credits = total_credits_required - sum(G.nodes[c]["credits"] for c in approved_subjects)
    semester_key = min(current_semester, 10)
    avg_credits_per_semester = credits_per_semester[semester_key] // 2 - 1 if is_half_time else credits_per_semester[semester_key]
    return max(1, (remaining_credits + avg_credits_per_semester - 1) // avg_credits_per_semester)

def generate_full_plan(G_tuple, approved_subjects, program, credits_per_semester, calculate_semester, semester_options):
    G, prereq_cache = G_tuple
    plan = []
    current_approved = approved_subjects.copy()
    total_credits_approved = sum(G.nodes[course]["credits"] for course in current_approved)
    current_semester = min(calculate_semester(total_credits_approved), 10)
    total_credits_required = 180 if program == "Fisioterapia" else 189
    total_cost = 0
    semester_counter = current_semester
    credit_thresholds = {i: sum(credits_per_semester.get(j, credits_per_semester[10]) for j in range(1, i + 1)) for i in range(1, 11)}
    
    while total_credits_approved < total_credits_required:
        best_cost = float('inf')
        best_config = None
        intersemestral_options = get_intersemestral_options((G, prereq_cache), current_approved)
        
        for is_half_time in [False, True]:
            max_extra_credits = 1 if is_half_time else 3  # Reduced from 5
            for extra_credits in range(max_extra_credits + 1):
                for intersemestral in [None] + intersemestral_options:
                    subjects, credits, intersemestral_credits, semester_cost, extra_credits_used = recommend_subjects(
                        (G, prereq_cache), current_approved, current_semester, credits_per_semester, is_half_time, extra_credits, intersemestral
                    )
                    temp_approved = current_approved + subjects
                    if intersemestral:
                        temp_approved.append(intersemestral)
                    remaining_semesters = estimate_remaining_semesters(
                        (G, prereq_cache), temp_approved, total_credits_required, credits_per_semester, current_semester, is_half_time
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
        
        plan.append({
            "semester": semester_counter,
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
        
        current_semester = min(calculate_semester(total_credits_approved), 10)
        next_semester_threshold = credit_thresholds.get(semester_counter + 1, credit_thresholds[10])
        if total_credits_approved >= next_semester_threshold and not best_config["is_half_time"]:
            semester_counter += 1
        elif best_config["is_half_time"]:
            if total_credits_approved >= credit_thresholds.get(semester_counter + 1, credit_thresholds[10]):
                semester_counter += 1
    
    return plan, total_cost

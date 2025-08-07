# courses_data.py
# Datos de los cursos y funciones para calcular el semestre

fisioterapia_courses = {
    "Competencias idiomáticas básicas": {"credits": 2, "semester": 1},
    "Ciencias básicas": {"credits": 6, "semester": 1},
    "Morfofisiología I": {"credits": 6, "semester": 1},
    "Fundamentos de Fisioterapia": {"credits": 3, "semester": 1},
    "Morfofisiología II": {"credits": 6, "semester": 2, "prerequisites": ["Morfofisiología I", "Ciencias básicas"]},
    "Desarrollo motor humano": {"credits": 2, "semester": 2},
    "Psicología del aprendizaje": {"credits": 2, "semester": 2},
    "Competencias básicas digitales": {"credits": 3, "semester": 2},
    "Condiciones de salud y movimiento corporal humano": {"credits": 4, "semester": 3, "prerequisites": ["Morfofisiología II"]},
    "Biomecánica": {"credits": 6, "semester": 3, "prerequisites": ["Morfofisiología II"]},
    "Salud mental y movimiento corporal humano": {"credits": 4, "semester": 3},
    "Evaluación y diagnóstico fisioterapéutico I": {"credits": 4, "semester": 4, "prerequisites": ["Condiciones de salud y movimiento corporal humano", "Biomecánica"]},
    "Tecnología en fisioterapia": {"credits": 4, "semester": 4},
    "Fisiología y prescripción del ejercicio": {"credits": 3, "semester": 4, "prerequisites": ["Morfofisiología II"]},
    "Precálculo": {"credits": 2, "semester": 4},
    "Bioestadística y epidemiología": {"credits": 2, "semester": 5, "prerequisites": ["Precálculo"]},
    "Evaluación y diagnóstico fisioterapéutico II": {"credits": 4, "semester": 5, "prerequisites": ["Evaluación y diagnóstico fisioterapéutico I", "Inglés 3"]},
    "Procesos de interacción fisioterapéutica I": {"credits": 4, "semester": 5, "prerequisites": ["Evaluación y diagnóstico fisioterapéutico I"]},
    "Fundamentos de salud pública": {"credits": 3, "semester": 5},
    "Investigación I": {"credits": 2, "semester": 6, "prerequisites": ["Bioestadística y epidemiología"]},
    "Procesos de interacción fisioterapéutica II": {"credits": 4, "semester": 6, "prerequisites": ["Evaluación y diagnóstico fisioterapéutico II"]},
    "Práctica formativa en Salud Pública": {"credits": 5, "semester": 6, "prerequisites": ["Desarrollo motor humano", "Fundamentos de salud pública", "Evaluación y diagnóstico fisioterapéutico II"]},
    "Educación en salud y programas": {"credits": 2, "semester": 6, "corerequisites": ["Práctica formativa en Salud Pública"]},
    "Investigación II": {"credits": 2, "semester": 7, "prerequisites": ["Investigación I"]},
    "Administración y gestión de proyectos en fisioterapia": {"credits": 4, "semester": 7},
    "Práctica formativa integral I": {"credits": 9, "semester": 7, "prerequisites": ["Procesos de interacción fisioterapéutica II", "Práctica formativa en Salud Pública", "Tecnología en fisioterapia", "Inglés 5"]},
    "Profundización I": {"credits": 4, "semester": 7, "prerequisites": ["Práctica formativa en Salud Pública"]},
    "Research seminar III": {"credits": 2, "semester": 8, "prerequisites": ["Investigación II"]},
    "Práctica formativa integral II": {"credits": 9, "semester": 8, "prerequisites": ["Práctica formativa integral I"]},
    "Profundización II": {"credits": 4, "semester": 8, "prerequisites": ["Práctica formativa integral I"]},
    "Espíritu emprendedor": {"credits": 2, "semester": 8},
    "Opción de grado I": {"credits": 2, "semester": 9, "prerequisites": ["Research seminar III"]},
    "Práctica de profundización I": {"credits": 9, "semester": 9, "prerequisites": ["Inglés 7", "Profundización I", "Práctica formativa integral II"]},
    "Electiva 1": {"credits": 2, "semester": 9},
    "Electiva 2": {"credits": 2, "semester": 9},
    "Opción de grado II": {"credits": 2, "semester": 10, "prerequisites": ["Opción de grado I"]},
    "Práctica de profundización II": {"credits": 9, "semester": 10, "prerequisites": ["Profundización II", "Práctica de profundización I"]},
    "Electiva 3": {"credits": 2, "semester": 10},
    "Electiva 4": {"credits": 2, "semester": 10},
    "Inglés 1": {"credits": 2, "semester": 1},
    "Inglés 2": {"credits": 3, "semester": 2, "prerequisites": ["Inglés 1"]},
    "Inglés 3": {"credits": 3, "semester": 3, "prerequisites": ["Inglés 1", "Inglés 2"]},
    "Inglés 4": {"credits": 3, "semester": 4, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3"]},
    "Inglés 5": {"credits": 3, "semester": 5, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4"]},
    "Inglés 6": {"credits": 3, "semester": 6, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4", "Inglés 5"]},
    "Inglés 7": {"credits": 3, "semester": 7, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4", "Inglés 5", "Inglés 6"]},
    "Core Currículum Persona y Cultura I": {"credits": 2, "semester": 2},
    "Core Currículum Persona y Cultura II": {"credits": 2, "semester": 3, "prerequisites": ["Core Currículum Persona y Cultura I"]},
    "Core Currículum Persona y Cultura III": {"credits": 2, "semester": 4, "prerequisites": ["Core Currículum Persona y Cultura I", "Core Currículum Persona y Cultura II"]},
    "Core Currículum Persona y Cultura IV": {"credits": 2, "semester": 5, "prerequisites": ["Core Currículum Persona y Cultura I", "Core Currículum Persona y Cultura II", "Core Currículum Persona y Cultura III"]},
    "Core Currículum Persona y Cultura V": {"credits": 3, "semester": 6, "prerequisites": ["Core Currículum Persona y Cultura I", "Core Currículum Persona y Cultura II", "Core Currículum Persona y Cultura III", "Core Currículum Persona y Cultura IV"]}
}

enfermeria_courses = {
    "Competencias Idiomáticas Básicas": {"credits": 2, "semester": 1},
    "Inglés 1": {"credits": 2, "semester": 1},
    "Morfofisiología I": {"credits": 6, "semester": 1},
    "Ciencias Básicas": {"credits": 6, "semester": 1},
    "Naturaleza del Cuidado": {"credits": 2, "semester": 1},
    "Core Curriculum Persona y Cultura I": {"credits": 2, "semester": 2},
    "Inglés 2": {"credits": 3, "semester": 2, "prerequisites": ["Inglés 1"]},
    "Morfofisiología II": {"credits": 6, "semester": 2, "prerequisites": ["Morfofisiología I", "Ciencias Básicas"]},
    "Fundamentación del Cuidado": {"credits": 4, "semester": 2, "prerequisites": ["Naturaleza del Cuidado", "Ciencias Básicas", "Morfofisiología I"]},
    "Desarrollo Teórico de Enfermería": {"credits": 3, "semester": 2},
    "Microbiología": {"credits": 2, "semester": 2, "prerequisites": ["Ciencias Básicas"]},
    "Core Curriculum Persona y Cultura II": {"credits": 2, "semester": 3, "prerequisites": ["Core Curriculum Persona y Cultura I"]},
    "Inglés 3": {"credits": 3, "semester": 3, "prerequisites": ["Inglés 1", "Inglés 2"]},
    "Fisiopatología": {"credits": 3, "semester": 3, "prerequisites": ["Morfofisiología II"], "corerequisites": ["Semiología"]},
    "Psicología del Aprendizaje": {"credits": 2, "semester": 3},
    "Semiología": {"credits": 3, "semester": 3, "prerequisites": ["Fundamentación del Cuidado", "Morfofisiología II"]},
    "Embriología y Genética": {"credits": 2, "semester": 3},
    "Cuidado del Adulto I": {"credits": 6, "semester": 3, "prerequisites": ["Fundamentación del Cuidado", "Morfofisiología II"], "corerequisites": ["Fisiopatología"]},
    "Core Curriculum Persona y Cultura III": {"credits": 2, "semester": 4, "prerequisites": ["Core Curriculum Persona y Cultura I", "Core Curriculum Persona y Cultura II"]},
    "Inglés 4": {"credits": 3, "semester": 4, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3"]},
    "Precálculo": {"credits": 2, "semester": 4},
    "Competencias Básicas Digitales": {"credits": 3, "semester": 4},
    "Psicología del Desarrollo": {"credits": 3, "semester": 4, "prerequisites": ["Psicología del Aprendizaje"]},
    "Farmacología I": {"credits": 2, "semester": 4, "prerequisites": ["Microbiología"]},
    "Cuidado del Adulto II": {"credits": 7, "semester": 4, "prerequisites": ["Fisiopatología", "Cuidado del Adulto I", "Farmacología I"]},
    "Core Curriculum Persona y Cultura IV": {"credits": 2, "semester": 5, "prerequisites": ["Core Curriculum Persona y Cultura I", "Core Curriculum Persona y Cultura II", "Core Curriculum Persona y Cultura III"]},
    "Inglés 5": {"credits": 3, "semester": 5, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4"]},
    "Bioestadística y Epidemiología": {"credits": 2, "semester": 5, "prerequisites": ["Precálculo"]},
    "Teoría del Servicio y de la Calidad": {"credits": 3, "semester": 5},
    "Farmacología II": {"credits": 2, "semester": 5, "prerequisites": ["Farmacología I"]},
    "Cuidado del Adulto III": {"credits": 7, "semester": 5, "prerequisites": ["Cuidado del Adulto II", "Farmacología I", "Inglés 3"], "corerequisites": ["Farmacología II"]},
    "Electiva I": {"credits": 2, "semester": 5},
    "Core Curriculum Persona y Cultura V": {"credits": 3, "semester": 6, "prerequisites": ["Core Curriculum Persona y Cultura I", "Core Curriculum Persona y Cultura II", "Core Curriculum Persona y Cultura III", "Core Curriculum Persona y Cultura IV"]},
    "Inglés 6": {"credits": 3, "semester": 6, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4", "Inglés 5"]},
    "Investigación I": {"credits": 2, "semester": 6, "prerequisites": ["Bioestadística y Epidemiología"]},
    "Farmacología III": {"credits": 2, "semester": 6, "prerequisites": ["Farmacología II"]},
    "Cuidado de la Mujer y Neonato": {"credits": 9, "semester": 6, "prerequisites": ["Cuidado del Adulto III", "Embriología y Genética"], "corerequisites": ["Farmacología III"]},
    "Inglés 7": {"credits": 3, "semester": 7, "prerequisites": ["Inglés 1", "Inglés 2", "Inglés 3", "Inglés 4", "Inglés 5", "Inglés 6"]},
    "Investigación II": {"credits": 2, "semester": 7, "prerequisites": ["Investigación I"]},
    "Gestión Humana": {"credits": 3, "semester": 7},
    "Cuidado al Niño y al Adolescente": {"credits": 9, "semester": 7, "prerequisites": ["Cuidado del Adulto III", "Farmacología III", "Inglés 5"]},
    "Deontología de Enfermería": {"credits": 1, "semester": 7},
    "Electiva II": {"credits": 2, "semester": 7},
    "Research Seminar III": {"credits": 2, "semester": 8, "prerequisites": ["Investigación II"]},
    "Educación en Salud y Programas": {"credits": 2, "semester": 8},
    "Gestión de Calidad en el Servicio": {"credits": 3, "semester": 8},
    "Contabilidad Financiera": {"credits": 3, "semester": 8},
    "Salud Mental y Psiquiatría": {"credits": 6, "semester": 8, "prerequisites": ["Cuidado del Adulto III", "Farmacología III", "Cuidado al Niño y al Adolescente"]},
    "Opción de Grado I": {"credits": 2, "semester": 9, "prerequisites": ["Research Seminar III"]},
    "Gestión del Cuidado I": {"credits": 13, "semester": 9, "prerequisites": ["Inglés 7", "Cuidado de la Mujer y Neonato", "Cuidado al Niño y al Adolescente", "Salud Mental y Psiquiatría"]},
    "Electiva III": {"credits": 2, "semester": 9},
    "Opción de Grado II": {"credits": 2, "semester": 10, "prerequisites": ["Opción de Grado I"]},
    "Gestión del Cuidado II": {"credits": 13, "semester": 10, "prerequisites": ["Gestión del Cuidado I"]}
}

credits_per_semester_fisioterapia = {1: 19, 2: 18, 3: 19, 4: 18, 5: 18, 6: 19, 7: 22, 8: 17, 9: 15, 10: 15}
credits_per_semester_enfermeria = {1: 18, 2: 20, 3: 21, 4: 22, 5: 21, 6: 19, 7: 20, 8: 16, 9: 17, 10: 15}

def calculate_semester_fisioterapia(credits):
    if credits <= 13:
        return 1
    elif credits <= 31:
        return 2
    elif credits <= 50:
        return 3
    elif credits <= 68:
        return 4
    elif credits <= 86:
        return 5
    elif credits <= 105:
        return 6
    elif credits <= 127:
        return 7
    elif credits <= 144:
        return 8
    elif credits <= 159:
        return 9
    else:
        return 10

def calculate_semester_enfermeria(credits):
    if credits <= 12:
        return 1
    elif credits <= 32:
        return 2
    elif credits <= 53:
        return 3
    elif credits <= 75:
        return 4
    elif credits <= 96:
        return 5
    elif credits <= 115:
        return 6
    elif credits <= 135:
        return 7
    elif credits <= 151:
        return 8
    elif credits <= 168:
        return 9
    else:
        return 10

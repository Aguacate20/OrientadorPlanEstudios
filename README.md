Orientador de Plan de Estudios
Este proyecto es una aplicación web desarrollada con Streamlit que ayuda a estudiantes de Fisioterapia y Enfermería a planificar sus semestres académicos, considerando prerrequisitos, correquisitos, media matrícula, compra de créditos e intersemestrales.
Instalación

Clona el repositorio:
git clone <URL_DEL_REPOSITORIO>
cd project


Crea un entorno virtual e instala las dependencias:
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt


Ejecuta la aplicación:
streamlit run app.py



Estructura del proyecto

app.py: Interfaz principal de Streamlit.
curriculum.py: Lógica para construir el grafo y generar recomendaciones.
courses_data.py: Datos de los cursos y funciones para calcular el semestre.
requirements.txt: Dependencias del proyecto.

Uso

Selecciona tu programa (Fisioterapia o Enfermería).
Marca las asignaturas aprobadas, organizadas por semestre.
Configura opciones para cada semestre (media matrícula, créditos extra, intersemestral).
Haz clic en "Generar plan de estudios" para ver las recomendaciones.

Reglas

Las asignaturas de Inglés y Core Currículum son obligatorias si están disponibles.
Media matrícula limita los créditos a la mitad del estándar menos 1.
Máximo 25 créditos por semestre, incluyendo créditos extra comprados.
Intersemestrales (Inglés o Precálculo) no cuentan en el límite de créditos.

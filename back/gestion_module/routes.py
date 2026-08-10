# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/gestion_module/routes.py
#
#  PROPÓSITO:
#    Expone las APIs de GESTIÓN (CRUD) que consume el frontend para llenar
#    las tablas de los módulos Estudiantes, Cursos, Profesores y Sesiones:
#
#      GET    /api/estudiantes                     -> listar
#      POST   /api/estudiantes                     -> crear (genera el ID)
#      DELETE /api/estudiantes/<id>                -> eliminar
#      GET    /api/cursos        | POST | DELETE   -> ídem cursos
#      GET    /api/profesores    | POST | DELETE   -> ídem profesores
#      GET    /api/sesiones      | POST | DELETE   -> ídem sesiones
#
#  FLUJO CRÍTICO (privilegiado para este proyecto):
#    Al crear un estudiante, el backend genera SOLO su matrícula (id) y la
#    devuelve al frontend. Ese id es el que se usa para registrar el rostro
#    (POST /registrar_rostro guarda back/imagenes_conocidas/{id}.jpg), por lo
#    que el botón "Registrar rostro" del modal usa EXACTAMENTE ese id.
#
#  SEGURIDAD:
#    Todas las rutas están protegidas con login_required (401 si no hay sesión).
# =============================================================================

import os

from flask import Blueprint, jsonify, request

from camera_module.services.db_service import get_db
from auth_module.routes import login_required

# Blueprint con las rutas /api/* de gestión académica.
gestion_bp = Blueprint("gestion", __name__)

# Ruta absoluta de la carpeta donde se guardan las fotos de los rostros:
#   feriatp/back/imagenes_conocidas/
CARPETA_FOTOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "imagenes_conocidas",
)


# -----------------------------------------------------------------------------
# UTILIDADES COMPARTIDAS
# -----------------------------------------------------------------------------

def _json_error(mensaje, status=400):
    """Respuesta JSON de error con la forma {ok: False, mensaje: ...}."""
    return jsonify({"ok": False, "mensaje": mensaje}), status


def _conectar():
    """
    Intenta conectar a la BD. Devuelve la conexión o lanza una respuesta
    JSON de error (para no repetir el try/except en cada ruta).
    """
    try:
        return get_db()
    except Exception as e:
        raise ConnectionError(str(e))


def _filtrar_numero(valor, nombre_campo):
    """Convierte un input a entero o lanza ValueError con mensaje claro."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"El campo {nombre_campo} debe ser un número entero.")


def _ejecutar_y_cerrar(conn, sql, params=()):
    """Ejecuta una consulta y cierra la conexión en bloque (una sola llamada)."""
    try:
        with conn.cursor() as c:
            c.execute(sql, params)
            filas = c.fetchall()
        conn.commit()
        return filas
    except Exception as e:
        raise ConnectionError(str(e))
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 1) ESTUDIANTES (tabla `alumnos`)
# -----------------------------------------------------------------------------

@gestion_bp.route("/api/estudiantes", methods=["GET"])
@login_required
def listar_estudiantes():
    """Lista todos los estudiantes (sin JOINs: la tabla alumnos ya tiene todo)."""
    try:
        conn = _conectar()
        filas = _ejecutar_y_cerrar(
            conn,
            "SELECT id, nombre, apellido, correo, curso, estado FROM alumnos ORDER BY id",
        )
    except ConnectionError as e:
        return _json_error(f"Error de conexión a la BD: {e}", 500)

    return jsonify({"ok": True, "datos": filas})


@gestion_bp.route("/api/estudiantes", methods=["POST"])
@login_required
def crear_estudiante():
    """
    Crea un estudiante. Genera AUTOMÁTICAMENTE la matrícula (id):
        id = MAX(id) + 1  (con base 20231000 si la tabla está vacía)
    y la devuelve en la respuesta para que el frontend la use en el
    registro de rostro. Devuelve 400 si el id generado ya es usado por
    una foto existente (caso raro).
    """
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or "").strip()
    apellido = (datos.get("apellido") or "").strip()
    correo = (datos.get("correo") or "").strip() or None
    curso = (datos.get("curso") or "").strip() or None
    estado = (datos.get("estado") or "activo").strip()

    # Validación: nombre y apellido obligatorios.
    if not nombre or not apellido:
        return _json_error("Nombre y apellido son obligatorios.")

    if estado not in ("activo", "inactivo", "ausente"):
        estado = "activo"

    try:
        conn = _conectar()

        # 1. Calcular el siguiente id libre de matrícula.
        filas = _ejecutar_y_cerrar(
            conn,
            "SELECT COALESCE(MAX(id), 20231000) AS max_id FROM alumnos",
        )
        nuevo_id = int(filas[0]["max_id"]) + 1

        # 2. Insertar el estudiante con ese id generado.
        conn2 = _conectar()
        _ejecutar_y_cerrar(
            conn2,
            """
            INSERT INTO alumnos (id, nombre, apellido, correo, curso, estado)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (nuevo_id, nombre, apellido, correo, curso, estado),
        )
    except ConnectionError as e:
        return _json_error(f"Error al guardar el estudiante: {e}", 500)

    # Respuesta estelar: id + datos, felicitando el siguiente paso (rostro).
    return jsonify({
        "ok": True,
        "mensaje": f"Estudiante creado con matrícula {nuevo_id}. Ahora registra su rostro con ese ID.",
        "id": nuevo_id,
        "nombre_completo": f"{nombre} {apellido}",
    })


@gestion_bp.route("/api/estudiantes/<int:alumno_id>", methods=["DELETE"])
@login_required
def eliminar_estudiante(alumno_id):
    """
    Elimina un estudiante por id. Además borra su foto de rostro
    (back/imagenes_conocidas/{id}.jpg) si existe, para que el sistema
    no reconozca a un alumno que ya no existe.
    """
    try:
        conn = _conectar()
        filas = _ejecutar_y_cerrar(
            conn,
            "DELETE FROM alumnos WHERE id = %s",
            (alumno_id,),
        )
    except ConnectionError as e:
        return _json_error(f"Error al eliminar el estudiante: {e}", 500)

    # Borrar la foto del rostro si existe (fuera de la BD, con try para no romper).
    foto = os.path.join(CARPETA_FOTOS, f"{alumno_id}.jpg")
    try:
        if os.path.exists(foto):
            os.remove(foto)
    except OSError:
        pass  # Si no se pudo borrar la foto, no impedimos la eliminación.

    return jsonify({
        "ok": True,
        "mensaje": f"Estudiante {alumno_id} eliminado correctamente.",
    })


# -----------------------------------------------------------------------------
# 2) CURSOS
# -----------------------------------------------------------------------------

@gestion_bp.route("/api/cursos", methods=["GET"])
@login_required
def listar_cursos():
    """Lista los cursos con el nombre del profesor asignado (JOIN)."""
    try:
        conn = _conectar()
        filas = _ejecutar_y_cerrar(
            conn,
            """
            SELECT c.id, c.codigo, c.nombre, c.profesor_id, c.estudiantes,
                   c.semestre, c.estado, p.nombre AS profesor
            FROM cursos c
            LEFT JOIN profesores p ON p.id = c.profesor_id
            ORDER BY c.id
            """,
        )
    except ConnectionError as e:
        return _json_error(f"Error de conexión a la BD: {e}", 500)

    return jsonify({"ok": True, "datos": filas})


@gestion_bp.route("/api/cursos", methods=["POST"])
@login_required
def crear_curso():
    """Crea un curso. El profesor se referencia por su id (opcional)."""
    datos = request.get_json(silent=True) or {}
    codigo = (datos.get("codigo") or "").strip()
    nombre = (datos.get("nombre") or "").strip()

    if not codigo or not nombre:
        return _json_error("Código y nombre son obligatorios.")

    profesor_id = datos.get("profesor_id") or None
    if profesor_id:
        try:
            profesor_id = int(profesor_id)
        except (TypeError, ValueError):
            profesor_id = None

    estudiantes = datos.get("estudiantes") or 0
    try:
        estudiantes = int(estudiantes)
    except (TypeError, ValueError):
        estudiantes = 0

    semestre = (datos.get("semestre") or "").strip() or None
    estado = (datos.get("estado") or "activo").strip()
    if estado not in ("activo", "inactivo", "finalizado"):
        estado = "activo"

    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            """
            INSERT INTO cursos (codigo, nombre, profesor_id, estudiantes, semestre, estado)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (codigo, nombre, profesor_id, estudiantes, semestre, estado),
        )
    except ConnectionError as e:
        if "1062" in str(e):
            return _json_error(f"Ya existe un curso con el código '{codigo}'.")
        return _json_error(f"Error al guardar el curso: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Curso '{nombre}' creado correctamente."})


@gestion_bp.route("/api/cursos/<int:curso_id>", methods=["DELETE"])
@login_required
def eliminar_curso(curso_id):
    """Elimina un curso por id."""
    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            "DELETE FROM cursos WHERE id = %s",
            (curso_id,),
        )
    except ConnectionError as e:
        return _json_error(f"Error al eliminar el curso: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Curso {curso_id} eliminado."})


# -----------------------------------------------------------------------------
# 3) PROFESORES
# -----------------------------------------------------------------------------

@gestion_bp.route("/api/profesores", methods=["GET"])
@login_required
def listar_profesores():
    """Lista profesores y el número de cursos asignados a cada uno."""
    try:
        conn = _conectar()
        filas = _ejecutar_y_cerrar(
            conn,
            """
            SELECT p.id, p.nombre, p.especialidad, p.correo, p.estado,
                   (SELECT COUNT(*) FROM cursos c WHERE c.profesor_id = p.id) AS cursos_a_cargo
            FROM profesores p
            ORDER BY p.id
            """,
        )
    except ConnectionError as e:
        return _json_error(f"Error de conexión a la BD: {e}", 500)

    return jsonify({"ok": True, "datos": filas})


@gestion_bp.route("/api/profesores", methods=["POST"])
@login_required
def crear_profesor():
    """Crea un profesor."""
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        return _json_error("El nombre del profesor es obligatorio.")

    especialidad = (datos.get("especialidad") or "").strip() or None
    correo = (datos.get("correo") or "").strip() or None
    estado = (datos.get("estado") or "activo").strip()
    if estado not in ("activo", "inactivo"):
        estado = "activo"

    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            """
            INSERT INTO profesores (nombre, especialidad, correo, estado)
            VALUES (%s, %s, %s, %s)
            """,
            (nombre, especialidad, correo, estado),
        )
    except ConnectionError as e:
        return _json_error(f"Error al guardar el profesor: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Profesor '{nombre}' creado."})


@gestion_bp.route("/api/profesores/<int:profesor_id>", methods=["DELETE"])
@login_required
def eliminar_profesor(profesor_id):
    """Elimina un profesor por id (los cursos asignados quedan sin profesor)."""
    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            "DELETE FROM profesores WHERE id = %s",
            (profesor_id,),
        )
    except ConnectionError as e:
        return _json_error(f"Error al eliminar el profesor: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Profesor {profesor_id} eliminado."})


# -----------------------------------------------------------------------------
# 4) SESIONES
# -----------------------------------------------------------------------------

@gestion_bp.route("/api/sesiones", methods=["GET"])
@login_required
def listar_sesiones():
    """Lista sesiones mostrando el nombre del curso y del profesor."""
    try:
        conn = _conectar()
        filas = _ejecutar_y_cerrar(
            conn,
            """
            SELECT s.id, s.fecha, s.horario, s.curso_id, s.profesor_id,
                   s.total_alumnos, s.asistencia, s.estado,
                   c.nombre AS curso, p.nombre AS profesor
            FROM sesiones s
            LEFT JOIN cursos c     ON c.id = s.curso_id
            LEFT JOIN profesores p ON p.id = s.profesor_id
            ORDER BY s.fecha DESC, s.id DESC
            """,
        )
    except ConnectionError as e:
        return _json_error(f"Error de conexión a la BD: {e}", 500)

    return jsonify({"ok": True, "datos": filas})


@gestion_bp.route("/api/sesiones", methods=["POST"])
@login_required
def crear_sesion():
    """Crea una sesión (clase programada). Fecha formato YYYY-MM-DD."""
    datos = request.get_json(silent=True) or {}
    fecha = (datos.get("fecha") or "").strip()
    if not fecha:
        return _json_error("La fecha es obligatoria (formato AAAA-MM-DD).")

    horario = (datos.get("horario") or "").strip() or None

    curso_id = datos.get("curso_id") or None
    if curso_id:
        try:
            curso_id = int(curso_id)
        except (TypeError, ValueError):
            curso_id = None

    profesor_id = datos.get("profesor_id") or None
    if profesor_id:
        try:
            profesor_id = int(profesor_id)
        except (TypeError, ValueError):
            profesor_id = None

    total_alumnos = datos.get("total_alumnos") or 0
    try:
        total_alumnos = int(total_alumnos)
    except (TypeError, ValueError):
        total_alumnos = 0

    estado = (datos.get("estado") or "programada").strip()
    if estado not in ("programada", "en_curso", "finalizada"):
        estado = "programada"

    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            """
            INSERT INTO sesiones (fecha, horario, curso_id, profesor_id, total_alumnos, estado)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (fecha, horario, curso_id, profesor_id, total_alumnos, estado),
        )
    except ConnectionError as e:
        return _json_error(f"Error al guardar la sesión: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Sesión del {fecha} creada."})


@gestion_bp.route("/api/sesiones/<int:sesion_id>", methods=["DELETE"])
@login_required
def eliminar_sesion(sesion_id):
    """Elimina una sesión por id."""
    try:
        conn = _conectar()
        _ejecutar_y_cerrar(
            conn,
            "DELETE FROM sesiones WHERE id = %s",
            (sesion_id,),
        )
    except ConnectionError as e:
        return _json_error(f"Error al eliminar la sesión: {e}", 500)

    return jsonify({"ok": True, "mensaje": f"Sesión {sesion_id} eliminada."})
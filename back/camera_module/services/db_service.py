# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/camera_module/services/db_service.py
#
#  PROPÓSITO:
#    Capa de acceso a la BASE DE DATOS MySQL. Es el ÚNICO archivo del proyecto
#    que se conecta a la BD (por eso es tan importante).
#
#  TABLAS QUE SE USAN:
#    1. `alumnos`      -> SELECT * FROM alumnos WHERE id = %s   (leer datos del alumno)
#    2. `asistencias`  -> SELECT id ... (¿ya marcó hoy?)  /  INSERT (marcar asistencia)
#
#  BASE DE DATOS:
#    El esquema y los datos de ejemplo se crean con la carpeta `db/`
#    (ver db/schema.sql, db/seed.sql y db/init_db.py).
#
#  CONFIGURACIÓN DE LA CONEXIÓN:
#    Se leen variables de entorno (DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE)
#    para que cada equipo pueda usar sus propias credenciales sin modificar
#    el código. Los valores por defecto son los de una instalación local típica.
# =============================================================================

import os

import pymysql
import pymysql.cursors
from datetime import date, datetime

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA BASE DE DATOS (leo variables de entorno con valores por defecto)
# -----------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_DATABASE", "colegio"),
}


def get_db():
    """
    Crea y devuelve una conexión a MySQL (base de datos `colegio`).

    Usamos DictCursor para que cada fila devuelta sea un diccionario
    (alumno['nombre'] en lugar de alumno[0]).
    """
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def guardar_asistencia(alumno_id):
    """
    Registra la asistencia de un alumno (el id lo determinó el reconocimiento facial).

    FLUJO:
      1. Conecta a la BD.
      2. Busca al alumno por su `id` (si no existe -> error).
      3. Verifica si YA marcó asistencia HOY (la tabla tiene UNIQUE(alumno_id, fecha)).
      4. Si no marcó, calcula el estado (presente / tarde) según la hora actual.
      5. Inserta el registro en la tabla `asistencias`.
      6. Devuelve un diccionario con el resultado para que el frontend lo muestre.

    Retorna: dict con las claves usadas por el frontend
             (ok, ya_registrado, nombre, curso, estado, hora, mensaje).
    """
    # 1. Intentar conectar (si falla, devolvemos el error como JSON amigable).
    try:
        conn = get_db()
    except Exception as e:
        return {"ok": False, "mensaje": f"Error de conexión a la base de datos: {e}"}

    try:
        # 2. Buscar al alumno reconocido en la tabla `alumnos`.
        with conn.cursor() as c:
            c.execute("SELECT * FROM alumnos WHERE id = %s", (alumno_id,))
            alumno = c.fetchone()

        if not alumno:
            # Hay foto pero la matrícula no existe en la BD -> avisamos.
            return {"ok": False, "mensaje": "Alumno reconocido pero no está en la BD"}

        # 3. Verificar si ya existe una asistencia del alumno para HOY.
        with conn.cursor() as c:
            c.execute(
                "SELECT id FROM asistencias WHERE alumno_id = %s AND fecha = %s",
                (alumno_id, date.today()),
            )
            ya_marco = c.fetchone()

        if ya_marco:
            # Ya registró hoy: avisamos sin insertar nada.
            return {
                "ok": True,
                "ya_registrado": True,
                "nombre": f"{alumno['nombre']} {alumno['apellido']}",
                "mensaje": "Ya registraste asistencia hoy",
            }

        # 4. Calcular estado: "presente" antes de las 08:15, "tarde" después.
        hora_actual = datetime.now().time()
        hora_limite = datetime.strptime("08:15", "%H:%M").time()
        estado = "tarde" if hora_actual > hora_limite else "presente"

        # 5. Insertar el nuevo registro de asistencia.
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO asistencias (alumno_id, fecha, hora, estado) VALUES (%s, %s, %s, %s)",
                (alumno_id, date.today(), hora_actual, estado),
            )
        conn.commit()

        # 6. Devolver los datos para mostrar en pantalla (nombre, curso, hora...).
        return {
            "ok": True,
            "ya_registrado": False,
            "nombre": f"{alumno['nombre']} {alumno['apellido']}",
            "curso": alumno.get("curso", "N/A"),
            "estado": estado,
            "hora": hora_actual.strftime("%H:%M"),
            "mensaje": f"¡Asistencia registrada! Estado: {estado}",
        }

    except Exception as e:
        return {"ok": False, "mensaje": f"Error en la base de datos: {e}"}
    finally:
        # `finally` siempre se ejecuta: garantizamos cerrar la conexión.
        conn.close()
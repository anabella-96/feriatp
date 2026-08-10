# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/camera_module/routes.py
#
#  PROPÓSITO:
#    Define las RUTAS (endpoints) HTTP del módulo de la cámara.
#    Estas rutas las llama el JavaScript del frontend (front/js/script.js):
#
#      POST /registrar_rostro  -> guarda la foto de un alumno nuevo.
#                                  (llamado desde el botón "Registrar rostro")
#      POST /reconocer         -> identifica un rostro y registra la asistencia.
#                                  (llamado desde el botón "Registrar asistencia")
#
#  CÓMO SE CONECTA CON EL RESTO:
#    - face_service.py  -> reconocimiento facial (DeepFace) + archivos de imágenes.
#    - db_service.py    -> INSERT/SELECT en MySQL (tablas alumnos y asistencias).
# =============================================================================

import base64

from flask import Blueprint, request, jsonify

from .services.face_service import identificar_rostro, guardar_rostro
from .services.db_service import guardar_asistencia

# Creamos el Blueprint (un "grupo de rutas" que depois se registra en app.py).
camera_bp = Blueprint("camera", __name__)


@camera_bp.route("/registrar_rostro", methods=["POST"])
def registrar_rostro():
    """
    Endpoint POST /registrar_rostro

    Recibe en JSON:
        { "alumno_id": 20231045, "imagen": "data:image/jpeg;base64,..." }

    Hace:
        1. Convierte el id a entero.
        2. Decodifica la imagen base64 a bytes.
        3. Llama a guardar_rostro() que verifica el rostro, guarda la foto en
           back/imagenes_conocidas/{alumno_id}.jpg y actualiza la memoria.

    Devuelve: {"ok": bool, "mensaje": str}
    """
    # get_json(silent=True) evita una excepción si el cuerpo no es JSON.
    datos = request.get_json(silent=True)
    if not datos or "imagen" not in datos or "alumno_id" not in datos:
        return jsonify({"ok": False, "mensaje": "Faltan datos: envía imagen y alumno_id"})

    # El id del alumno debe ser un número entero (será el nombre del archivo).
    try:
        alumno_id = int(datos["alumno_id"])
    except (TypeError, ValueError):
        return jsonify({"ok": False, "mensaje": "El alumno_id debe ser un número entero"})

    # La imagen llega como data URL: "data:image/jpeg;base64,XXXX..."
    # Tomamos la parte después de la coma y la decodificamos a bytes.
    try:
        imagen_base64 = datos["imagen"].split(",")[1]
        imagen_bytes = base64.b64decode(imagen_base64)
    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error al decodificar la imagen: {e}"})

    # Delegamos la lógica al servicio (guardar + verificar rostro).
    ok, mensaje = guardar_rostro(alumno_id, imagen_bytes)
    return jsonify({"ok": ok, "mensaje": mensaje})


@camera_bp.route("/reconocer", methods=["POST"])
def reconocer():
    """
    Endpoint POST /reconocer

    Recibe en JSON:
        { "imagen": "data:image/jpeg;base64,..." }

    Hace:
        1. Decodifica la imagen.
        2. identificar_rostro() -> compara contra todos los rostros conocidos
           (DeepFace + base de embeddings en memoria).
        3. Si reconoce, guardar_asistencia() registra la asistencia en MySQL.

    Devuelve: JSON con ok / ya_registrado / nombre / curso / estado / hora.
    """
    datos = request.get_json()
    if not datos or "imagen" not in datos:
        return jsonify({"ok": False, "mensaje": "No se recibió ninguna imagen"})

    # Decodificar el base64 de la data URL a bytes de imagen.
    try:
        imagen_base64 = datos["imagen"].split(",")[1]
        imagen_bytes = base64.b64decode(imagen_base64)
    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error al decodificar la imagen: {e}"})

    # Identificar el rostro: devuelve (alumno_id, mensaje).
    alumno_id, mensaje = identificar_rostro(imagen_bytes)

    if alumno_id is None:
        # No se reconoció a nadie (o no hay rostros registrados).
        return jsonify({"ok": False, "mensaje": mensaje})

    # Rostro reconocido: registrar la asistencia del alumno en la BD.
    resultado = guardar_asistencia(alumno_id)
    return jsonify(resultado)
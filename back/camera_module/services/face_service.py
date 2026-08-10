# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/camera_module/services/face_service.py
#
#  PROPÓSITO:
#    Motor de RECONOCIMIENTO FACIAL. Todo gira alrededor de los "embeddings":
#
#      1. CARGA (cargar_rostros):
#         Cada foto en back/imagenes_conocidas/{id}.jpg se convierte en un
#         vector de 512 números (embedding con ArcFace). Eso "resume" el rostro.
#         La lista rostros_en_memoria guarda {alumno_id, embedding}.
#
#      2. GUARDADO (guardar_rostro):
#         Al registrar un rostro desde la web, verificamos que haya una cara,
#         guardamos la foto como {alumno_id}.jpg y actualizamos la memoria
#         para que funcione sin reiniciar el servidor.
#
#      3. IDENTIFICACIÓN (identificar_rostro):
#         Un nuevo rostro se convierte en embedding y se compara (distancia
#         coseno) contra todos los conocidos. Si la distancia es menor que el
#         umbral, es la misma persona.
#
#  TECNOLOGÍAS:
#    - DeepFace  -> modelo ArcFace para el embedding + RetinaFace como detector.
#    - OpenCV    -> decodificar los bytes de imagen.
#    - NumPy     -> vectores y cálculo de distancia.
# =============================================================================

import os

import numpy as np
import cv2
from deepface import DeepFace

# -----------------------------------------------------------------------------
# CONFIGURACIÓN GLOBAL
# -----------------------------------------------------------------------------
# Carpeta donde se guardan las fotos de los alumnos: back/imagenes_conocidas/
# El nombre del archivo es el id del alumno: 20231045.jpg -> alumno id 20231045.
CARPETA_IMAGENES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "imagenes_conocidas",
)

# Formatos de imagen aceptados.
EXTENSIONES_OK = {"jpg", "jpeg", "png"}

# Umbral de distancia coseno para considerar que es la misma persona.
# 0.0 = idénticos, 1.0 = totalmente distintos.
# Más bajo = más estricto; más alto = más permisivo.
UMBRAL_DISTANCIA = 0.40

# Lista en MEMORIA con los rostros conocidos:
#   [ { "alumno_id": 20231045, "embedding": np.array([512 números]) }, ... ]
rostros_en_memoria = []


# -----------------------------------------------------------------------------
# CARGA DE ROSTROS AL INICIAR
# -----------------------------------------------------------------------------
def cargar_rostros():
    """
    Lee todas las fotos de imagenes_conocidas/ y llena rostros_en_memoria.

    Se ejecuta cuando arranca el servidor (back/app.py) para que el
    reconocimiento funcione de inmediato.

    FLUJO por foto:  archivo.jpg -> RetinaFace detecta la cara
                   -> ArcFace la convierte en 512 números (embedding)
                   -> append a rostros_en_memoria
    """
    # Limpiamos la lista antes de recargar (evita duplicados al reiniciar).
    rostros_en_memoria.clear()

    if not os.path.exists(CARPETA_IMAGENES):
        print(f"⚠️ La carpeta {CARPETA_IMAGENES} no existe todavía.")
        return

    # Recorremos cada archivo de la carpeta.
    for archivo in os.listdir(CARPETA_IMAGENES):
        # Solo imágenes con extensión válida.
        ext = archivo.rsplit(".", 1)[-1].lower()
        if ext not in EXTENSIONES_OK:
            continue

        # El nombre del archivo SIN extensión debe ser el id del alumno.
        try:
            alumno_id = int(os.path.splitext(archivo)[0])
        except ValueError:
            continue  # Archivos que no se llamen como un número se ignoran.

        ruta = os.path.join(CARPETA_IMAGENES, archivo)
        try:
            # DeepFace.represent() recibe la foto y devuelve su embedding.
            resultado = DeepFace.represent(
                img_path=ruta,
                model_name="ArcFace",
                detector_backend="retinaface",
                enforce_detection=True,  # Si no hay cara, lanza excepción.
            )
            embedding = np.array(resultado[0]["embedding"])
            rostros_en_memoria.append({"alumno_id": alumno_id, "embedding": embedding})
            print(f"  ✅ alumno_id={alumno_id} cargado correctamente")
        except Exception as e:
            print(f"  ❌ Error al procesar {archivo}: {e}")

    print(f"\n📸 Total de rostros en memoria: {len(rostros_en_memoria)}\n")


# -----------------------------------------------------------------------------
# GUARDADO DE UN NUEVO ROSTRO (desde la web)
# -----------------------------------------------------------------------------
def guardar_rostro(alumno_id, imagen_bytes):
    """
    Registra el rostro de un alumno desde la cámara web.

    FLUJO:
      1. Se asegura de que exista la carpeta de imágenes.
      2. Convierte los bytes a una imagen (OpenCV).
      3. Verifica que la imagen contenga una cara y obtiene su embedding (ArcFace).
      4. Guarda la foto como back/imagenes_conocidas/{alumno_id}.jpg.
      5. Actualiza el embedding EN MEMORIA (reemplaza el anterior si existía)
         para que funcione de inmediato.

    Retorna: (ok: bool, mensaje: str)
    """
    # 1. Crear la carpeta si no existe.
    try:
        os.makedirs(CARPETA_IMAGENES, exist_ok=True)
    except Exception as e:
        return False, f"No se pudo crear la carpeta de imágenes: {e}"

    # 2-3. Decodificar y validar que haya un rostro.
    try:
        arr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "La imagen recibida no se pudo decodificar."

        # enforce_detection=True -> lanza excepción si NO hay una cara.
        resultado = DeepFace.represent(
            img_path=img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
        )
        embedding = np.array(resultado[0]["embedding"])
    except Exception as e:
        return False, f"No se detectó ningún rostro válido: {e}"

    # 4. Guardar la foto. Si ya existía, se sobrescribe con la nueva.
    ruta = os.path.join(CARPETA_IMAGENES, f"{alumno_id}.jpg")
    try:
        cv2.imwrite(ruta, img)
    except Exception as e:
        return False, f"Error al guardar la foto: {e}"

    # 5. Actualizar la lista en memoria.
    #    Quitamos cualquier entrada anterior del mismo alumno y añadimos la nueva.
    rostros_en_memoria[:] = [
        r for r in rostros_en_memoria if r["alumno_id"] != alumno_id
    ]
    rostros_en_memoria.append({"alumno_id": alumno_id, "embedding": embedding})

    print(f"  ✅ Rostro guardado: alumno_id={alumno_id} → {ruta}")
    print(f"  📸 Total de rostros en memoria: {len(rostros_en_memoria)}")
    return True, f"Rostro registrado correctamente para el alumno {alumno_id}"


# -----------------------------------------------------------------------------
# DISTANCIA COSENO (cuánto se parecen dos rostros)
# -----------------------------------------------------------------------------
def distancia_coseno(vector_a, vector_b):
    """
    Mide qué tan parecidos son dos embeddings (dos rostros).

    Resultado:
        0.0 -> vectores idénticos (misma persona, misma foto)
        0.4 -> misma persona, condiciones de luz/ángulo diferentes
        1.0 -> personas totalmente distintas
    """
    return 1 - np.dot(vector_a, vector_b) / (
        np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    )


# -----------------------------------------------------------------------------
# IDENTIFICACIÓN DE UN ROSTRO (marcar asistencia)
# -----------------------------------------------------------------------------
def identificar_rostro(imagen_bytes):
    """
    Intenta identificar a quién pertenece la cara de una imagen capturada.

    Retorna: (alumno_id: int|None, mensaje: str)
      - Si reconoce: (20231045, "ok")
      - Si no:       (None, "Rostro no reconocido (distancia=0.52)")

    FLUJO:
      bytes -> imagen (OpenCV) -> embedding de la captura (ArcFace)
           -> comparar contra TODOS los embeddings en memoria (distancia coseno)
           -> quedarse con la mejor coincidencia
           -> si está bajo el umbral, ¡es esa persona!
    """
    if not rostros_en_memoria:
        return None, "No hay rostros registrados. Registra un alumno primero."

    try:
        # Convertir bytes a imagen.
        arr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # Extraer el embedding del rostro capturado.
        resultado = DeepFace.represent(
            img_path=img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
        )
        embedding_captura = np.array(resultado[0]["embedding"])
    except Exception as e:
        return None, f"No se detectó ningún rostro en la imagen: {e}"

    # Recorrer todos los rostros conocidos y quedarse con el más parecido.
    mejor_distancia = float("inf")
    mejor_id = None

    for rostro in rostros_en_memoria:
        d = distancia_coseno(embedding_captura, rostro["embedding"])
        if d < mejor_distancia:
            mejor_distancia = d
            mejor_id = rostro["alumno_id"]

    print(f"  → Mejor coincidencia: alumno_id={mejor_id}, distancia={mejor_distancia:.4f}")

    # ¿La distancia mínima es igual o menor al umbral? -> reconocido.
    if mejor_distancia <= UMBRAL_DISTANCIA:
        return mejor_id, "ok"
    else:
        return None, (
            f"Rostro no reconocido (distancia={mejor_distancia:.3f}, umbral={UMBRAL_DISTANCIA})"
        )
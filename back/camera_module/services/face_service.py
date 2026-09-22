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
#         Al registrar un rostro desde la web, verificamos que haya una cara
#         ÚNICA y clara, y ANTES de guardar comprobamos contra TODOS los rostros
#         conocidos si esa persona ya existe (duplicado). Solo si NO hay
#         coincidencia se guarda la foto como {alumno_id}.jpg y se actualiza
#         la memoria para que funcione sin reiniciar el servidor.
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

# -----------------------------------------------------------------------------
# UMBRAL DE COINCIDENCIA (compartido por registro y reconocimiento)
# -----------------------------------------------------------------------------
# Distancia coseno entre dos embeddings. 0.0 = rostros idénticos,
# 1.0 = totalmente distintos. Si dos rostros quedan MÁS CERCANOS que este valor,
# se decide que son LA MISMA persona. Se puede ajustar desde el entorno
# (FACE_MATCH_THRESHOLD) sin tocar el código.
UMBRAL_DISTANCIA = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.40"))

# -----------------------------------------------------------------------------
# TAMAÑO MÍNIMO DEL ROSTRO (píxeles) durante el registro
# -----------------------------------------------------------------------------
# RetinaFace detecta hasta caritas diminutas del fondo (7x7 px). Para el REGISTRO
# solo contamos los rostros cuyo alto Y ancho superan este valor; los menores se
# ignoran. Así exigimos un rostro único y claro frente a la cámara. Ajustable
# con FACE_MIN_FACE_SIZE.
TAMANO_MINIMO_ROSTRO = int(os.environ.get("FACE_MIN_FACE_SIZE", "40"))

# Lista en MEMORIA con los rostros conocidos:
#   [ { "alumno_id": 20231045, "embedding": np.array([512 números]) }, ... ]
rostros_en_memoria = []


# -----------------------------------------------------------------------------
# UTILIDADES SOBRE ROSTROS DETECTADOS
# -----------------------------------------------------------------------------
def _rostro_mas_grande(resultado):
    """
    Devuelve el dict de DeepFace del rostro con MAYOR área (alto * ancho).
    Sirve para elegir el sujeto principal cuando una foto trae varias caras.
    """
    return max(resultado, key=lambda d: d["facial_area"]["w"] * d["facial_area"]["h"])


def _rostros_significativos(resultado):
    """
    Filtra los rostros detectados dejando SOLO los que superan
    TAMANO_MINIMO_ROSTRO (caras pequeñas del fondo no cuentan).
    Devuelve una lista de dicts de DeepFace.
    """
    return [
        d for d in resultado
        if d["facial_area"]["w"] >= TAMANO_MINIMO_ROSTRO
        and d["facial_area"]["h"] >= TAMANO_MINIMO_ROSTRO
    ]


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
            # Si la foto trae más de un rostro (accidente histórico), usamos el
            # MÁS GRANDE (el sujeto principal) y avisamos, sin romper la carga.
            rostro = _rostro_mas_grande(resultado)
            embedding = np.array(rostro["embedding"])
            rostros_en_memoria.append({"alumno_id": alumno_id, "embedding": embedding})
            if len(resultado) > 1:
                print(f"  ⚠️ {archivo}: {len(resultado)} rostros detectados; se usa el más grande.")
            print(f"  ✅ alumno_id={alumno_id} cargado correctamente")
        except Exception as e:
            print(f"  ❌ Error al procesar {archivo}: {e}")

    print(f"\n📸 Total de rostros en memoria: {len(rostros_en_memoria)}\n")


# -----------------------------------------------------------------------------
# GUARDADO DE UN NUEVO ROSTRO (desde la web)
# -----------------------------------------------------------------------------
def guardar_rostro(alumno_id, imagen_bytes):
    """
    Registra el rostro de un alumno desde la cámara web, SOLO si esa persona
    aún no está registrada.

    FLUJO:
      1. Se asegura de que exista la carpeta de imágenes.
      2. Convierte los bytes a una imagen (OpenCV).
      3. Verifica que haya UN SOLO rostro claro (ni cero, ni varios, ni diminuto).
      4. Extrae su embedding (ArcFace).
      5. Compara contra TODOS los rostros conocidos en memoria. Si alguno
         coincide (distancia <= UMBRAL_DISTANCIA), NO guarda y lo avisa:
         es la misma persona ya registrada, aunque la foto sea diferente.
      6. Solo si NO hay coincidencia guarda la foto como
         back/imagenes_conocidas/{alumno_id}.jpg y actualiza la memoria.

    Retorna: (ok: bool, mensaje: str, info: dict|None)
      - ok=False con info["ya_registrado"]=True  -> persona duplicada.
      - ok=False sin esa clave                     -> error de validación.
      - ok=True                                    -> registro creado.
    """
    # 1. Crear la carpeta si no existe.
    try:
        os.makedirs(CARPETA_IMAGENES, exist_ok=True)
    except Exception as e:
        return False, f"No se pudo crear la carpeta de imágenes: {e}", None

    # 2-3. Decodificar y detectar el/los rostro(s).
    try:
        arr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, "La imagen recibida no se pudo decodificar.", None

        # enforce_detection=True -> lanza excepción si NO hay ninguna cara.
        resultado = DeepFace.represent(
            img_path=img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
        )
    except Exception as e:
        return False, f"No se detectó ningún rostro válido: {e}", None

    # 4. Validar que haya UN ÚNICO rostro claro frente a la cámara.
    if not resultado:
        return False, "No se detectó ningún rostro en la imagen.", None

    significativos = _rostros_significativos(resultado)
    if not significativos:
        return False, (
            "El rostro es demasiado pequeño. Acércate a la cámara."
        ), None
    if len(significativos) > 1:
        return False, (
            "Se detectaron varios rostros. Asegúrate de que solo haya una "
            "persona frente a la cámara."
        ), None

    embedding = np.array(significativos[0]["embedding"])

    # 5. COMPARAR contra TODOS los rostros conocidos (detectar duplicados).
    existente_id, distancia = buscar_mejor_coincidencia(embedding)
    if existente_id is not None and distancia <= UMBRAL_DISTANCIA:
        print(
            f"  ⛔ Registro bloqueado: alumno_id={alumno_id} coincide con "
            f"alumno {existente_id} (distancia={distancia:.4f})"
        )
        return False, (
            f"Rostro ya registrado. Coincide con la matrícula {existente_id} "
            f"(distancia={distancia:.3f}, umbral={UMBRAL_DISTANCIA}). "
            "No se creó un nuevo registro."
        ), {
            "ya_registrado": True,
            "alumno_existente": existente_id,
            "distancia": round(float(distancia), 4),
        }

    # 6. Sin coincidencia: guardar la foto {alumno_id}.jpg y actualizar la memoria.
    ruta = os.path.join(CARPETA_IMAGENES, f"{alumno_id}.jpg")
    try:
        cv2.imwrite(ruta, img)
    except Exception as e:
        return False, f"Error al guardar la foto: {e}", None

    #    Quitamos cualquier entrada anterior del mismo alumno y añadimos la nueva.
    rostros_en_memoria[:] = [
        r for r in rostros_en_memoria if r["alumno_id"] != alumno_id
    ]
    rostros_en_memoria.append({"alumno_id": alumno_id, "embedding": embedding})

    print(f"  ✅ Rostro guardado: alumno_id={alumno_id} → {ruta}")
    print(f"  📸 Total de rostros en memoria: {len(rostros_en_memoria)}")
    return True, f"Rostro registrado correctamente para el alumno {alumno_id}", None


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


def buscar_mejor_coincidencia(embedding):
    """
    Compara un embedding contra TODOS los rostros conocidos (rostros_en_memoria)
    y devuelve el más parecido.

    Retorna: (alumno_id: int|None, distancia: float|None)
      - (20231045, 0.12) si hay rostros conocidos.
      - (None, None)     si la carpeta está vacía (aún no hay nadie registrado).
    """
    if not rostros_en_memoria:
        return None, None

    mejor_distancia = float("inf")
    mejor_id = None
    for rostro in rostros_en_memoria:
        d = distancia_coseno(embedding, rostro["embedding"])
        if d < mejor_distancia:
            mejor_distancia = d
            mejor_id = rostro["alumno_id"]
    return mejor_id, mejor_distancia


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

        # Extraer el embedding del rostro capturado. Si la imagen trajera
        # varias caras, usamos la más grande (el sujeto principal).
        resultado = DeepFace.represent(
            img_path=img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
        )
        embedding_captura = np.array(_rostro_mas_grande(resultado)["embedding"])
    except Exception as e:
        return None, f"No se detectó ningún rostro en la imagen: {e}"

    # Recorrer todos los rostros conocidos y quedarse con el más parecido.
    mejor_id, mejor_distancia = buscar_mejor_coincidencia(embedding_captura)

    print(f"  → Mejor coincidencia: alumno_id={mejor_id}, distancia={mejor_distancia:.4f}")

    # ¿La distancia mínima es igual o menor al umbral? -> reconocido.
    if mejor_distancia <= UMBRAL_DISTANCIA:
        return mejor_id, "ok"
    else:
        return None, (
            f"Rostro no reconocido (distancia={mejor_distancia:.3f}, umbral={UMBRAL_DISTANCIA})"
        )
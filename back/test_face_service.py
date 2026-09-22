# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/test_face_service.py
#
#  PROPÓSITO:
#    Pruebas de la lógica de registro de rostros y detección de duplicados
#    (back/camera_module/services/face_service.py). Cubren los casos pedidos:
#      - registrar una persona nueva                     -> se crea el registro
#      - re-registrar la MISMA foto (otro ID o el mismo) -> se rechaza (duplicado)
#      - misma persona con otra iluminación              -> se rechaza
#      - persona diferente                               -> se permite
#      - imagen sin rostro                               -> se rechaza
#      - imagen con varios rostros                       -> se rechaza
#      - rostro demasiado pequeño                        -> se rechaza
#      - archivo corrupto en imagenes_conocidas          -> no rompe la app
#      - carpeta vacía                                   -> se permite el 1º registro
#      - registrar repetidamente a la misma persona      -> solo queda 1 registro
#
#  CÓMO EJECUTAR (usa el venv del proyecto):
#      .venv\Scripts\python.exe back\test_face_service.py
#
#  NOTA: corre DeepFace (ArcFace + RetinaFace) de verdad, con los pesos ya
#  descargados (~/.deepface/weights). Puede tardar un par de minutos.
# =============================================================================

import os
import sys
import shutil
import tempfile
import unittest

import numpy as np
import cv2

# Igual que back/app.py: en consolas Windows (cp1252) los emojis del sistema
# rompen los print(); forzamos UTF-8 para que la suite no falle al imprimir.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Poder importar 'camera_module' sea cual sea el directorio desde el que se ejecute.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import camera_module.services.face_service as fs


# Cambiar solo cuando DeepFace tenga los pesos cacheados localmente.
CARPETA_FOTOS_REALES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),   # .../feriatp/back
    "imagenes_conocidas",
)

# Fotos verificadas que contienen EXACTAMENTE UN rostro (verificado con el detector).
FOTO_A = "20231087.jpg"      # persona A (cara grande 166x250)
FOTO_B = "20231113.jpg"      # persona B (cara grande 145x229)


def leer_bytes(nombre_foto):
    """Devuelve los bytes de una foto real del proyecto."""
    with open(os.path.join(CARPETA_FOTOS_REALES, nombre_foto), "rb") as f:
        return f.read()


def variar_iluminacion(bytes_imagen, delta=25):
    """Devuelve los bytes de la misma imagen con un +delta de brillo."""
    arr = np.frombuffer(bytes_imagen, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    img_brillo = np.clip(img.astype(np.int16) + delta, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img_brillo)
    if not ok:
        raise RuntimeError("No se pudo codificar la imagen con brillo modificado.")
    return buf.tobytes()


def crear_imagen_sin_rostro():
    """Genera una imagen gris uniforme (sin ningún rostro)."""
    gris = np.full((320, 240, 3), 128, np.uint8)
    ok, buf = cv2.imencode(".jpg", gris)
    return buf.tobytes()


def crear_imagen_con_dos_rostros():
    """Une lado a lado las fotos de dos personas distintas (2 rostros claros)."""
    a = cv2.imread(os.path.join(CARPETA_FOTOS_REALES, FOTO_A))
    b = cv2.imread(os.path.join(CARPETA_FOTOS_REALES, FOTO_B))
    ancho_total = a.shape[1] + b.shape[1]
    alto = max(a.shape[0], b.shape[0])
    lienzo = np.full((alto, ancho_total, 3), 0, np.uint8)
    lienzo[:a.shape[0], :a.shape[1]] = a
    lienzo[:b.shape[0], a.shape[1]:] = b
    ok, buf = cv2.imencode(".jpg", lienzo)
    return buf.tobytes()


def extraer_embedding(bytes_imagen):
    """Calcula el embedding ArcFace de una imagen (para aserciones de distancia)."""
    arr = np.frombuffer(bytes_imagen, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    resultado = fs.DeepFace.represent(
        img_path=img,
        model_name="ArcFace",
        detector_backend="retinaface",
        enforce_detection=True,
    )
    return np.array(fs._rostro_mas_grande(resultado)["embedding"])


class TestRegistroRostros(unittest.TestCase):

    def setUp(self):
        # Carpeta temporal como si fuera 'imagenes_conocidas' (sin tocar el disco real).
        self.original_carpeta = fs.CARPETA_IMAGENES
        self.original_min_tamano = fs.TAMANO_MINIMO_ROSTRO
        self.tmp = tempfile.mkdtemp(prefix="imagenes_test_")
        fs.CARPETA_IMAGENES = self.tmp
        fs.TAMANO_MINIMO_ROSTRO = 40
        fs.rostros_en_memoria.clear()

    def tearDown(self):
        fs.CARPETA_IMAGENES = self.original_carpeta
        fs.TAMANO_MINIMO_ROSTRO = self.original_min_tamano
        fs.rostros_en_memoria.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def existe_foto(self, alumno_id):
        return os.path.exists(os.path.join(self.tmp, f"{alumno_id}.jpg"))

    # ------------------------------------------------------------------
    # 1) Carrera principal
    # ------------------------------------------------------------------
    def test_carpeta_vacia_permite_registrar_la_primera_persona(self):
        ok, mensaje, info = fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        self.assertTrue(ok, mensaje)
        self.assertTrue(self.existe_foto(9001))
        self.assertEqual(len(fs.rostros_en_memoria), 1)

    def test_misma_foto_con_otro_id_se_rechaza_como_duplicado(self):
        ok, men, info = fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        self.assertTrue(ok)
        # Mismo rostro, ID distinto -> NO debe crearse otro registro.
        ok2, men2, info2 = fs.guardar_rostro(9002, leer_bytes(FOTO_A))
        self.assertFalse(ok2)
        self.assertIn("ya registrado", men2.lower())
        self.assertTrue(info2["ya_registrado"])
        self.assertEqual(info2["alumno_existente"], 9001)
        self.assertFalse(self.existe_foto(9002))
        self.assertEqual(len(fs.rostros_en_memoria), 1)

    def test_reintentar_el_mismo_id_se_rechaza(self):
        fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        ok2, men2, info2 = fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        self.assertFalse(ok2)
        self.assertIn("ya registrado", men2.lower())
        self.assertTrue(info2["ya_registrado"])

    def test_misma_persona_con_otra_iluminacion_se_rechaza(self):
        original = leer_bytes(FOTO_A)
        con_luz = variar_iluminacion(original, delta=25)
        fs.guardar_rostro(9001, original)

        # Sanidad: para el modelo, la foto con otra luz sigue siendo la misma persona.
        distancia = fs.distancia_coseno(
            extraer_embedding(con_luz),
            fs.rostros_en_memoria[0]["embedding"],
        )
        self.assertLess(distancia, fs.UMBRAL_DISTANCIA,
                        f"La variación de luz dejó de ser la misma persona (d={distancia:.3f})")

        ok2, men2, info2 = fs.guardar_rostro(9002, con_luz)
        self.assertFalse(ok2, "Un segundo registro de la misma persona debe rechazarse")
        self.assertTrue(info2["ya_registrado"])
        self.assertFalse(self.existe_foto(9002))

    def test_persona_diferente_si_se_permite(self):
        fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        # Sanidad: son dos personas distintas para el modelo.
        distancia = fs.distancia_coseno(
            extraer_embedding(leer_bytes(FOTO_B)),
            fs.rostros_en_memoria[0]["embedding"],
        )
        self.assertGreater(distancia, fs.UMBRAL_DISTANCIA,
                           f"Se esperaban dos personas distintas (d={distancia:.3f})")

        ok, men, info = fs.guardar_rostro(9002, leer_bytes(FOTO_B))
        self.assertTrue(ok, men)
        self.assertTrue(self.existe_foto(9002))
        self.assertEqual(len(fs.rostros_en_memoria), 2)

    def test_registrar_repetidamente_la_misma_persona_no_duplica(self):
        fs.guardar_rostro(9001, leer_bytes(FOTO_A))
        for intento in range(3):
            fs.guardar_rostro(9100 + intento, leer_bytes(FOTO_A))
        self.assertEqual(len(fs.rostros_en_memoria), 1)
        # Solo debe existir una foto del rostro A en toda la carpeta.
        fotos = [f for f in os.listdir(self.tmp) if f.lower().endswith(".jpg")]
        self.assertEqual(fotos, ["9001.jpg"])

    # ------------------------------------------------------------------
    # 2) Validación de la imagen
    # ------------------------------------------------------------------
    def test_imagen_sin_rostro_se_rechaza(self):
        ok, men, info = fs.guardar_rostro(9201, crear_imagen_sin_rostro())
        self.assertFalse(ok)
        self.assertIn("rostro", men.lower())
        self.assertFalse(self.existe_foto(9201))

    def test_imagen_con_varios_rostros_se_rechaza(self):
        ok, men, info = fs.guardar_rostro(9202, crear_imagen_con_dos_rostros())
        self.assertFalse(ok)
        self.assertIn("varios", men.lower())
        self.assertFalse(self.existe_foto(9202))

    def test_rostro_demasiado_pequeno_se_rechaza(self):
        # Subimos el umbral mínimo a un valor absurdo para forzar el caso.
        fs.TAMANO_MINIMO_ROSTRO = 1_000_000
        ok, men, info = fs.guardar_rostro(9203, leer_bytes(FOTO_A))
        self.assertFalse(ok)
        self.assertIn("pequeño", men.lower())
        self.assertFalse(self.existe_foto(9203))

    # ------------------------------------------------------------------
    # 3) Robustez ante archivos problemáticos
    # ------------------------------------------------------------------
    def test_archivo_corrupto_en_carpeta_no_rompe_la_carga(self):
        # Foto válida + un archivo corrupto y otro que no es imagen.
        shutil.copy(
            os.path.join(CARPETA_FOTOS_REALES, FOTO_A),
            os.path.join(self.tmp, "7001.jpg"),
        )
        with open(os.path.join(self.tmp, "7002.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff" + os.urandom(64))  # basura
        with open(os.path.join(self.tmp, "leeme.txt"), "w") as f:
            f.write("no soy una foto")

        # No debe lanzar excepción ni terminar la app.
        fs.cargar_rostros()
        ids = [r["alumno_id"] for r in fs.rostros_en_memoria]
        self.assertIn(7001, ids)
        self.assertEqual(len(fs.rostros_en_memoria), 1)

    def test_bytes_de_imagen_corrupta_en_registro_se_rechazan(self):
        ok, men, info = fs.guardar_rostro(9204, b"\xff\xd8\xffbasura-no-es-una-foto")
        self.assertFalse(ok)
        self.assertFalse(self.existe_foto(9204))


if __name__ == "__main__":
    unittest.main(verbosity=2)
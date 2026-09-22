# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/test_gestion_sin_rostro.py
#
#  PROPÓSITO:
#    Prueba la lógica del "ID automático" del registro de rostros:
#      - _tiene_foto_rostro() (back/gestion_module/routes.py)
#      - la ruta GET /api/estudiantes/sin_rostro queda registrada en la app.
#
#  CÓMO EJECUTAR (usa el venv del proyecto):
#      .venv\Scripts\python.exe back\test_gestion_sin_rostro.py
# =============================================================================

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gestion_module.routes as gr


class TestAlumnosSinRostro(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sin_rostro_")
        self.original_carpeta = gr.CARPETA_FOTOS
        gr.CARPETA_FOTOS = self.tmp

    def tearDown(self):
        gr.CARPETA_FOTOS = self.original_carpeta
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_alumno_con_foto_jpg_si_tiene_rostro(self):
        open(os.path.join(self.tmp, "20231045.jpg"), "wb").close()
        self.assertTrue(gr._tiene_foto_rostro(20231045))

    def test_alumno_con_foto_png_si_tiene_rostro(self):
        open(os.path.join(self.tmp, "20231045.png"), "wb").close()
        self.assertTrue(gr._tiene_foto_rostro(20231045))

    def test_alumno_sin_foto_no_tiene_rostro(self):
        self.assertFalse(gr._tiene_foto_rostro(20231045))

    def test_archivo_que_no_es_foto_no_cuenta(self):
        open(os.path.join(self.tmp, "20231045.txt"), "wb").close()
        self.assertFalse(gr._tiene_foto_rostro(20231045))

    def test_ruta_sin_rostro_registrada_en_la_app(self):
        from app import create_app
        app = create_app()
        reglas = {str(r.rule) for r in app.url_map.iter_rules()}
        self.assertIn("/api/estudiantes/sin_rostro", reglas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
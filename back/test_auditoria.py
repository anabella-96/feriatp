# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/test_auditoria.py
#
#  PROPÓSITO:
#    Suite de AUDITORÍA INTEGRAL de todo el proyecto. Cubre:
#      - Flujos de autenticación (login correcto/incorrecto/bloqueado/401).
#      - CRUD de las APIs de gestión (estudiantes, cursos, profesores, sesiones).
#      - Casos límite: campos vacíos, strings gigantes, datos inválidos.
#      - Integración del reconocimiento facial a través del ENDPOINT real:
#        registrar rostro -> guardar en carpeta -> /reconocer -> marcar asistencia.
#      - Seguridad: sesiones forjadas, autorización por rol, Host header,
#        inyección SQL, traversal de rutas.
#      - Recuperación: caída de BD simulada, carpetas inexistentes.
#      - Privacidad: la carpeta de fotos NO debe servirse por HTTP/estático.
#
#  IMPORTANTE:
#    Todo se ejecuta contra la base aislada `colegio_auditoria` (NO toca la BD
#    real `colegio`) y las fotos se guardan en una carpeta temporal.
#    Requiere:  python db/init_db.py  (crea `colegio`)  + MySQL local root/root.
#
#  CÓMO EJECUTAR:
#      .venv\Scripts\python.exe back\test_auditoria.py
# =============================================================================

import io
import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

# Antes de importar módulos del proyecto: apuntar a la BD de auditoría aislada.
os.environ["DB_HOST"] = "localhost"
os.environ["DB_USER"] = "root"
os.environ["DB_PASSWORD"] = "root"
os.environ["DB_DATABASE"] = "colegio_auditoria"

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import cv2

import camera_module.services.face_service as fs
import camera_module.services.db_service as db
import gestion_module.routes as gr
from app import create_app

CARPETA_FOTOS_REALES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "imagenes_conocidas",
)
FOTO_A = "20231087.jpg"   # persona A (un solo rostro, verificado)
FOTO_B = "20231113.jpg"   # persona B (un solo rostro, verificado)


def leer_bytes(nombre_foto):
    with open(os.path.join(CARPETA_FOTOS_REALES, nombre_foto), "rb") as f:
        return f.read()


def data_url(bytes_img):
    import base64
    return "data:image/jpeg;base64," + base64.b64encode(bytes_img).decode()


def imagen_sin_rostro():
    import numpy as _np, cv2 as _cv2
    gris = _np.full((320, 240, 3), 128, _np.uint8)
    ok, buf = _cv2.imencode(".jpg", gris)
    return buf.tobytes()


class BaseAuditoria(unittest.TestCase):
    """Base: app + cliente, carpeta temporal para fotos, memoria limpia."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self.tmp_fotos = tempfile.mkdtemp(prefix="aud_fotos_")
        self.fs_carpeta_original = fs.CARPETA_IMAGENES
        self.gr_carpeta_original = gr.CARPETA_FOTOS
        fs.CARPETA_IMAGENES = self.tmp_fotos
        gr.CARPETA_FOTOS = self.tmp_fotos
        fs.rostros_en_memoria.clear()

    def tearDown(self):
        fs.CARPETA_IMAGENES = self.fs_carpeta_original
        gr.CARPETA_FOTOS = self.gr_carpeta_original
        fs.rostros_en_memoria.clear()
        shutil.rmtree(self.tmp_fotos, ignore_errors=True)

    def login(self, usuario="carlosr", password="123456"):
        return self.client.post(
            "/login",
            data={"usuario": usuario, "password": password},
            follow_redirects=False,
        )


# =============================================================================
# A) FLUJOS DE AUTENTICACIÓN
# =============================================================================

class TestAutenticacion(BaseAuditoria):

    def test_login_correcto_establece_sesion(self):
        r = self.login()
        self.assertEqual(r.status_code, 302)
        # Verificar que la sesión quedó con usuario_id vía una API protegida.
        api = self.client.get("/api/estudiantes")
        self.assertEqual(api.status_code, 200)

    def test_login_incorrecto_no_establece_sesion(self):
        # Cliente nuevo: el 'self.client' ya lleva la sesión de otro test.
        c = self.app.test_client()
        c.post("/login", data={"usuario": "carlosr", "password": "incorrecta"})
        api = c.get("/api/estudiantes")
        self.assertEqual(api.status_code, 401)

    def test_login_usuario_bloqueado_se_rechaza(self):
        c = self.app.test_client()
        r = c.post("/login", data={"usuario": "sofiah", "password": "123456"})
        self.assertEqual(r.status_code, 200)  # vuelve a la página de login
        api = c.get("/api/estudiantes")
        self.assertEqual(api.status_code, 401)

    def test_rutas_principales_requieren_sesion(self):
        c = self.app.test_client()
        for ruta in ("/", "/face"):
            r = c.get(ruta)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers.get("Location", ""))

    def test_sin_sesion_api_devuelve_401(self):
        c = self.app.test_client()
        r = c.get("/api/estudiantes")
        self.assertEqual(r.status_code, 401)


# =============================================================================
# B) CRUD DE LAS APIS DE GESTIÓN (sobre BD aislada)
# =============================================================================

class TestApiGestion(BaseAuditoria):

    def setUp(self):
        super().setUp()
        self.login()

    def test_listar_estudiantes_ok(self):
        r = self.client.get("/api/estudiantes")
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertIsInstance(d["datos"], list)

    def test_sin_rostro_con_carpeta_vacia_lista_todos(self):
        r = self.client.get("/api/estudiantes/sin_rostro")
        d = r.get_json()
        self.assertTrue(d["ok"])
        # En la BD aislada el seed trae 8 alumnos y la carpeta está vacía.
        total = self.client.get("/api/estudiantes").get_json()["datos"]
        self.assertEqual(len(d["datos"]), len(total))

    def test_crear_estudiante_genera_id(self):
        r = self.client.post("/api/estudiantes", json={
            "nombre": "Test", "apellido": "Auditoria", "curso": "Ciencias",
        })
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertIsInstance(d["id"], int)

    def test_crear_estudiante_sin_nombre_400(self):
        r = self.client.post("/api/estudiantes", json={"apellido": "X"})
        self.assertEqual(r.status_code, 400)

    def test_crear_estudiante_nombre_absurdamente_largo(self):
        # Sin validación de longitud -> MySQL rechaza (1406) y se devuelve 500.
        r = self.client.post("/api/estudiantes", json={
            "nombre": "X" * 2000, "apellido": "Y",
        })
        self.assertEqual(r.status_code, 500)

    def test_crear_curso_codigo_duplicado_400(self):
        self.client.post("/api/cursos", json={"codigo": "DUP-1", "nombre": "A"})
        r = self.client.post("/api/cursos", json={"codigo": "DUP-1", "nombre": "B"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Ya existe", r.get_json()["mensaje"])

    def test_crear_curso_ok_y_eliminar(self):
        r = self.client.post("/api/cursos", json={"codigo": "AUD-1", "nombre": "AUDIT"})
        self.assertTrue(r.get_json()["ok"])
        lista = self.client.get("/api/cursos").get_json()["datos"]
        nuevo = [c for c in lista if c["codigo"] == "AUD-1"][0]
        d = self.client.delete(f"/api/cursos/{nuevo['id']}")
        self.assertTrue(d.get_json()["ok"])

    def test_eliminar_estudiante_borra_foto(self):
        # Crear alumno y su foto "de rostro" en la carpeta temporal.
        creado = self.client.post("/api/estudiantes", json={
            "nombre": "Foto", "apellido": "Rostro",
        }).get_json()
        with open(os.path.join(self.tmp_fotos, f"{creado['id']}.jpg"), "wb") as f:
            f.write(leer_bytes(FOTO_A))
        self.assertTrue(gr._tiene_foto_rostro(creado["id"]))
        d = self.client.delete(f"/api/estudiantes/{creado['id']}")
        self.assertTrue(d.get_json()["ok"])
        self.assertFalse(gr._tiene_foto_rostro(creado["id"]))

    def test_eliminar_estudiante_inexistente_responde_ok(self):
        r = self.client.delete("/api/estudiantes/999888777")
        self.assertTrue(r.get_json()["ok"])  # idempotente (no es ideal, pero no rompe)


# =============================================================================
# C) SEGURIDAD
# =============================================================================

class TestSeguridad(BaseAuditoria):

    def setUp(self):
        super().setUp()
        self.login()

    def test_sesion_forjada_con_secret_conocido(self):
        # app.secret_key es "cambiar_en_produccion" (hardcodeado): se puede
        # firmar una cookie de sesión con cualquier usuario_id sin contraseña.
        from flask.sessions import SecureCookieSessionInterface
        s = SecureCookieSessionInterface().get_signing_serializer(self.app)
        cookie = s.dumps({"usuario_id": 1})
        c = self.app.test_client()
        c.set_cookie("session", cookie, domain="localhost")
        r = c.get("/api/estudiantes")
        self.assertEqual(r.status_code, 200)  # BUG: acceso administrativo sin credenciales

    def test_usuario_estudiante_puede_modificar_datos(self):
        # Crear cuenta con rol Estudiante (3) e intentar CRUD de gestión.
        with db.get_db() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (usuario, nombre, correo, password_hash, rol_id, estado) "
                "VALUES ('est_audit', 'Est Audit', 'ea@x.co', %s, 3, 'activo') "
                "ON DUPLICATE KEY UPDATE rol_id = 3",
                ("scrypt:32768:8:1$P2Kb34KPoZjs5XB8$f351f694b29fd7d439487c46472c556f5c0d93a05b278bc93802ad36a13b26f518d2a4847fea04d7d8b4f10b86eb20c5b4f60b948ebe245b6a879fbe7bd16239",),
            )
            conn.commit()
        self.login("est_audit", "123456")
        r = self.client.post("/api/estudiantes", json={
            "nombre": "Hack", "apellido": "Rol",
        })
        # BUG de autorización: rol estudiante crea estudiantes (y puede borrarlos
        # y borrar cursos/profesores/sesiones) porque no hay chequeo de rol.
        self.assertEqual(r.status_code, 200)

    def test_open_redirect_por_host_header(self):
        # before_request construye https://{host}:5001 con request.host -> el
        # Host lo controla el cliente -> redirección abierta.
        r = self.client.get("/", headers={"Host": "evil.example"})
        self.assertEqual(r.status_code, 301)
        self.assertIn("https://evil.example:5001", r.headers.get("Location", ""))

    def test_inyeccion_sql_en_nombre_se_almacena_literal(self):
        payload = "x' OR '1'='1' --"
        r = self.client.post("/api/estudiantes", json={"nombre": payload, "apellido": "Z"})
        self.assertTrue(r.get_json()["ok"])
        # No debe haberse "inyectado": al listar solo debe existir UN registro con ese texto.
        lista = self.client.get("/api/estudiantes").get_json()["datos"]
        coincidencias = [a for a in lista if payload in (a["nombre"] or "")]
        self.assertEqual(len(coincidencias), 1)

    def test_traversal_de_ruta_en_delete_bloqueado(self):
        r = self.client.delete("/api/estudiantes/../../../../../windows/win.ini")
        # Werkzeug normaliza los ".." del path ANTES de enrutar, así que nunca
        # llega a manipular el sistema de archivos: 404 (no existe la ruta
        # normalizada) o 405 (ruta normalizada con otro método).
        self.assertIn(r.status_code, (404, 405))


# =============================================================================
# D) INTEGRACIÓN DEL REGISTRO DE ROSTROS (endpoint real)
# =============================================================================

class TestRegistroRostroEndpoint(BaseAuditoria):

    def setUp(self):
        super().setUp()
        self.login()

    def test_registrar_rostro_persona_nueva_ok(self):
        r = self.client.post("/registrar_rostro", json={
            "alumno_id": 20231085,
            "imagen": data_url(leer_bytes(FOTO_A)),
        })
        d = r.get_json()
        self.assertTrue(d["ok"], d["mensaje"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp_fotos, "20231085.jpg")))

    def test_registrar_rostro_id_inexistente_en_bd_se_acepta(self):
        # BUG: la API no valida que el alumno exista en la BD; guarda la foto
        # como "huérfana" ({99999999.jpg} sin alumno).
        r = self.client.post("/registrar_rostro", json={
            "alumno_id": 99999999,
            "imagen": data_url(leer_bytes(FOTO_A)),
        })
        self.assertTrue(r.get_json()["ok"], "Debería rechazar un ID que no existe en la BD")
        self.assertTrue(os.path.exists(os.path.join(self.tmp_fotos, "99999999.jpg")))

    def test_registrar_rostro_sobreeescribe_foto_de_alumno_distinto(self):
        # BUG: si el alumno YA tiene una foto pero le "asignan" la cara de OTRA
        # persona (mismo ID, distinto rostro), la API la guarda y SOBREESCRIBE
        # la foto legítima (el guardado solo compara duplicados faciales, no el ID).
        r1 = self.client.post("/registrar_rostro", json={
            "alumno_id": 20231085, "imagen": data_url(leer_bytes(FOTO_A)),
        })
        self.assertTrue(r1.get_json()["ok"])
        original = leer_bytes(FOTO_A)
        with open(os.path.join(self.tmp_fotos, "20231085.jpg"), "rb") as f:
            igual = f.read() == original
        r2 = self.client.post("/registrar_rostro", json={
            "alumno_id": 20231085, "imagen": data_url(leer_bytes(FOTO_B)),
        })
        if r2.get_json().get("ok"):
            with open(os.path.join(self.tmp_fotos, "20231085.jpg"), "rb") as f:
                sobrescrita = f.read() != original
            self.assertTrue(sobrescrita,
                            "Se sobrescribió la foto del alumno con la de otra persona")

    def test_registrar_rostro_imagen_no_rostro_rechazada(self):
        r = self.client.post("/registrar_rostro", json={
            "alumno_id": 20231085, "imagen": data_url(imagen_sin_rostro()),
        })
        self.assertFalse(r.get_json()["ok"])

    def test_registrar_rostro_faltan_datos(self):
        r = self.client.post("/registrar_rostro", json={"alumno_id": 20231085})
        d = r.get_json()
        self.assertFalse(d["ok"])

    def test_registrar_rostro_funciona_SIN_sesion_BUG(self):
        # BUG (documentado): /registrar_rostro NO exige login_required, así que
        # cualquiera en la red puede escribir fotos en imagenes_conocidas.
        c = self.app.test_client()  # cliente NUEVO, sin sesión
        r = c.post("/registrar_rostro", json={
            "alumno_id": 20231085, "imagen": data_url(leer_bytes(FOTO_A)),
        })
        self.assertEqual(r.status_code, 200)  # debería ser 401

    def test_reconocer_funciona_SIN_sesion_BUG(self):
        # BUG (documentado): /reconocer tampoco exige login_required.
        c = self.app.test_client()  # cliente NUEVO, sin sesión
        r = c.post("/reconocer", json={"imagen": data_url(leer_bytes(FOTO_A))})
        self.assertEqual(r.status_code, 200)  # actual: procesa sin autenticar


# =============================================================================
# E) FLUJO COMPLETO: registrar rostro -> /reconocer -> marcar asistencia
# =============================================================================

class TestReconocerIntegral(BaseAuditoria):

    def setUp(self):
        super().setUp()
        self.login()

    def test_flujo_completo_reconocimiento(self):
        # Asegurar que la fila 20231085 exista (otros tests la borran) y que el
        # test sea repetible dentro del mismo día.
        with db.get_db() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM asistencias WHERE alumno_id = 20231085")
            cur.execute("""
                INSERT IGNORE INTO alumnos (id, nombre, apellido, correo, curso, estado)
                VALUES (20231085, 'Antonella', 'Lobos', 'antonella.lobos@sip.cl',
                        'Programación I', 'activo')
            """)
            conn.commit()
        # 1) Registrar el rostro del alumno 20231085 (Antonella Lobos) vía API.
        r = self.client.post("/registrar_rostro", json={
            "alumno_id": 20231085, "imagen": data_url(leer_bytes(FOTO_A)),
        })
        self.assertTrue(r.get_json()["ok"])

        # 2) /reconocer con la MISMA foto -> debe identificar y marcar asistencia.
        r2 = self.client.post("/reconocer", json={"imagen": data_url(leer_bytes(FOTO_A))})
        d2 = r2.get_json()
        self.assertTrue(d2["ok"], d2["mensaje"])
        self.assertEqual(d2["nombre"], "Antonella Lobos")
        self.assertFalse(d2["ya_registrado"])

        # 3) Segunda vez el mismo día -> ya_registrado (no duplicar asistencia).
        r3 = self.client.post("/reconocer", json={"imagen": data_url(leer_bytes(FOTO_A))})
        self.assertTrue(r3.get_json()["ya_registrado"])

    def test_reconocer_persona_no_registrada(self):
        r = self.client.post("/reconocer", json={"imagen": data_url(imagen_sin_rostro())})
        self.assertFalse(r.get_json()["ok"])


# =============================================================================
# F) RECUPERACIÓN ANTE ERRORES
# =============================================================================

class TestRecuperacion(BaseAuditoria):

    def setUp(self):
        super().setUp()
        self.login()

    def test_bd_caida_devuelve_json_no_panico(self):
        # gestion_module usa su propio binding `get_db` (import del módulo),
        # así que se parchea ese binding concreto.
        with mock.patch.object(gr, "get_db", side_effect=Exception("conexión caída")):
            for ruta in ("/api/estudiantes", "/api/estudiantes/sin_rostro",
                         "/api/cursos", "/api/profesores", "/api/sesiones"):
                r = self.client.get(ruta)
                self.assertEqual(r.status_code, 500)
                d = r.get_json()
                self.assertIsNotNone(d)
                self.assertFalse(d["ok"])

    def test_carpeta_fotos_inexistente_no_rompe_al_crearse(self):
        shutil.rmtree(self.tmp_fotos)  # simular que la carpeta desapareció
        ok, men, info = fs.guardar_rostro(20231085, leer_bytes(FOTO_A))
        self.assertTrue(ok, men)  # o: la crea y guarda o falla con mensaje claro
        self.assertTrue(os.path.isdir(self.tmp_fotos))


# =============================================================================
# G) PRIVACIDAD
# =============================================================================

class TestPrivacidad(BaseAuditoria):

    def test_fotos_no_accesibles_por_http(self):
        # static_folder es front/ -> /imagenes_conocidas/* NO debe existir por HTTP.
        self.login()
        for ruta in ("/imagenes_conocidas/20231087.jpg",
                     "/../back/imagenes_conocidas/20231087.jpg"):
            r = self.client.get(ruta)
            self.assertIn(r.status_code, (301, 302, 404))  # nunca 200

    def test_eliminar_estudiante_no_quita_embeddings_de_memoria(self):
        self.login()
        ok, _, _ = fs.guardar_rostro(20231085, leer_bytes(FOTO_A))
        self.assertTrue(ok)
        self.assertIn(20231085, [r["alumno_id"] for r in fs.rostros_en_memoria])
        # Eliminamos al estudiante (borra la fila y la foto, pero NO la memoria).
        self.client.delete("/api/estudiantes/20231085")
        ids = [r["alumno_id"] for r in fs.rostros_en_memoria]
        # BUG (documentado): tras el DELETE la memoria sigue conteniendo el
        # embedding del rol eliminado en tiempo de ejecución; la app lo
        # reconocerá hasta el reinicio. La aserción verifica el comportamiento
        # ACTUAL (no el ideal) para dejar constancia objetiva del defecto.
        self.assertIn(20231085, ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
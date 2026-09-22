# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/app.py
#
#  PROPÓSITO:
#    Punto de entrada del servidor web (Flask). Arma la aplicación,
#    registra las rutas del módulo de la cámara y sirve el frontend.
#
#  ESTRUCTURA DE CARPETAS QUE USA:
#      feriatp/
#        ├─ back/app.py                 <- este archivo (servidor)
#        ├─ back/camera_module/         <- lógica de cámara y reconocimiento facial
#        ├─ back/imagenes_conocidas/    <- fotos de rostros: {id_alumno}.jpg
#        ├─ front/templates/            <- páginas HTML (index.html + secciones)
#        ├─ front/css/ y front/js/      <- estilos y JavaScript del frontend
#        └─ db/                         <- scripts para crear la base de datos
#
#  CÓMO EJECUTAR:
#      python back/app.py        (o doble clic en start.bat)
#      Luego abre:  http://localhost:5000
# =============================================================================

import os
import threading

from flask import Flask, redirect, render_template, request
from werkzeug.serving import run_simple

from camera_module.routes import camera_bp
from camera_module.services.face_service import cargar_rostros
from auth_module.routes import auth_bp, login_required, usuario_actual
from gestion_module.routes import gestion_bp
from ssl_utils import ensure_certificate


def create_app():
    """
    Fábrica de la aplicación Flask (patrón "Application Factory").

    Es una función (no código suelto) para poder crear varias instancias
    y para poder testearla fácilmente con un test client.
    """
    # 1. Ruta absoluta del directorio raíz del proyecto ('feriatp').
    #    __file__ = .../feriatp/back/app.py
    #    1er dirname -> .../feriatp/back
    #    2º dirname -> .../feriatp   <-- la raíz del proyecto
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 2. Carpetas del frontend dentro de la raíz.
    front_dir = os.path.join(base_dir, "front")
    templates_dir = os.path.join(front_dir, "templates")

    # 3. Creamos Flask:
    #    - template_folder=templates_dir  -> busca index.html y las secciones
    #    - static_folder=front_dir        -> sirve los archivos estáticos
    #    - static_url_path=""             -> rutas limpias: /css/style.css, /js/script.js
    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=front_dir,
        static_url_path="",
    )

    # Clave secreta (necesaria para sesiones/Flash de Flask).
    # En producción debes cambiarla por una clave segura.
    app.secret_key = "cambiar_en_produccion"

    # Cachear los archivos estáticos (css, js, fuentes, imágenes) durante 30 días.
    # Así el navegador NO los vuelve a descargar en cada visita y la app abre mucho
    # más rápido (los cambios de contenido se sirven sin caché por separado).
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30

    # -----------------------------------------------------------------------------
    # REDIRECCIÓN HTTP -> HTTPS (clave para que la CÁMARA funcione).
    #
    # El navegador SOLO permite la cámara (getUserMedia) en "contexto seguro"
    # (localhost o https://). Si un dispositivo de la red entra con
    # http://192.168.1.X:5000, la API de cámara no existe y salta el error
    # "debes ingresar por una ruta segura".
    #
    # Solución: cualquier petición HTTP hecha desde OTRO dispositivo de la red
    # se redirige automáticamente a https://IP:5001 (donde sí funciona la cámara).
    # localhost y 127.0.0.1 se dejan en HTTP porque ahí la cámara ya funciona.
    # -----------------------------------------------------------------------------
    @app.before_request
    def redirigir_a_https():
        if request.scheme == "https":
            return None
        host = request.host.split(":")[0]
        if host in ("localhost", "127.0.0.1"):
            return None
        destino = f"https://{host}:5001{request.full_path}"
        # 301 para GET (normal); 308 para POST/PUT/etc. (conserva método y cuerpo).
        codigo = 301 if request.method in ("GET", "HEAD") else 308
        return redirect(destino, code=codigo)

    # 4. Registrar los blueprints:
    #    - auth_bp     -> rutas de login/registro/logout (back/auth_module/routes.py)
    #    - camera_bp   -> POST /reconocer y POST /registrar_rostro (cámara)
    #    - gestion_bp  -> /api/estudiantes, /api/cursos, /api/profesores, /api/sesiones
    app.register_blueprint(auth_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(gestion_bp)

    # 5. Página principal: carga el dashboard completo (index.html incluye
    #    todas las secciones: Inicio, Dashboard, Asistencia, Reportes, etc.).
    #    Solo accesible con sesión iniciada (login_required); redirige a /login.
    @app.route("/")
    @app.route("/face")  # Alias para no romper enlaces antiguos.
    @login_required
    def index():
        """Página principal que carga la interfaz con la cámara."""
        return render_template("index.html", usuario=usuario_actual())

    return app


# -----------------------------------------------------------------------------
# Solo se ejecuta cuando corremos ESTE archivo directamente:  python back/app.py
# Si lo importamos desde otro lugar (p.ej. un test), no arranca el servidor.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # Los mensajes del sistema (#, emojis) usan UTF-8; en consolas Windows
    # (cp1252) imprimirlos lanzaba UnicodeEncodeError y mataba el servidor.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    app = create_app()

    # Cargar en memoria los embeddings de todos los rostros que ya estén
    # guardados en back/imagenes_conocidas/ (para que el reconocimiento
    # funcione apenas arranca el servidor).
    print("Iniciando carga de rostros...")
    cargar_rostros()

    # Certificado autofirmado para HTTPS. Es lo que permite usar la cámara
    # desde OTROS dispositivos de la red (el navegador exige contexto seguro).
    cert_pem, key_pem = ensure_certificate()
    print("Certificado SSL listo:", cert_pem)

    def servir_http():
        # HTTP: funciona en este equipo vía localhost (contexto seguro).
        # Las visitas desde OTROS dispositivos se redirigen solas a HTTPS
        # (before_request) para que la cámara funcione sin errores.
        run_simple("0.0.0.0", 5000, app, threaded=True)

    def servir_https():
        # HTTPS: permite la cámara desde cualquier dispositivo de la red.
        run_simple(
            "0.0.0.0", 5001, app,
            ssl_context=(cert_pem, key_pem),
            threaded=True,
        )

    print("=" * 60)
    print(" Servidor iniciado. Abre en tu navegador:")
    print("   En este equipo  ->  http://localhost:5000   (cámara OK)")
    print("   Otros dispositivos de la red -> http://192.168.1.X:5000")
    print("   (se reenvían solos a https://192.168.1.X:5001 para activar la cámara)")
    print("=" * 60)

    # HTTPS en un hilo aparte + HTTP principal en este hilo.
    hilo_https = threading.Thread(target=servir_https, daemon=True)
    hilo_https.start()
    servir_http()
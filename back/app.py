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

from flask import Flask, render_template

from camera_module.routes import camera_bp
from camera_module.services.face_service import cargar_rostros
from auth_module.routes import auth_bp, login_required, usuario_actual
from gestion_module.routes import gestion_bp


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
    app = create_app()

    # Cargar en memoria los embeddings de todos los rostros que ya estén
    # guardados en back/imagenes_conocidas/ (para que el reconocimiento
    # funcione apenas arranca el servidor).
    print("Iniciando carga de rostros...")
    cargar_rostros()

    print("Servidor iniciado. Accede a http://localhost:5000")
    # host 0.0.0.0 -> accesible desde la red local; debug=True -> recarga automática.
    app.run(host="0.0.0.0", port=5000, debug=True)
# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: back/auth_module/routes.py
#
#  PROPÓSITO:
#    Maneja la AUTENTICACIÓN del sistema: iniciar sesión, registrarse y cerrar
#    sesión. También expone el decorador `login_required` que protege las
#    demás rutas (el dashboard y las APIs solo funcionan logueado).
#
#  FLUJO DE LOGIN:
#      front/templates/login.html  --POST /login-->  auth_module/routes.py
#        (form: usuario + contraseña)      (valida contra la tabla `usuarios`
#                                           usando werkzeug.check_password_hash)
#
#  SESIÓN:
#    Al loguearse se guarda session['usuario_id']. Flask firma la cookie con
#    app.secret_key, así que el usuario no puede falsificar su sesión.
# =============================================================================

import functools

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from camera_module.services.db_service import get_db

# Blueprint con las rutas de autenticación (login, registro, logout).
auth_bp = Blueprint("auth", __name__)


# -----------------------------------------------------------------------------
# DECORADOR: protege una ruta (solo se puede acceder estando logueado)
# -----------------------------------------------------------------------------
def login_required(vista):
    """
    Decorador que envuelve una ruta para exigir sesión iniciada.

    Si NO hay sesión:
        - Peticiones API (que esperan JSON) -> responde HTTP 401.
        - Peticiones de página (navegador)  -> redirige a /login.
    """
    @functools.wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            if request.path.startswith("/api/"):
                return (
                    {
                        "ok": False,
                        "mensaje": "No autenticado. Inicia sesión para continuar.",
                    },
                    401,
                )
            return redirect(url_for("auth.login"))
        return vista(*args, **kwargs)

    return envoltura


def usuario_actual():
    """
    Devuelve un diccionario con los datos del usuario logueado (incluido el
    nombre de su rol) o None si no hay sesión activa.

    Se usa para personalizar la interfaz: mostrar el nombre en el sidebar,
    ocultar/mostrar opciones según el rol, etc.
    """
    uid = session.get("usuario_id")
    if not uid:
        return None

    try:
        conn = get_db()
    except Exception:
        return None

    try:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT u.*, r.nombre AS rol
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                WHERE u.id = %s
                """,
                (uid,),
            )
            return c.fetchone()
    except Exception:
        return None
    finally:
        conn.close()


def _actualizar_ultimo_acceso(usuario_id):
    """Guarda la fecha/hora del último inicio de sesión del usuario."""
    try:
        conn = get_db()
    except Exception:
        return
    try:
        with conn.cursor() as c:
            c.execute(
                "UPDATE usuarios SET ultimo_acceso = %s WHERE id = %s",
                (datetime.now(), usuario_id),
            )
        conn.commit()
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# RUTAS
# -----------------------------------------------------------------------------

# --- Iniciar sesión (GET muestra el formulario, POST lo procesa) ----------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Página y lógica de inicio de sesión."""
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        if not usuario or not password:
            flash("Ingresa tu usuario y contraseña.", "error")
            return render_template("login.html")

        try:
            conn = get_db()
        except Exception as e:
            flash(f"Base de datos no disponible: {e}", "error")
            return render_template("login.html")

        try:
            with conn.cursor() as c:
                c.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
                fila = c.fetchone()
        except Exception as e:
            flash(f"Error al consultar la base de datos: {e}", "error")
            return render_template("login.html")
        finally:
            conn.close()

        # Validar contraseña SOLO si existe el usuario y tiene hash.
        if not fila or not fila.get("password_hash"):
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("login.html")

        if not check_password_hash(fila["password_hash"], password):
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("login.html")

        if fila["estado"] == "bloqueado":
            flash("Tu cuenta está bloqueada. Contacta al administrador.", "error")
            return render_template("login.html")

        # Éxito: registrar la sesión y actualizar el último acceso.
        session["usuario_id"] = fila["id"]
        session["usuario_nombre"] = fila["nombre"]
        session["usuario_rol"] = fila["rol_id"]
        _actualizar_ultimo_acceso(fila["id"])

        return redirect(url_for("index"))

    return render_template("login.html")


# --- Registro de una nueva cuenta ------------------------------------------
@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    """Página y lógica de creación de una cuenta nueva."""
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        # Validaciones básicas del formulario.
        if not (usuario and nombre and correo and password):
            flash("Completa todos los campos obligatorios.", "error")
            return render_template("registro.html")
        if len(password) < 4:
            flash("La contraseña debe tener al menos 4 caracteres.", "error")
            return render_template("registro.html")
        if password != password2:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("registro.html")

        try:
            conn = get_db()
        except Exception as e:
            flash(f"Base de datos no disponible: {e}", "error")
            return render_template("registro.html")

        try:
            # Rol por defecto: 3 (Estudiante). El admin asigna roles en el módulo Usuarios.
            hash_pw = generate_password_hash(password)
            with conn.cursor() as c:
                c.execute(
                    """
                    INSERT INTO usuarios (usuario, nombre, correo, password_hash, rol_id, estado)
                    VALUES (%s, %s, %s, %s, 3, 'activo')
                    """,
                    (usuario, nombre, correo, hash_pw),
                )
            conn.commit()
            flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "ok")
        except Exception as e:
            # Error de MySQL con código 1062 = UNIQUE duplicado (usuario/correo ya existen).
            if "1062" in str(e):
                flash("Ese nombre de usuario o correo ya está registrado.", "error")
            else:
                flash(f"Error al crear la cuenta: {e}", "error")
            return render_template("registro.html")
        finally:
            conn.close()

        return redirect(url_for("auth.login"))

    return render_template("registro.html")


# --- Cerrar sesión -----------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    """Limpia la sesión y devuelve al usuario a la pantalla de login."""
    session.clear()
    return redirect(url_for("auth.login"))
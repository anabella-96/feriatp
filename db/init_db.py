# =============================================================================
#  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
#  ARCHIVO: db/init_db.py
#  PROPÓSITO: Crea y rellena la base de datos `colegio` leyendo los archivos
#             `db/schema.sql` (estructura) y `db/seed.sql` (datos de ejemplo).
#
#  CÓMO USARLO (desde la raíz del proyecto):
#     python db/init_db.py                          -> crea BD, tablas y datos
#     python db/init_db.py --no-seed                -> solo crea BD y tablas
#     python db/init_db.py --force-drop             -> borra la BD antes (desde cero)
#
#  CONFIGURACIÓN DE LA CONEXIÓN:
#     Usa las mismas variables que la aplicación (back/camera_module/
#     services/db_service.py). Se pueden pasar como argumentos o con variables
#     de entorno:
#        DB_HOST / DB_USER / DB_PASSWORD / DB_DATABASE
#     Ejemplo en PowerShell:
#        $env:DB_PASSWORD="mi_password"; python db\init_db.py
# =============================================================================

import os
import sys
import argparse

try:
    import pymysql
except ImportError:
    print("❌ Falta la librería pymysql. Instálala con:  pip install PyMySQL")
    sys.exit(1)


# -----------------------------------------------------------------------------
# 1) LECTURA DE CONFIGURACIÓN
#    Orden de prioridad: argumento CLI > variable de entorno > valor por defecto.
#    OJO: estas credenciales DEBEN coincidir con las de db_service.py.
# -----------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_DATABASE = os.environ.get("DB_DATABASE", "colegio")


def parse_args():
    """Define y lee los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Crea la base de datos del sistema de asistencia biométrica.")
    # Conexión (sobrescriben a las variables de entorno / valores por defecto)
    parser.add_argument("--host", default=DB_HOST, help=f"Host de MySQL (por defecto: {DB_HOST})")
    parser.add_argument("--user", default=DB_USER, help=f"Usuario de MySQL (por defecto: {DB_USER})")
    parser.add_argument("--password", default=DB_PASSWORD, help="Contraseña de MySQL")
    parser.add_argument("--database", default=DB_DATABASE, help=f"Nombre de la base de datos (por defecto: {DB_DATABASE})")
    # Comportamiento
    parser.add_argument("--no-seed", action="store_true", help="No insertar los datos de ejemplo (solo esquema)")
    parser.add_argument("--force-drop", action="store_true", help="Borrar la base de datos si ya existe (empezar de cero)")
    return parser.parse_args()


def leer_sql(ruta_archivo):
    """
    Lee un archivo .sql y lo devuelve como una lista de sentencias.
    Se eliminan las líneas de comentario '--' y las sentencias se separan por ';'.
    NOTA: las sentencias de nuestros .sql no contienen ';' dentro de los datos.
    """
    if not os.path.exists(ruta_archivo):
        print(f"❌ No se encontró el archivo: {ruta_archivo}")
        return []

    with open(ruta_archivo, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    # Quitar comentarios y líneas vacías, y unir todo en un solo texto
    lineas = [l for l in lineas if l.strip() and not l.strip().startswith("--")]
    sql_completo = "\n".join(lineas)

    # Dividir por ';' y limpiar espacios sobrantes
    sentencias = [s.strip() for s in sql_completo.split(";") if s.strip()]
    return sentencias


def ejecutar(conn, sentencias):
    """Ejecuta cada sentencia SQL de la lista y muestra un mensaje corto."""
    with conn.cursor() as cursor:
        for sql in sentencias:
            cursor.execute(sql)
            # Mostramos la 'primera palabra' de la sentencia para informar (CREATE/INSERT/USE...)
            primera = sql.split()[0].upper()
            print(f"  ✔ Ejecutada: {primera} {sql.split()[1] if len(sql.split()) > 1 else ''} ...")
    # Confirmar todos los cambios pendientes en la BD
    conn.commit()


def migrar_si_falta(conn, database):
    """
    Ajusta una base que YA existía de versiones anteriores del esquema.

    Antes no existía la columna password_hash en `usuarios` (no había login).
    Si la base es antigua, CREATE TABLE IF NOT EXISTS no la agrega, así que la
    añadimos aquí con un ALTER. Así se puede ejecutar init_db.py sin necesidad
    de --force-drop después de actualizar el proyecto.
    """
    with conn.cursor() as c:
        c.execute(f"USE `{database}`")
        c.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'usuarios' AND column_name = 'password_hash'
            """,
            (database,),
        )
        tiene_password = c.fetchone()[0]

    if not tiene_password:
        print("  🔁 Migración: agregando columna password_hash a la tabla usuarios...")
        with conn.cursor() as c:
            c.execute(
                "ALTER TABLE usuarios ADD COLUMN password_hash VARCHAR(255) NOT NULL "
                "COMMENT 'Hash de la contraseña (werkzeug)' AFTER correo"
            )
        conn.commit()


def main():
    """Punto de entrada del script."""
    args = parse_args()

    # Ruta base del script: .../feriatp/db/init_db.py  ->  carpeta db
    dir_db = os.path.dirname(os.path.abspath(__file__))
    ruta_esquema = os.path.join(dir_db, "schema.sql")
    ruta_seed = os.path.join(dir_db, "seed.sql")

    print("=" * 70)
    print("  INICIALIZADOR DE BASE DE DATOS - Asistec")
    print("=" * 70)
    print(f"  Host     : {args.host}")
    print(f"  Usuario  : {args.user}")
    print(f"  Base     : {args.database}")
    print()

    # -------------------------------------------------------------------------
    # 1) CONECTAR AL SERVIDOR MySQL (sin elegir todavía la base de datos).
    #    Esto permite crear la base si no existe / borrarla con --force-drop.
    # -------------------------------------------------------------------------
    try:
        conn = pymysql.connect(
            host=args.host,
            user=args.user,
            password=args.password,
            connect_timeout=5,
        )
    except Exception as e:
        print(f"❌ No se pudo conectar a MySQL en {args.host}:")
        print(f"   {e}")
        print("   ¿Está MySQL corriendo? ¿Son correctas user/password?")
        print("   Consejo: si tu root tiene contraseña, pásala con: python db/init_db.py --password TU_CLAVE")
        sys.exit(1)

    try:
        # ---------------------------------------------------------------------
        # 2) (OPCIONAL) BORRAR TODO Y CREAR LA BASE DESDE CERO
        #    Evita errores cuando las tablas ya existen con datos antiguos.
        # ---------------------------------------------------------------------
        if args.force_drop:
            print("  🧨 --force-drop activado: borrando la base de datos anterior...")
            with conn.cursor() as c:
                c.execute(f"DROP DATABASE IF EXISTS `{args.database}`")
            conn.commit()

        # ---------------------------------------------------------------------
        # 3) EJECUTAR EL ESQUEMA (crea base de datos + tablas).
        # ---------------------------------------------------------------------
        print("  📦 Aplicando esquema (schema.sql)...")
        sentencias_esquema = leer_sql(ruta_esquema)
        if not sentencias_esquema:
            print(f"❌ El archivo {ruta_esquema} está vacío o no se encontró.")
            sys.exit(1)
        ejecutar(conn, sentencias_esquema)

        # ---------------------------------------------------------------------
        # 3.5) MIGRACIÓN: si la base era de una versión anterior (sin login),
        #      agregar la columna password_hash que exige el seed.
        # ---------------------------------------------------------------------
        migrar_si_falta(conn, args.database)

        # ---------------------------------------------------------------------
        # 4) (OPCIONAL) INSERTAR DATOS DE EJEMPLO.
        # ---------------------------------------------------------------------
        if not args.no_seed:
            print("  📊 Insertando datos de ejemplo (seed.sql)...")
            sentencias_seed = leer_sql(ruta_seed)
            if sentencias_seed:
                ejecutar(conn, sentencias_seed)
            else:
                print(f"  ⚠ El archivo {ruta_seed} no se encontró. Saltando datos de ejemplo.")
        else:
            print("  ⏭  --no-seed: no se insertaron datos de ejemplo.")

        print()
        print("  ✅ BASE DE DATOS LISTA.")
        print(f"  Base creada/configurada: {args.database}")
        print("  Ahora inicia el servidor con:  start.bat  (o  python back/app.py)")
    except Exception as e:
        print(f"❌ Error durante la inicialización: {e}")
        sys.exit(1)
    finally:
        # Siempre cerramos la conexión, tenga éxito o no.
        conn.close()


if __name__ == "__main__":
    main()
# Carpeta `db/` — Base de datos del sistema

Esta carpeta contiene los scripts que crean y alinean la base de datos **MySQL** con todo el proyecto **Asistec** (control de asistencia biométrica con reconocimiento facial).

## ¿Qué hace cada archivo?

| Archivo       | Propósito                                                              |
|---------------|------------------------------------------------------------------------|
| `schema.sql`  | Crea la base de datos `colegio` y **todas las tablas** del sistema.     |
| `seed.sql`    | Inserta **datos de ejemplo** (alumnos, profesores, cursos, usuarios...). |
| `init_db.py`  | Ejecuta automáticamente `schema.sql` + `seed.sql` desde Python.         |

## ¿Qué base de datos usa el proyecto?

El backend solo consulta la BD en un lugar:

- **`back/camera_module/services/db_service.py`** → tablas `alumnos` y `asistencias` (para registrar la asistencia cuando se reconoce un rostro).

El resto de tablas (`roles`, `usuarios`, `profesores`, `cursos`, `sesiones`, `historial`) reflejan los módulos que muestra el dashboard y quedan listas para que el sistema crezca.

> **Importante:** las fotos de los rostros se guardan en `back/imagenes_conocidas/{id_alumno}.jpg`. Por eso los `id` de los alumnos (ej. `20231045`) coinciden exactamente con el nombre de su foto y con lo que muestra la interfaz.

## Cómo usarlo

### 1. Ejecutar el inicializador (recomendado)

Desde la raíz del proyecto:

```bash
python db/init_db.py
```

Si tu MySQL tiene contraseña:

```bash
python db/init_db.py --password TU_CONTRASEÑA
```

Opciones útiles:

```bash
python db/init_db.py --no-seed        # solo crea tablas (sin datos de ejemplo)
python db/init_db.py --force-drop     # borra y recrea la base desde cero
```

### 2. Alternativa con el cliente de MySQL

```bash
mysql -u root -p < db/schema.sql
mysql -u root -p < db/seed.sql
```

## Cómo alinear las credenciales con la aplicación

`db/init_db.py` y `db_service.py` usan la misma configuración:

| Variable de entorno | Valor por defecto |
|---------------------|-------------------|
| `DB_HOST`           | `localhost`       |
| `DB_USER`           | `root`            |
| `DB_PASSWORD`       | *(vacío)*         |
| `DB_DATABASE`       | `colegio`         |

En PowerShell puedes definirla para toda la sesión:

```powershell
$env:DB_PASSWORD="tu_password"
python db\init_db.py
```

o directamente en los argumentos:

```powershell
python db\init_db.py --password tu_password
```

## Orden de ejecución para probar todo

```bash
# 1. Crear y llenar la base de datos
python db/init_db.py --password tu_password

# 2. Iniciar el servidor web
start.bat                # o: python back/app.py

# 3. Abrir http://localhost:5000 -> te pedirá INICIAR SESIÓN
#    Usuario:  carlosr      Contraseña:  123456   (Administrador)
#    Usuario:  luism        Contraseña:  123456   (Profesor)
```

## Login y roles (nuevo)

- El esquema ahora incluye `usuarios.password_hash` para iniciar sesión.
- Los usuarios de ejemplo tienen la contraseña **`123456`** (hash scrypt de werkzeug):
  - `carlosr` → Administrador (acceso total).
  - `luism` y `anar` → Profesor.
  - `sofiah` → bloqueado (no puede entrar, para probar el aviso).
- Hay una página pública **`/registro`** que crea cuentas con rol *Estudiante* por defecto.
- Si ya tenías la base creada antes de esta actualización, `init_db.py` ahora la **migra automáticamente** (agrega `password_hash`); o bien usa `--force-drop`.

## Flujo completo recomendado (desde cero)

```bash
# 1. Crear BD + datos de ejemplo (con tus credenciales de MySQL)
python db/init_db.py --password tu_password

# 2. Iniciar sesión en http://localhost:5000 (carlosr / 123456)

# 3. Módulo "Estudiantes" -> "+ Nuevo Estudiante":
#    el sistema genera la matrícula, la muestra en pantalla y ofrece
#    "Registrar su rostro" (va a la cámara con ese ID ya cargado).

# 4. En Asistencia en tiempo real -> "Iniciar cámara" ->
#    "Registrar rostro" (guarda la foto) y "Registrar asistencia" (reconoce y marca).
```

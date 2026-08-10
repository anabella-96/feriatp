-- =============================================================================
--  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
--  ARCHIVO: db/schema.sql
--  PROPÓSITO: Crea la base de datos `colegio` y TODAS las tablas que usa el
--             proyecto, alineadas con los módulos del frontend y con lo que
--             el backend realmente consulta.
--
--  ¿QUIÉN USA QUÉ?
--    * back/camera_module/services/db_service.py  ->  tablas `alumnos` y
--                                                    `asistencias`  (CRÍTICO).
--    * El resto de tablas (roles, usuarios, profesores, cursos, sesiones,
--      historial) representan los módulos que muestra el dashboard
--      (Usuarios, Roles, Profesores, Cursos, Sesiones, Historial de cambios).
--
--  IMPORTANTE (almacenamiento de fotos):
--    El reconocimiento facial guarda las fotos en back/imagenes_conocidas/
--    con el nombre {id_del_alumno}.jpg  -> por eso alumnos.id usa los mismos
--    IDs de 8 dígitos que se ven en la interfaz (ej: 20231045).
--
--  CÓMO EJECUTARLO:
--    Opción A (recomendada):  python db/init_db.py
--    Opción B:  mysql -u root -p < db/schema.sql  y luego  mysql -u root -p < db/seed.sql
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1) CREAR LA BASE DE DATOS (si no existe).
--    utf8mb4 soporta tildes, ñ y emojis correctamente.
-- ----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS colegio
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- A partir de aquí trabajamos dentro de la base `colegio`.
USE colegio;

-- ----------------------------------------------------------------------------
-- 2) TABLA: roles
--    Tipos de usuario del sistema (Administrador, Profesor, Estudiante...).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del rol',
    nombre      VARCHAR(50)  NOT NULL UNIQUE COMMENT 'Nombre del rol (admin, profesor, estudiante, invitado)',
    descripcion VARCHAR(255) NULL        COMMENT 'Qué puede hacer este rol'
) ENGINE=InnoDB COMMENT='Roles de usuario del sistema';

-- ----------------------------------------------------------------------------
-- 3) TABLA: usuarios
--    Cuentas de acceso al sistema (lo que muestra el módulo "Usuarios").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del usuario',
    usuario        VARCHAR(50)  NOT NULL UNIQUE COMMENT 'Nombre de usuario para iniciar sesión',
    nombre         VARCHAR(120) NOT NULL COMMENT 'Nombre completo real',
    correo         VARCHAR(150) NOT NULL UNIQUE COMMENT 'Correo asociado a la cuenta',
    password_hash  VARCHAR(255) NOT NULL COMMENT 'Hash de la contraseña (werkzeug generate_password_hash)',
    rol_id         INT UNSIGNED NOT NULL COMMENT 'Rol asignado (FK -> roles.id)',
    ultimo_acceso  DATETIME     NULL COMMENT 'Último inicio de sesión',
    estado         ENUM('activo','bloqueado','inactivo') NOT NULL DEFAULT 'activo' COMMENT 'Estado de la cuenta',
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Usuarios / cuentas del sistema';

-- ----------------------------------------------------------------------------
-- 4) TABLA: profesores
--    Docentes de la institución (módulo "Profesores").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profesores (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del profesor',
    nombre       VARCHAR(120) NOT NULL COMMENT 'Nombre completo del docente',
    especialidad VARCHAR(100) NULL COMMENT 'Área en la que se desempeña',
    correo       VARCHAR(150) NULL COMMENT 'Correo del docente',
    estado       ENUM('activo','inactivo') NOT NULL DEFAULT 'activo' COMMENT 'Estado del docente'
) ENGINE=InnoDB COMMENT='Profesores de la institución';

-- ----------------------------------------------------------------------------
-- 5) TABLA: cursos
--    Cursos vigentes (módulo "Cursos").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cursos (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del curso',
    codigo        VARCHAR(20)  NOT NULL UNIQUE COMMENT 'Código del curso (ej: PROG-101)',
    nombre        VARCHAR(120) NOT NULL COMMENT 'Nombre del curso',
    profesor_id   INT UNSIGNED NULL COMMENT 'Profesor asignado (FK -> profesores.id)',
    estudiantes   INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Cantidad de estudiantes inscritos',
    semestre      VARCHAR(30)  NULL COMMENT 'Semestre académico (ej: 1° 2026)',
    estado        ENUM('activo','inactivo','finalizado') NOT NULL DEFAULT 'activo' COMMENT 'Estado del curso',
    CONSTRAINT fk_cursos_profesor FOREIGN KEY (profesor_id) REFERENCES profesores(id) ON DELETE SET NULL
) ENGINE=InnoDB COMMENT='Cursos de la institución';

-- ----------------------------------------------------------------------------
-- 6) TABLA: alumnos  *** TABLA CRÍTICA PARA EL RECONOCIMIENTO FACIAL ***
--    db_service.py ejecuta: SELECT * FROM alumnos WHERE id = %s
--    y luego lee las columnas: nombre, apellido, curso.
--    Por eso esas columnas DEBEN existir con exactamente esos nombres.
--    La columna `curso` es un texto simple (denormalizado) a propósito,
--    para que el backend la muestre sin necesidad de hacer JOINs.
--    El `id` coincide con el nombre del archivo de foto:
--    back/imagenes_conocidas/20231045.jpg  <->  alumno id = 20231045
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alumnos (
    id       BIGINT UNSIGNED NOT NULL PRIMARY KEY COMMENT 'Matrícula/ID del alumno (ej: 20231045). Coincide con el nombre de su foto',
    nombre   VARCHAR(120) NOT NULL COMMENT 'Primer nombre del alumno',
    apellido VARCHAR(120) NOT NULL COMMENT 'Apellido del alumno',
    correo   VARCHAR(150) NULL COMMENT 'Correo del alumno',
    curso    VARCHAR(120) NULL COMMENT 'Curso al que pertenece (texto, coincide con el frontend)',
    estado   ENUM('activo','inactivo','ausente') NOT NULL DEFAULT 'activo' COMMENT 'Estado del alumno'
) ENGINE=InnoDB COMMENT='Alumnos (matrícula + datos para el reconocimiento facial)';

-- ----------------------------------------------------------------------------
-- 7) TABLA: sesiones
--    Clases programadas por curso (módulo "Sesiones").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sesiones (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único de la sesión',
    fecha          DATE NOT NULL COMMENT 'Fecha de la clase',
    horario        VARCHAR(30) NULL COMMENT 'Horario (ej: 10:00 - 11:30)',
    curso_id       INT UNSIGNED NULL COMMENT 'Curso de la sesión (FK -> cursos.id)',
    profesor_id    INT UNSIGNED NULL COMMENT 'Profesor a cargo (FK -> profesores.id)',
    total_alumnos  INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Alumnos esperados',
    asistencia     DECIMAL(5,2) NULL COMMENT 'Porcentaje de asistencia registrado',
    estado         ENUM('programada','en_curso','finalizada') NOT NULL DEFAULT 'programada' COMMENT 'Estado de la sesión',
    CONSTRAINT fk_sesiones_curso    FOREIGN KEY (curso_id)    REFERENCES cursos(id)    ON DELETE SET NULL,
    CONSTRAINT fk_sesiones_profesor FOREIGN KEY (profesor_id) REFERENCES profesores(id) ON DELETE SET NULL
) ENGINE=InnoDB COMMENT='Sesiones / clases programadas';

-- ----------------------------------------------------------------------------
-- 8) TABLA: asistencias  *** TABLA CRÍTICA PARA REGISTRAR ASISTENCIA ***
--    db_service.py (guardar_asistencia) hace:
--      1. SELECT id FROM asistencias WHERE alumno_id=%s AND fecha=%s  (evita duplicar)
--      2. INSERT INTO asistencias (alumno_id, fecha, hora, estado) VALUES (...)
--    El UNIQUE(alumno_id, fecha) garantiza a nivel de BD que un alumno
--    solo pueda marcar UNA vez por día.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asistencias (
    id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del registro',
    alumno_id BIGINT UNSIGNED NOT NULL COMMENT 'Alumno que marcó (FK -> alumnos.id)',
    fecha     DATE            NOT NULL COMMENT 'Día en que marcó asistencia',
    hora      TIME            NOT NULL COMMENT 'Hora exacta del registro',
    estado    ENUM('presente','tarde','ausente') NOT NULL DEFAULT 'presente' COMMENT 'Estado calculado por el sistema',
    CONSTRAINT fk_asistencias_alumno FOREIGN KEY (alumno_id) REFERENCES alumnos(id) ON DELETE CASCADE,
    CONSTRAINT uq_alumno_fecha UNIQUE (alumno_id, fecha)
) ENGINE=InnoDB COMMENT='Registro de asistencia diario por alumno';

-- ----------------------------------------------------------------------------
-- 9) TABLA: historial
--    Bitácora de acciones realizadas (módulo "Historial de cambios").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del evento',
    fecha_hora DATETIME NOT NULL COMMENT 'Cuándo ocurrió la acción',
    usuario_id INT UNSIGNED NULL COMMENT 'Usuario que la realizó (FK -> usuarios.id)',
    accion     VARCHAR(50)  NOT NULL COMMENT 'Tipo de acción (creación, edición, eliminación...)',
    modulo     VARCHAR(50)  NOT NULL COMMENT 'Módulo afectado (Usuarios, Sesiones...)',
    detalle    VARCHAR(255) NULL COMMENT 'Descripción de la acción',
    ip         VARCHAR(45)  NULL COMMENT 'Dirección IP desde la que se hizo'
) ENGINE=InnoDB COMMENT='Historial de cambios y auditoría';
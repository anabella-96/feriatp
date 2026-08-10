-- =============================================================================
--  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
--  ARCHIVO: db/seed.sql
--  PROPÓSITO: Inserta datos de ejemplo en la base `colegio` para que el
--             proyecto se pueda probar de inmediato.
--
--  LOS DATOS SON LOS MISMOS QUE APARECEN EN LA INTERFAZ:
--    - Alumnos con IDs 20231045, 20231050, ... para que el reconocimiento
--      facial funcione: si registras un rostro con el ID 20231045, el sistema
--      guardará back/imagenes_conocidas/20231045.jpg y podrá marcarlo.
--    - Las fechas de asistencia son PASADAS (no hoy) para no estropear el
--      flujo "marcó hoy" de prueba.
--
--  LOS INSERTS SE PUEDEN EJECUTAR VARIAS VECES SIN ERROR (usamos
--  INSERT ... ON DUPLICATE KEY UPDATE / IGNORE según el caso).
-- =============================================================================

USE colegio;

-- ----------------------------------------------------------------------------
-- 1) ROLES  (módulo Roles y Permisos)
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO roles (id, nombre, descripcion) VALUES
    (1, 'Administrador', 'Acceso total al sistema'),
    (2, 'Profesor',      'Gestiona cursos y asistencia'),
    (3, 'Estudiante',    'Solo consulta de su información'),
    (4, 'Invitado',      'Acceso limitado solo a reportes públicos');

-- ----------------------------------------------------------------------------
-- 2) USUARIOS  (módulo Usuarios)
--    password_hash = hash werkzeug (scrypt) de la contraseña "123456" para
--    TODOS los usuarios de ejemplo ->  usuario: carlosr  contraseña: 123456
--    (generado con: generate_password_hash("123456")).
--    Los INSERT ... ON DUPLICATE KEY UPDATE refrescan el hash por si la cuenta
--    ya existía sin contraseña (creada con el esquema anterior).
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO usuarios (usuario, nombre, correo, rol_id, ultimo_acceso, estado, password_hash) VALUES
    ('carlosr', 'Carlos Ramírez',  'admin@asistec.edu', 1, '2026-07-07 08:10:00', 'activo',   'scrypt:32768:8:1$P2Kb34KPoZjs5XB8$f351f694b29fd7d439487c46472c556f5c0d93a05b278bc93802ad36a13b26f518d2a4847fea04d7d8b4f10b86eb20c5b4f60b948ebe245b6a879fbe7bd16239'),
    ('luism',   'Luis Martínez',   'luis@asistec.edu',  2, '2026-07-07 07:45:00', 'activo',   'scrypt:32768:8:1$P2Kb34KPoZjs5XB8$f351f694b29fd7d439487c46472c556f5c0d93a05b278bc93802ad36a13b26f518d2a4847fea04d7d8b4f10b86eb20c5b4f60b948ebe245b6a879fbe7bd16239'),
    ('anar',    'Ana Ruiz',        'ana@asistec.edu',   2, '2026-07-06 16:20:00', 'activo',   'scrypt:32768:8:1$P2Kb34KPoZjs5XB8$f351f694b29fd7d439487c46472c556f5c0d93a05b278bc93802ad36a13b26f518d2a4847fea04d7d8b4f10b86eb20c5b4f60b948ebe245b6a879fbe7bd16239'),
    ('sofiah',  'Sofía Herrera',   'sofia@asistec.edu', 2, '2026-07-01 09:05:00', 'bloqueado','scrypt:32768:8:1$P2Kb34KPoZjs5XB8$f351f694b29fd7d439487c46472c556f5c0d93a05b278bc93802ad36a13b26f518d2a4847fea04d7d8b4f10b86eb20c5b4f60b948ebe245b6a879fbe7bd16239')
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    nombre        = VALUES(nombre),
    correo        = VALUES(correo);

-- ----------------------------------------------------------------------------
-- 3) PROFESORES  (módulo Profesores)
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO profesores (id, nombre, especialidad, correo, estado) VALUES
    (1, 'Luis Martínez Ojeda', 'Informática',      'luis.martinez@correo.edu', 'activo'),
    (2, 'Ana Ruiz Herrera',    'Matemáticas',      'ana.ruiz@correo.edu',      'activo'),
    (3, 'Carlos Torres Silva', 'Bases de Datos',   'carlos.torres@correo.edu', 'activo'),
    (4, 'Sofía Herrera Díaz',  'Idiomas',          'sofia.herrera@correo.edu', 'activo'),
    (5, 'Gonzalo Lufin',       'Informática',      'gonzalo.lufin@correo.edu', 'activo'),
    (6, 'Carolina Moreno',     'Programación',     'carolina.moreno@correo.edu', 'activo'),
    (7, 'Liza Molina',         'Bases de Datos',   'liza.molina@correo.edu',   'activo'),
    (8, 'Lucas Reyes',         'Ciencias',         'lucas.reyes@correo.edu',   'activo');

-- ----------------------------------------------------------------------------
-- 4) CURSOS  (módulo Cursos)
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO cursos (id, codigo, nombre, profesor_id, estudiantes, semestre, estado) VALUES
    (1, 'PROG-101', 'Matemáticas',     5, 45, '1° 2026', 'activo'),
    (2, 'MAT-202',  'Programación I',  6, 38, '1° 2026', 'activo'),
    (3, 'BD-301',   'Base de Datos',   7, 42, '1° 2026', 'activo'),
    (4, 'ING-103',  'Ciencias',        8, 50, '1° 2026', 'finalizado');

-- ----------------------------------------------------------------------------
-- 5) ALUMNOS  *** LOS IDs DEBEN COINCIDIR CON LAS FOTOS EN imagenes_conocidas ***
--    Ejemplo: foto 20231045.jpg  ->  alumno id 20231045
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO alumnos (id, nombre, apellido, correo, curso, estado) VALUES
    (20231045, 'Fernando',  'Ojeda',        'fernando.ojeda@sip.cl', 'Programación I',  'activo'),
    (20231050, 'Carolina',  'Moreno',       'carolina.moreno@sip.cl', 'Base de Datos',  'activo'),
    (20231052, 'Gonzalo',   'Lufin',        'gonzalo.lufin@sip.cl',   'Matemáticas',    'activo'),
    (20231060, 'Liza',      'Molina',       'liza.molina@sip.cl',     'Base de Datos',  'activo'),
    (20231061, 'Pedro',     'López Silva',  'pedro.lopez@correo.edu', 'Base de Datos',  'activo'),
    (20231070, 'Lucas',     'Reyes',        'lucas.reyes@sip.cl',     'Ciencias',       'activo'),
    (20231078, 'Ana',       'Martínez Torres', 'ana.martinez@correo.edu', 'Inglés Técnico', 'inactivo'),
    (20231085, 'Antonella', 'Lobos',        'antonella.lobos@sip.cl', 'Programación I', 'activo');

-- ----------------------------------------------------------------------------
-- 6) SESIONES  (módulo Sesiones) - fechas pasadas para no interferir en pruebas
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO sesiones (fecha, horario, curso_id, profesor_id, total_alumnos, asistencia, estado) VALUES
    ('2026-07-07', '10:00 - 11:30', 2, 6, 45, 78.00, 'en_curso'),
    ('2026-07-07', '08:00 - 09:30', 1, 5, 38, NULL,  'programada'),
    ('2026-07-06', '14:00 - 15:30', 3, 7, 42, 91.00, 'finalizada');

-- ----------------------------------------------------------------------------
-- 7) ASISTENCIAS  (registros de ejemplo, NINGUNO es de hoy)
--    Fecha "hoy" = fecha del servidor; si registras los mismos IDs hoy,
--    el sistema los marcará como presentes (no "ya registrado").
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO asistencias (alumno_id, fecha, hora, estado) VALUES
    (20231045, '2026-07-07', '10:15:22', 'presente'),
    (20231050, '2026-07-07', '10:16:05', 'presente'),
    (20231060, '2026-07-07', '10:17:12', 'presente'),
    (20231070, '2026-07-07', '10:18:45', 'presente'),
    (20231052, '2026-07-06', '08:02:00', 'presente'),
    (20231061, '2026-07-06', '14:05:30', 'tarde'),
    (20231045, '2026-07-06', '08:03:15', 'presente');

-- ----------------------------------------------------------------------------
-- 8) HISTORIAL  (módulo Historial de cambios)
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO historial (fecha_hora, usuario_id, accion, modulo, detalle, ip) VALUES
    ('2026-07-07 08:22:15', 1, 'Edición',      'Usuarios',  'Modificación de rol para usuario: sofiah',  '192.168.1.45'),
    ('2026-07-07 08:10:02', 1, 'Inicio sesión','Acceso',    'Ingreso exitoso al sistema',                '192.168.1.45'),
    ('2026-07-06 16:20:44', 3, 'Creación',     'Sesiones',  'Programada nueva sesión: Matemáticas II',   '192.168.1.52'),
    ('2026-07-06 15:45:10', 2, 'Reporte',      'Reportes',  'Generado reporte de asistencia mensual',    '192.168.1.38'),
    ('2026-07-05 11:30:05', 1, 'Eliminación',  'Estudiantes','Eliminado registro: ID 20231022',          '192.168.1.45');
// =============================================================================
//  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
//  ARCHIVO: front/js/gestion.js
//
//  PROPÓSITO:
//    Da vida a los módulos de gestión académica del dashboard (Estudiantes,
//    Cursos, Profesores y Sesiones):
//      1. Carga los datos desde las APIs /api/* y pinta las tablas.
//      2. Abre/cierra los modales de "Nuevo ...".
//      3. Crea y elimina registros (POST / DELETE).
//      4. FLUJO CLAVE DEL PROYECTO: al crear un estudiante, muestra la
//         MATRÍCULA generada por el servidor y ofrece el botón
//         "Registrar su rostro", que lleva a la cámara con ese ID ya cargado.
//
//  SE CARGA SOLO EN EL DASHBOARD (después de front/js/script.js).
//  Todas las llamadas llevan la cookie de sesión (mismo origen). Si el
//  servidor responde 401, redirigimos a /login.
// =============================================================================

// -----------------------------------------------------------------------------
// Utilidades
// -----------------------------------------------------------------------------

// Escapar texto para insertarlo en HTML sin riesgo de inyección (XSS).
function esc(texto) {
    return String(texto ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

// Fetch con manejo central de errores y sesión caducada (401 -> /login).
async function apiFetch(url, opciones) {
    const config = opciones || {};
    try {
        const respuesta = await fetch(url, config);
        if (respuesta.status === 401) {
            window.location.href = '/login';
            throw new Error('Sesión expirada');
        }
        const datos = await respuesta.json();
        return datos;
    } catch (e) {
        if (e.message === 'Sesión expirada') throw e;
        console.error('Error en la petición a', url, e);
        throw new Error('No se pudo conectar con el servidor.');
    }
}

// Mapea el estado (cadena de la BD) a la clase CSS y texto legible.
function estadoBadge(estado) {
    const mapa = {
        activo:     ['active',    'Activo'],
        inactivo:   ['inactive',  'Inactivo'],
        ausente:    ['warning',   'Ausente'],
        bloqueado:  ['blocked',   'Bloqueado'],
        programada: ['scheduled', 'Programada'],
        en_curso:   ['ongoing',   'En curso'],
        finalizada: ['completed', 'Finalizada'],
    };
    const [clase, texto] = mapa[estado] || ['inactive', estado || '—'];
    return `<span class="status ${clase}">${esc(texto)}</span>`;
}

// Convierte una fecha YYYY-MM-DD a DD/MM/YYYY para mostrar en las tablas.
function formatearFecha(fecha) {
    if (!fecha) return '-';
    const partes = String(fecha).split('-');
    if (partes.length !== 3) return fecha;
    return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

// Abrir (mostrar) y cerrar un modal por su id.
function abrirModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('show');
}

function cerrarModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('show');
    // Si es el modal del estudiante, restaurar el formulario (ocultar resultado).
    if (id === 'modal-estudiante') {
        const form = document.getElementById('form-estudiante');
        const resultado = document.getElementById('resultado-estudiante');
        if (form) form.style.display = 'block';
        if (resultado) resultado.style.display = 'none';
    }
}

// Llenar un <select> con opciones (id -> texto). Sirve para los formularios.
function llenarSelect(selectId, opciones, etiquetaVacia, valorVacio) {
    const select = document.getElementById(selectId);
    if (!select) return;
    // Opción por defecto (ej: "Selecciona un curso").
    select.innerHTML = `<option value="">${esc(etiquetaVacia)}</option>`;
    opciones.forEach(op => {
        const option = document.createElement('option');
        option.value = op.valor;
        option.textContent = op.texto;
        select.appendChild(option);
    });
    if (valorVacio !== '') select.value = valorVacio;
}

// -----------------------------------------------------------------------------
// Carga de cada lista (Estudiantes, Cursos, Profesores, Sesiones)
// -----------------------------------------------------------------------------

async function cargarEstudiantes() {
    const tbody = document.getElementById('cuerpoEstudiantes');
    if (!tbody) return;
    try {
        const datos = await apiFetch('/api/estudiantes');
        if (!datos.ok) { tbody.innerHTML = `<tr><td colspan="7">${esc(datos.mensaje)}</td></tr>`; return; }

        if (!datos.datos.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-gray-500" style="text-align:center;">Sin estudiantes registrados.</td></tr>';
            return;
        }

        tbody.innerHTML = datos.datos.map(a => `
            <tr>
                <td>${esc(a.id)}</td>
                <td>${esc(a.nombre)} ${esc(a.apellido)}</td>
                <td>${esc(a.correo || '-')}</td>
                <td>${esc(a.curso || '-')}</td>
                <td>-</td>
                <td>${estadoBadge(a.estado)}</td>
                <td>
                    <button class="btn-icon btn-rostro" data-id="${esc(a.id)}" title="Registrar rostro">
                        <i class="fa-solid fa-id-badge"></i>
                    </button>
                    <button class="btn-icon btn-delete" data-id="${esc(a.id)}" data-tipo="estudiantes" title="Eliminar">
                        <i class="fa-solid fa-trash text-danger"></i>
                    </button>
                </td>
            </tr>`).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7">${esc(e.message)}</td></tr>`;
    }
}

async function cargarCursos() {
    const tbody = document.getElementById('cuerpoCursos');
    if (!tbody) return;
    try {
        const datos = await apiFetch('/api/cursos');
        if (!datos.ok) { tbody.innerHTML = `<tr><td colspan="7">${esc(datos.mensaje)}</td></tr>`; return; }

        if (!datos.datos.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-gray-500" style="text-align:center;">Sin cursos registrados.</td></tr>';
            return;
        }

        tbody.innerHTML = datos.datos.map(c => `
            <tr>
                <td>${esc(c.codigo)}</td>
                <td>${esc(c.nombre)}</td>
                <td>${esc(c.profesor || 'Sin asignar')}</td>
                <td>${esc(c.estudiantes)}</td>
                <td>${esc(c.semestre || '-')}</td>
                <td>${estadoBadge(c.estado)}</td>
                <td>
                    <button class="btn-icon btn-delete" data-id="${esc(c.id)}" data-tipo="cursos" title="Eliminar">
                        <i class="fa-solid fa-trash text-danger"></i>
                    </button>
                </td>
            </tr>`).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7">${esc(e.message)}</td></tr>`;
    }
}

async function cargarProfesores() {
    const tbody = document.getElementById('cuerpoProfesores');
    if (!tbody) return;
    try {
        const datos = await apiFetch('/api/profesores');
        if (!datos.ok) { tbody.innerHTML = `<tr><td colspan="7">${esc(datos.mensaje)}</td></tr>`; return; }

        if (!datos.datos.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-gray-500" style="text-align:center;">Sin profesores registrados.</td></tr>';
            return;
        }

        tbody.innerHTML = datos.datos.map(p => `
            <tr>
                <td>PROF-${String(p.id).padStart(3, '0')}</td>
                <td>${esc(p.nombre)}</td>
                <td>${esc(p.especialidad || '-')}</td>
                <td>${esc(p.cursos_a_cargo)}</td>
                <td>${esc(p.correo || '-')}</td>
                <td>${estadoBadge(p.estado)}</td>
                <td>
                    <button class="btn-icon btn-delete" data-id="${esc(p.id)}" data-tipo="profesores" title="Eliminar">
                        <i class="fa-solid fa-trash text-danger"></i>
                    </button>
                </td>
            </tr>`).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7">${esc(e.message)}</td></tr>`;
    }
}

async function cargarSesiones() {
    const tbody = document.getElementById('cuerpoSesiones');
    if (!tbody) return;
    try {
        const datos = await apiFetch('/api/sesiones');
        if (!datos.ok) { tbody.innerHTML = `<tr><td colspan="8">${esc(datos.mensaje)}</td></tr>`; return; }

        if (!datos.datos.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-gray-500" style="text-align:center;">Sin sesiones programadas.</td></tr>';
            return;
        }

        tbody.innerHTML = datos.datos.map(s => `
            <tr>
                <td>${esc(formatearFecha(s.fecha))}</td>
                <td>${esc(s.horario || '-')}</td>
                <td>${esc(s.curso || '-')}</td>
                <td>${esc(s.profesor || '-')}</td>
                <td>${esc(s.total_alumnos)}</td>
                <td>${s.asistencia != null ? esc(s.asistencia) + '%' : '-'}</td>
                <td>${estadoBadge(s.estado)}</td>
                <td>
                    <button class="btn-icon btn-delete" data-id="${esc(s.id)}" data-tipo="sesiones" title="Eliminar">
                        <i class="fa-solid fa-trash text-danger"></i>
                    </button>
                </td>
            </tr>`).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8">${esc(e.message)}</td></tr>`;
    }
}

// Recargar una lista según el nombre del módulo.
function recargarLista(tipo) {
    if (tipo === 'estudiantes') cargarEstudiantes();
    else if (tipo === 'cursos') cargarCursos();
    else if (tipo === 'profesores') cargarProfesores();
    else if (tipo === 'sesiones') cargarSesiones();
}

// -----------------------------------------------------------------------------
// Registro de rostro: navega a "Asistencia en tiempo real" con el ID cargado
// -----------------------------------------------------------------------------

// Función global para que el botón "Registrar su rostro" y los de cada fila
// lleven al usuario a la cámara con ese alumno ya SELECCIONADO automáticamente
// (la matrícula nunca se digita; sale del selector de alumnos sin rostro).
function irARegistrarRostro(id) {
    // Recordar la matrícula pendiente ANTES de navegar: si la página se recarga
    // (p. ej. redirección a HTTPS de la cámara o F5), el selector de abajo la
    // vuelve a pre-seleccionar y no se pierde el ID ni el flujo de registro.
    try { sessionStorage.setItem('await_rostro', String(id)); } catch (e) { /* sin storage */ }

    // La misma matrícula como parámetro "?rostro=" sobrevive incluso si el
    // navegador cambia de origen (http://IP:5000 -> https://IP:5001).
    const current = new URLSearchParams(window.location.search);
    current.set('rostro', String(id));
    window.history.replaceState({}, '', window.location.pathname + '?' + current.toString());

    // 1. Navegar a la sección "Asistencia en tiempo real" usando el sidebar.
    const linkAsistencia = document.querySelector('.nav-link[data-section="asistencia"]');
    if (linkAsistencia) linkAsistencia.click();
    // 2. Seleccionar automáticamente al alumno en el selector (ID automático).
    if (typeof cargarAlumnosSinRostro === 'function') cargarAlumnosSinRostro(id);
    // 3. Encender la cámara automáticamente (función global de script.js).
    if (typeof encenderCamara === 'function') encenderCamara();
}

// -----------------------------------------------------------------------------
// Creación de registros (POST) — según el formulario del modal
// -----------------------------------------------------------------------------

async function crearEstudiante(form) {
    const cuerpo = {
        nombre: form.nombre.value.trim(),
        apellido: form.apellido.value.trim(),
        correo: form.correo.value.trim(),
        curso: form.curso.value,
        estado: form.estado.value,
    };

    try {
        const res = await apiFetch('/api/estudiantes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo),
        });

        if (!res.ok) { alert(res.mensaje); return; }

        // ÉXITO: enseñar la matrícula generada y ofrecer el registro de rostro.
        document.getElementById('id-estudiante-nuevo').textContent = res.id;
        document.getElementById('nombre-estudiante-nuevo').textContent = res.nombre_completo;

        form.style.display = 'none';
        document.getElementById('resultado-estudiante').style.display = 'block';

        recargarLista('estudiantes');
    } catch (e) {
        alert(e.message);
    }
}

async function crearCurso(form) {
    const cuerpo = {
        codigo: form.codigo.value.trim(),
        nombre: form.nombre.value.trim(),
        profesor_id: form.profesor.value || null,
        estudiantes: form.estudiantes.value,
        semestre: form.semestre.value.trim(),
        estado: form.estado.value,
    };

    try {
        const res = await apiFetch('/api/cursos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo),
        });
        alert(res.ok ? res.mensaje : res.mensaje);
        if (res.ok) { cerrarModal('modal-curso'); recargarLista('cursos'); }
    } catch (e) {
        alert(e.message);
    }
}

async function crearProfesor(form) {
    const cuerpo = {
        nombre: form.nombre.value.trim(),
        especialidad: form.especialidad.value.trim(),
        correo: form.correo.value.trim(),
        estado: form.estado.value,
    };

    try {
        const res = await apiFetch('/api/profesores', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo),
        });
        alert(res.ok ? res.mensaje : res.mensaje);
        if (res.ok) { cerrarModal('modal-profesor'); recargarLista('profesores'); }
    } catch (e) {
        alert(e.message);
    }
}

async function crearSesion(form) {
    const cuerpo = {
        fecha: form.fecha.value,
        horario: form.horario.value.trim(),
        curso_id: form.curso.value || null,
        profesor_id: form.profesor.value || null,
        total_alumnos: form.total_alumnos.value,
        estado: form.estado.value,
    };

    try {
        const res = await apiFetch('/api/sesiones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo),
        });
        alert(res.ok ? res.mensaje : res.mensaje);
        if (res.ok) { cerrarModal('modal-sesion'); recargarLista('sesiones'); }
    } catch (e) {
        alert(e.message);
    }
}

// -----------------------------------------------------------------------------
// Eliminación (DELETE) con confirmación
// -----------------------------------------------------------------------------

async function eliminarRegistro(tipo, id) {
    const etiquetas = { estudiantes: 'estudiante', cursos: 'curso', profesores: 'profesor', sesiones: 'sesión' };
    if (!confirm(`¿Eliminar este ${etiquetas[tipo] || 'registro'}? Esta acción no se puede deshacer.`)) return;

    try {
        const res = await apiFetch(`/api/${tipo}/${id}`, { method: 'DELETE' });
        alert(res.mensaje || (res.ok ? 'Eliminado.' : 'No se pudo eliminar.'));
        if (res.ok) recargarLista(tipo);
    } catch (e) {
        alert(e.message);
    }
}

// -----------------------------------------------------------------------------
// Inicialización: cargar listas, llenar selects y conectar eventos
// -----------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {

    // 1. Cargar las 4 tablas al abrir el dashboard.
    cargarEstudiantes();
    cargarCursos();
    cargarProfesores();
    cargarSesiones();

    // 2. Llenar los selects de los formularios con datos existentes.
    //    (el select de curso del estudiante y de sesiones = nombres de cursos;
    //     el select de profesor = lista de profesores).
    (async () => {
        try {
            const cursos = await apiFetch('/api/cursos');
            if (cursos.ok) {
                const opciones = cursos.datos.map(c => ({ valor: c.nombre, texto: c.nombre }));
                llenarSelect('estudiante-curso', opciones, 'Selecciona un curso');
                llenarSelect('sesion-curso', cursos.datos.map(c => ({ valor: c.id, texto: c.nombre })), 'Selecciona un curso');
            }
        } catch (e) { /* ya se mostró el error en consola */ }

        try {
            const profesores = await apiFetch('/api/profesores');
            if (profesores.ok) {
                llenarSelect('curso-profesor', profesores.datos.map(p => ({ valor: p.id, texto: p.nombre })), 'Sin asignar');
                llenarSelect('sesion-profesor', profesores.datos.map(p => ({ valor: p.id, texto: p.nombre })), 'Sin profesor');
            }
        } catch (e) { /* ya se mostró el error en consola */ }
    })();

    // 3. Botones "+ Nuevo ..." -> abren su modal.
    document.getElementById('btn-nuevo-estudiante')?.addEventListener('click', () => abrirModal('modal-estudiante'));
    document.getElementById('btn-nuevo-curso')?.addEventListener('click', () => abrirModal('modal-curso'));
    document.getElementById('btn-nuevo-profesor')?.addEventListener('click', () => abrirModal('modal-profesor'));
    document.getElementById('btn-nueva-sesion')?.addEventListener('click', () => abrirModal('modal-sesion'));

    // 4. Envío de los formularios de creación.
    document.getElementById('form-estudiante')?.addEventListener('submit', e => { e.preventDefault(); crearEstudiante(e.target); });
    document.getElementById('form-curso')?.addEventListener('submit', e => { e.preventDefault(); crearCurso(e.target); });
    document.getElementById('form-profesor')?.addEventListener('submit', e => { e.preventDefault(); crearProfesor(e.target); });
    document.getElementById('form-sesion')?.addEventListener('submit', e => { e.preventDefault(); crearSesion(e.target); });
});

// 5. Delegación de eventos dinámicos (botones creados al pintar las tablas):
//    - Cerrar modales  [data-cerrar]
//    - "Registrar su rostro" (desde el modal del estudiante)  #btn-ir-rostro
//    - "Registrar rostro" por fila de la tabla  .btn-rostro
//    - "Eliminar" por fila de la tabla  .btn-delete
document.addEventListener('click', e => {

    // Cerrar modal (botones "Cancelar" / "Cerrar" / X).
    const cerrarBtn = e.target.closest('[data-cerrar]');
    if (cerrarBtn) {
        cerrarModal(cerrarBtn.getAttribute('data-cerrar'));
        return;
    }

    // Botón del modal del estudiante: ir a la cámara con el ID generado.
    if (e.target.closest('#btn-ir-rostro')) {
        const id = document.getElementById('id-estudiante-nuevo').textContent;
        cerrarModal('modal-estudiante');
        irARegistrarRostro(id);
        return;
    }

    // Botón de cada fila de estudiantes: registrar el rostro de ese ID.
    const botonRostro = e.target.closest('.btn-rostro');
    if (botonRostro) {
        irARegistrarRostro(botonRostro.getAttribute('data-id'));
        return;
    }

    // Botón de eliminar de cada fila.
    const botonEliminar = e.target.closest('.btn-delete');
    if (botonEliminar) {
        eliminarRegistro(botonEliminar.getAttribute('data-tipo'), botonEliminar.getAttribute('data-id'));
    }
});
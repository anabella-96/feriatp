// =============================================================================
//  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
//  ARCHIVO: front/js/script.js
//
//  PROPÓSITO:
//    Da vida al dashboard. Se encarga de:
//      1. Navegación entre secciones (sidebar izquierdo).
//      2. Control de la cámara web (encender / apagar).
//      3. Registrar asistencia (captura un frame y lo envía a POST /reconocer).
//      4. Registrar nuevos rostros (captura un frame y lo envía a POST /registrar_rostro).
//      5. Gráficos de Chart.js y lógica auxiliar del frontend.
//
//  FLUJO BÁSICO DE LA CÁMARA:
//    front/js/script.js  --fetch-->  back/camera_module/routes.py  -->  MySQL
//      (captura frame en base64)         (DeepFace + db_service.py)
//
//  NOTA: existen DOS botones "Iniciar cámara" (uno en la tarjeta principal y
//  otro en la columna de controles); por eso el manejador de clics reconoce
//  tanto por id como por el texto del botón.
// =============================================================================

// -----------------------------------------------------------------------------
// 1) VARIABLES GLOBALES DE LA CÁMARA
//    Se obtienen UNA vez (al cargar el script) porque estos elementos existen
//    solo en la sección "Asistencia en tiempo real" (front/templates/asistencia.html).
// -----------------------------------------------------------------------------
const video = document.getElementById("video");               // <video> que muestra la cámara
const canvas = document.getElementById("canvas");             // <canvas> oculto donde copiamos el frame
const resultadoContainer = document.getElementById("resultado-container"); // caja donde se muestra el resultado
const resultadoTexto = document.getElementById("resultado");  // texto del resultado
const placeholderCamara = document.getElementById("camera-placeholder"); // mensaje gris "Cámara inactiva"

// Guardamos el stream (flujo de la cámara) en esta variable global
// para poder detenerlo con apagarCamara() cuando sea necesario.
let camaraStream = null;

// -----------------------------------------------------------------------------
// 2) FUNCIÓN AUXILIAR: mostrar mensajes de la cámara en la interfaz
// -----------------------------------------------------------------------------
function mostrarMensaje(texto, tipo) {
    if (resultadoTexto && resultadoContainer) {
        // Asegurar que la caja de resultado sea visible.
        resultadoContainer.style.display = "block";
        resultadoTexto.textContent = texto;

        // Colores de fondo y texto según el tipo de mensaje.
        let bgColor = "#f3f4f6";
        let textColor = "#1f2937";
        if (tipo === "error") { bgColor = "#fef2f2"; textColor = "#991b1b"; }
        else if (tipo === "success") { bgColor = "#ecfdf5"; textColor = "#065f46"; }
        else if (tipo === "warning") { bgColor = "#fffbeb"; textColor = "#92400e"; }
        else if (tipo === "info") { bgColor = "#eff6ff"; textColor = "#1e40af"; }

        resultadoContainer.style.backgroundColor = bgColor;
        resultadoContainer.style.color = textColor;
    } else {
        // Si el elemento no existe, al menos lo mostramos por consola.
        console.log(`[${tipo.toUpperCase()}]: ${texto}`);
    }
}

// -----------------------------------------------------------------------------
// 3) ENCENDER LA CÁMARA
//    Pide permiso al navegador (navigator.mediaDevices.getUserMedia),
//    asigna el stream al <video> y oculta el placeholder gris.
// -----------------------------------------------------------------------------
function encenderCamara() {
    if (!video) {
        console.error("No se encontró el elemento <video> en el HTML.");
        return;
    }

    mostrarMensaje("Iniciando cámara...", "info");

    // getUserMedia devuelve una "promesa". Si el usuario acepta, stream.
    navigator.mediaDevices.getUserMedia({
        video: {
            width: { ideal: 400 },
            height: { ideal: 300 },
        },
    })
    .then(stream => {
        camaraStream = stream;          // Guardamos el flujo para poder detenerlo.
        video.srcObject = stream;       // Conectamos el stream al <video>.

        // Esperamos a que el video cargue los metadatos y luego lo reproducimos.
        video.onloadedmetadata = () => {
            video.play()
                .then(() => {
                    mostrarMensaje("Cámara encendida y lista.", "success");
                    console.log("Stream de video reproduciéndose correctamente.");

                    // Ocultar el placeholder gris para dejar ver la cámara.
                    if (placeholderCamara) {
                        placeholderCamara.style.display = "none";
                    }

                    // Cambiar el badge de estado a "Activo".
                    const badge = document.getElementById("asistencia-status-badge");
                    if (badge) {
                        badge.textContent = "Activo";
                        badge.style.backgroundColor = "#d1fae5";
                        badge.style.color = "#065f46";
                    }
                })
                .catch(err => {
                    console.error("Error al reproducir el video:", err);
                    mostrarMensaje("Error al reproducir el video de la cámara.", "error");
                });
        };
    })
    .catch(err => {
        console.error("Error de acceso a la cámara:", err);
        mostrarMensaje("Error con la cámara: " + err.message, "error");
    });
}

// -----------------------------------------------------------------------------
// 4) APAGAR LA CÁMARA
//    Detiene los tracks del stream, libera el <video> y restaura el estado.
// -----------------------------------------------------------------------------
function apagarCamara() {
    // Detener cada "track" (video/audio) del stream anterior.
    if (camaraStream) {
        camaraStream.getTracks().forEach(track => track.stop());
        camaraStream = null;
    }
    if (video) {
        video.srcObject = null;
    }
    // Volver a mostrar el placeholder "Cámara inactiva".
    if (placeholderCamara) {
        placeholderCamara.style.display = "flex";
    }

    // Restablecer el badge a "Inactivo".
    const badge = document.getElementById("asistencia-status-badge");
    if (badge) {
        badge.textContent = "Inactivo";
        badge.style.backgroundColor = "#e5e7eb";
        badge.style.color = "#374151";
    }

    mostrarMensaje("Cámara apagada.", "info");
}

// -----------------------------------------------------------------------------
// 5) REGISTRAR ASISTENCIA
//    Toma un frame del video, lo envía a POST /reconocer y muestra el resultado.
//    El servidor identifica el rostro (DeepFace) y guarda la asistencia en MySQL.
// -----------------------------------------------------------------------------
function capturar() {
    if (!video || !canvas) {
        console.error("Los elementos de video o canvas no están definidos en el HTML.");
        return;
    }

    // No se puede capturar si la cámara no está encendida.
    if (!camaraStream) {
        mostrarMensaje("⚠️ Primero debes iniciar la cámara.", "warning");
        return;
    }

    // Copiar el frame actual del video al canvas (resolución 400x300).
    const contexto = canvas.getContext("2d");
    contexto.drawImage(video, 0, 0, 400, 300);

    // Convertir el canvas a una imagen JPEG en base64 (data URL).
    const imagenBase64 = canvas.toDataURL("image/jpeg");

    mostrarMensaje("Procesando detección facial...", "info");

    // Enviar la imagen al servidor con AJAX (petición POST).
    fetch("/reconocer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagen: imagenBase64 }),
    })
    .then(respuesta => respuesta.json())
    .then(datos => {
        // El servidor responde con un diccionario {ok, mensaje, ...}.
        if (!datos.ok) {
            // ERROR del servidor (no reconoció, no hay rostros, BD caída, etc.).
            mostrarMensaje("❌ " + datos.mensaje, "error");
            return;
        }
        if (datos.ya_registrado) {
            // El alumno ya marcó asistencia hoy.
            mostrarMensaje("⚠ " + datos.nombre + " — " + datos.mensaje, "warning");
            return;
        }

        // Actualizar la información dinámica del panel lateral de asistencia.
        document.getElementById("asistencia-nombre").textContent = `Última detección: ${datos.nombre}`;
        document.getElementById("asistencia-hora").textContent = `Hora: ${datos.hora || '--:--:--'}`;
        document.getElementById("asistencia-confianza").textContent = `Confianza: ${datos.confianza || '99'}%`;

        // ÉXITO: mostrar el resumen (nombre | curso | hora | estado).
        mostrarMensaje(
            "✅ " + datos.nombre + " | " + datos.curso + " | " + datos.hora + " | " + datos.estado,
            "success"
        );
    })
    .catch(err => {
        mostrarMensaje("Error de red: " + err, "error");
    });
}

// -----------------------------------------------------------------------------
// 6) REGISTRAR UN NUEVO ROSTRO
//    Toma un frame del video + el ID del alumno, los envía a POST /registrar_rostro.
//    El servidor verifica que haya una cara y guarda la foto en
//    back/imagenes_conocidas/{alumno_id}.jpg (dejándola lista para reconocer).
// -----------------------------------------------------------------------------

// Ayudante para mostrar mensajes en la tarjeta "Registrar nuevo rostro".
function mostrarResultadoRegistro(texto, tipo) {
    const contenedor = document.getElementById("registro-rostro-resultado");
    if (!contenedor) { console.log(`[${tipo.toUpperCase()}]: ${texto}`); return; }

    // Mismos colores que mostrarMensaje().
    let bgColor = "#f3f4f6";
    let textColor = "#1f2937";
    if (tipo === "error") { bgColor = "#fef2f2"; textColor = "#991b1b"; }
    else if (tipo === "success") { bgColor = "#ecfdf5"; textColor = "#065f46"; }
    else if (tipo === "warning") { bgColor = "#fffbeb"; textColor = "#92400e"; }
    else if (tipo === "info") { bgColor = "#eff6ff"; textColor = "#1e40af"; }

    contenedor.style.display = "block";
    contenedor.style.backgroundColor = bgColor;
    contenedor.style.color = textColor;
    contenedor.textContent = texto;
}

function registrarRostro() {
    if (!video || !canvas) {
        console.error("Los elementos de video o canvas no están definidos en el HTML.");
        return;
    }

    // No se puede registrar si la cámara no está encendida.
    if (!camaraStream) {
        mostrarResultadoRegistro("⚠️ Primero debes iniciar la cámara.", "warning");
        return;
    }

    // Leer el ID del alumno escrito en el input de la tarjeta.
    const inputAlumno = document.getElementById("input-alumno-registrar");
    const alumnoId = inputAlumno ? inputAlumno.value.trim() : "";

    // Validar que sea un número (el ID será el nombre del archivo de foto).
    if (!alumnoId || !/^\d+$/.test(alumnoId)) {
        mostrarResultadoRegistro("⚠️ Ingresa el ID del alumno (solo números).", "warning");
        return;
    }

    // Copiar el frame actual del video al canvas y convertirlo a base64.
    const contexto = canvas.getContext("2d");
    contexto.drawImage(video, 0, 0, 400, 300);
    const imagenBase64 = canvas.toDataURL("image/jpeg");

    mostrarResultadoRegistro("Procesando y guardando rostro...", "info");

    // Enviar imagen + id del alumno al servidor.
    fetch("/registrar_rostro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagen: imagenBase64, alumno_id: alumnoId }),
    })
    .then(respuesta => respuesta.json())
    .then(datos => {
        if (!datos.ok) {
            mostrarResultadoRegistro("❌ " + datos.mensaje, "error");
            return;
        }
        // Éxito: el rostro quedó registrado.
        mostrarResultadoRegistro("✅ " + datos.mensaje, "success");
        if (inputAlumno) inputAlumno.value = ""; // Limpiar el input para el siguiente.
    })
    .catch(err => {
        mostrarResultadoRegistro("Error de red: " + err, "error");
    });
}

// -----------------------------------------------------------------------------
// 7) INICIALIZACIÓN GENERAL (cuando el DOM termina de cargar)
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {

    // --- 7.1 Navegación entre secciones del sidebar ---
    // Cada enlace del sidebar tiene un atributo data-section (ej: "asistencia")
    // y la sección correspondiente tiene id="section-asistencia".
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.content-section');
    const breadcrumbs = document.getElementById('breadcrumbs');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault(); // Evitar el salto del ancla "#..."

            // Quitar la clase "active" de todos los enlaces y secciones.
            navLinks.forEach(l => l.classList.remove('active'));
            sections.forEach(sec => sec.classList.remove('active'));

            // Activar SOLO el enlace presionado.
            this.classList.add('active');

            // Mostrar SOLO la sección correspondiente.
            const sectionId = this.getAttribute('data-section');
            const targetSection = document.getElementById(`section-${sectionId}`);
            if (targetSection) {
                targetSection.classList.add('active');
            }

            // Actualizar la "miga de pan" (breadcrumb) de la barra superior.
            if (breadcrumbs) {
                breadcrumbs.innerHTML = `<span>${this.textContent.trim()}</span>`;
            }

            // En pantallas pequeñas, cerrar el sidebar tras navegar.
            if (window.innerWidth < 1024) {
                const sidebar = document.getElementById('sidebar');
                if (sidebar) sidebar.classList.remove('open');
            }
        });
    });

    // --- 7.2 Botón de menú lateral (versiones móviles / tablet) ---
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    // --- 7.3 Gráfico de evolución de asistencia mensual (Chart.js) ---
    const ctxAsistencia = document.getElementById('chartAsistencia');
    if (ctxAsistencia && typeof Chart !== 'undefined') {
        new Chart(ctxAsistencia, {
            type: 'line',
            data: {
                labels: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul'],
                datasets: [{
                    label: 'Porcentaje de asistencia',
                    data: [82, 85, 87, 88, 89, 90, 89.2],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: true,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: {
                    y: { beginAtZero: false, min: 70, max: 100 },
                },
            },
        });
    }

    // --- 7.4 Gráfico de distribución de estados (dona) ---
    const ctxEstados = document.getElementById('chartEstados');
    if (ctxEstados && typeof Chart !== 'undefined') {
        new Chart(ctxEstados, {
            type: 'doughnut',
            data: {
                labels: ['Presentes', 'Ausentes', 'Tardanzas'],
                datasets: [{
                    data: [89.2, 8.5, 2.3],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }

    // --- 7.5 Matriz de permisos por rol (módulo Roles y Permisos) ---
    // Al cambiar el rol seleccionado, se marcan/desmarcan los checkboxes
    // "permiso_*" según lo que puede hacer cada rol.
    const selectorRol = document.getElementById('selectorRol');
    if (selectorRol) {
        const permisosPorRol = {
            admin:      { ver: true, editar: true, eliminar: true, crear_usuarios: true, roles: true, reportes: true, asistencia: true, configuracion: true },
            profesor:   { ver: true, editar: true, eliminar: false, crear_usuarios: false, roles: false, reportes: true, asistencia: true, configuracion: false },
            estudiante: { ver: true, editar: false, eliminar: false, crear_usuarios: false, roles: false, reportes: false, asistencia: false, configuracion: false },
            invitado:   { ver: true, editar: false, eliminar: false, crear_usuarios: false, roles: false, reportes: true, asistencia: false, configuracion: false },
        };

        selectorRol.addEventListener('change', function() {
            const rol = this.value;
            const datos = permisosPorRol[rol];
            Object.keys(datos).forEach(permiso => {
                const elemento = document.getElementById(`permiso_${permiso}`);
                if (elemento) elemento.checked = datos[permiso];
            });
        });
    }

    // --- 7.6 Buscador global (barra superior) ---
    // Por ahora solo registra lo que se escribe; la búsqueda real se agrega después.
    const buscadorGlobal = document.getElementById('buscadorGlobal');
    if (buscadorGlobal) {
        buscadorGlobal.addEventListener('input', function() {
            const texto = this.value.toLowerCase().trim();
            if (texto.length < 2) return; // No buscar con menos de 2 caracteres.
            console.log('Buscando:', texto);
        });
    }
});

// -----------------------------------------------------------------------------
// 8) MANEJADOR GENERAL DE CLICS
//    Como los botones se crean dentro de plantillas Jinja, usamos DELEGACIÓN
//    de eventos: un único listener en document que detecta qué botón se
//    presionó (por id o por su texto) y llama a la función correcta.
// -----------------------------------------------------------------------------
document.addEventListener('click', function(e) {
    // 8.1 Si el clic fue dentro de un botón .btn ...
    if (e.target.closest('.btn')) {
        const boton = e.target.closest('button');
        const texto = boton.textContent.trim().toLowerCase();
        const id = boton.id;

        console.log("Botón presionado:", texto, "con ID:", id);

        // Iniciar la cámara (dos botones posibles: principal y controles laterales).
        if (id === 'btn-iniciar-camara' || texto.includes("iniciar cámara") || texto.includes("iniciar sesion / camara")) {
            encenderCamara();
        }
        // Pausar/detener la cámara.
        else if (id === 'btn-detener-camara' || texto.includes("pausar reconocimiento") || texto.includes("apagar cámara")) {
            apagarCamara();
        }
        // Registrar asistencia (capturar frame y enviar a /reconocer).
        else if (id === 'btn-capturar' || texto.includes("registrar asistencia")) {
            capturar();
        }
        // Registrar un nuevo rostro (enviar frame + id a /registrar_rostro).
        else if (id === 'btn-registrar-rostro' || texto.includes("registrar rostro")) {
            registrarRostro();
        }
    }

    // 8.2 Botones de icono genéricos en tablas (solo log de la acción).
    if (e.target.closest('.btn-icon')) {
        const boton = e.target.closest('button');
        const accion = boton.title || boton.getAttribute('aria-label');
        if (accion) console.log('Acción seleccionada:', accion);
    }
});
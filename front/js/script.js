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

// --- Selección de cámara (interna / externa) ---
// cameraActual   -> deviceId de la cámara que está en uso (null = automática)
// cameraDispositivos -> lista de cámaras detectadas {deviceId, label}
let cameraActual = null;
let cameraDispositivos = [];

// Devuelve un nombre amigable para una cámara. Mientras no se haya dado
// permiso, el navegador oculta las etiquetas, así que usamos "Interna"/"Externa"
// según la posición en la lista (por lo general la 1ª es interna y la 2ª externa).
function nombreCamara(dispositivo, indice) {
    const etiqueta = (dispositivo.label || "").trim();
    if (etiqueta) return etiqueta;
    if (indice === 0) return "Cámara interna";
    if (indice === 1) return "Cámara externa (USB)";
    return "Cámara " + (indice + 1);
}

// Enumera todas las cámaras del dispositivo y las muestra en el selector.
function cargarCamaras() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    const select = document.getElementById("camera-select");
    navigator.mediaDevices.enumerateDevices()
        .then(dispositivos => {
            cameraDispositivos = dispositivos.filter(d => d.kind === "videoinput");
            if (!select) return;

            // Recordar la selección actual antes de reconstruir las opciones.
            const previa = select.value;

            select.innerHTML = "";
            // Opción "Automática": el sistema usa la cámara por defecto.
            const opcionAuto = document.createElement("option");
            opcionAuto.value = "auto";
            opcionAuto.textContent = "📷 Cámara automática";
            select.appendChild(opcionAuto);

            cameraDispositivos.forEach((dispositivo, indice) => {
                const opcion = document.createElement("option");
                opcion.value = dispositivo.deviceId;
                opcion.textContent = nombreCamara(dispositivo, indice);
                select.appendChild(opcion);
            });

            // Restaurar la selección anterior (o la cámara que está activa).
            if (previa && Array.from(select.options).some(o => o.value === previa)) {
                select.value = previa;
            } else if (cameraActual && cameraActual !== "auto") {
                select.value = cameraActual;
            }
        })
        .catch(err => console.warn("No se pudieron listar las cámaras:", err));
}

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
//    Acepta la "deviceId" de la cámara que se quiere usar (interna, externa, etc.).
//    Si no se pasa nada, usa la cámara por defecto del dispositivo.
// -----------------------------------------------------------------------------
function encenderCamara(deviceId) {
    if (!video) {
        console.error("No se encontró el elemento <video> en el HTML.");
        return;
    }

    // La API de cámara SOLO existe en "contexto seguro" (HTTPS o localhost).
    // Si por cualquier motivo se abrió con http:// + IP (desde otro dispositivo
    // de la red) nos redirigimos solos a https://IP:5001, donde sí funciona,
    // en lugar de mostrar un error.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const host = window.location.hostname;
        const enLocal = (host === "localhost" || host === "127.0.0.1");

        if (window.location.protocol !== "https:" && !enLocal) {
            const aviso = "Conectando a la ruta segura (https) para poder usar la cámara...";
            console.warn(aviso);
            mostrarMensaje("ℹ️ " + aviso, "info");
            window.location.replace("https://" + host + ":5001" + window.location.pathname);
            return;
        }

        const aviso = "Tu navegador no permite la cámara aquí. Abre el sistema con https://IP:5001 (o desde localhost).";
        console.error(aviso);
        mostrarMensaje("⚠️ " + aviso, "error");
        if (placeholderCamara) placeholderCamara.style.display = "flex";
        return;
    }

    // Si ya hay una cámara activa y se pidió OTRA distinta, detener la anterior
    // para liberar el dispositivo antes de solicitar el nuevo.
    if (camaraStream) {
        camaraStream.getTracks().forEach(track => track.stop());
        camaraStream = null;
        video.srcObject = null;
        // Dejar visible el placeholder mientras se inicia la nueva cámara.
        if (placeholderCamara) placeholderCamara.style.display = "flex";
    }

    mostrarMensaje("Iniciando cámara...", "info");

    // Restricciones del video: alta resolución y orientación "environment"
    // para que en móviles use preferentemente la cámara trasera por defecto.
    const restriccionesVideo = {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "environment",
    };

    // Si el usuario eligió una cámara concreta, forzamos su deviceId exacto.
    if (deviceId && deviceId !== "auto") {
        restriccionesVideo.deviceId = { exact: deviceId };
        delete restriccionesVideo.facingMode;
    }

    // getUserMedia devuelve una "promesa". Si el usuario acepta, stream.
    navigator.mediaDevices.getUserMedia({ video: restriccionesVideo })
    .then(stream => {
        camaraStream = stream;          // Guardamos el flujo para poder detenerlo.
        cameraActual = (deviceId && deviceId !== "auto") ? deviceId : "auto";
        video.srcObject = stream;       // Conectamos el stream al <video>.

        // Al tener permiso, re-enumerar las cámaras para mostrar sus nombres reales.
        cargarCamaras();

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
    cameraActual = null;
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

    // Copiar el frame actual del video al canvas (mismo tamaño del canvas).
    const contexto = canvas.getContext("2d");
    contexto.drawImage(video, 0, 0, canvas.width, canvas.height);

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
//    Toma un frame del video + el alumno elegido automáticamente, los envía a
//    POST /registrar_rostro. El servidor verifica que haya una cara, rechaza a
//    personas ya registradas y guarda la foto en
//    back/imagenes_conocidas/{alumno_id}.jpg (dejándola lista para reconocer).
//
//    La matrícula NUNCA se digita a mano: sale del selector de alumnos sin
//    rostro (GET /api/estudiantes/sin_rostro), evitando IDs equivocados.
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

// Carga en el selector de "Registrar nuevo rostro" los estudiantes que AÚN no
// tienen foto (GET /api/estudiantes/sin_rostro). La matrícula (value de cada
// opción) se elige automáticamente; nunca se escribe a mano.
// 'seleccionarId' (opcional): matrícula a preseleccionar (ej. el alumno recién
// creado en el módulo Estudiantes).
//
// Para que el ID nunca se pierda (aunque la página se recargue, por ejemplo
// tras la redirección a HTTPS de la cámara o al presionar F5), el alumno
// pendiente se recuerda en sessionStorage y como parámetro "?rostro=" en la URL.
function obtenerAlumnoPendiente(seleccionarId) {
    if (seleccionarId) return String(seleccionarId);
    const deUrl = new URLSearchParams(window.location.search).get('rostro');
    if (deUrl) return deUrl;
    try { return sessionStorage.getItem('await_rostro') || ''; } catch (e) { return ''; }
}

function mostrarAvisoRegistro(texto) {
    const aviso = document.getElementById('alumno-registrar-aviso');
    if (!aviso) return;
    aviso.style.display = 'block';
    aviso.textContent = texto;
}

// Consume el ID pendiente solo cuando ya se confirmó (estaba en el selector).
function limpiarAlumnoPendiente() {
    try { sessionStorage.removeItem('await_rostro'); } catch (e) { /* sin storage */ }
    if (new URLSearchParams(window.location.search).has('rostro')) {
        const url = window.location.origin + window.location.pathname;
        window.history.replaceState({}, '', url);
    }
}
async function cargarAlumnosSinRostro(seleccionarId) {
    const select = document.getElementById('select-alumno-registrar');
    if (!select) return;

    // Completar el ID pedido con recuerdos de sesión (URL ?rostro= / storage).
    const pendiente = obtenerAlumnoPendiente(seleccionarId);

    try {
        const respuesta = await fetch('/api/estudiantes/sin_rostro');
        const datos = await respuesta.json();

        select.innerHTML = '';
        if (!datos.ok || !Array.isArray(datos.datos) || datos.datos.length === 0) {
            select.innerHTML = '<option value="">No hay alumnos pendientes de rostro</option>';
            if (pendiente) {
                mostrarResultadoRegistro(
                    "⚠️ La matrícula " + pendiente + " ya tiene un rostro registrado o no existe.",
                    "warning"
                );
            }
            return;
        }

        datos.datos.forEach(alumno => {
            const opcion = document.createElement('option');
            opcion.value = alumno.id;
            opcion.textContent = `${alumno.id} — ${alumno.nombre} ${alumno.apellido || ''}`;
            select.appendChild(opcion);
        });

        // Preseleccionar la matrícula pedida (la del alumno recién creado).
        // El resto usa la primera opción, que queda seleccionada por defecto.
        let preseleccionado = '';
        if (pendiente && Array.from(select.options).some(o => String(o.value) === String(pendiente))) {
            select.value = String(pendiente);
            preseleccionado = String(pendiente);
        }

        // Mostrar SIEMPRE qué matrícula quedó ingresada en el selector, para
        // que el número autogenerado en Estudiantes sea visible aquí abajo.
        const opcionActiva = Array.from(select.options).find(o => o.value === select.value);
        if (opcionActiva && opcionActiva.value) {
            const esPendiente = String(opcionActiva.value) === preseleccionado;
            mostrarAvisoRegistro(
                "📌 Matrícula a registrar: " + opcionActiva.value +
                (esPendiente ? " (auto-seleccionada desde Estudiantes)" : "")
            );
        }

        if (pendiente && !preseleccionado) {
            // El ID pedido no apareció en la lista (ya tiene rostro o no existe).
            // Se olvida para no arrastrar avisos obsoletos en futuras cargas.
            limpiarAlumnoPendiente();
            mostrarResultadoRegistro(
                "⚠️ La matrícula " + pendiente +
                " no está en la lista de alumnos sin rostro. Si acabas de crearla, verifica que no tenga una foto ya guardada.",
                "warning"
            );
            mostrarAvisoRegistro("Cayó a la primera opción: " + (opcionActiva ? opcionActiva.value : '—'));
        }

        // Si el ID pendiente se confirmó en el selector, olvidarlo para que un
        // futuro "Registrar rostro" no fuerce una matrícula vieja.
        if (preseleccionado) limpiarAlumnoPendiente();
    } catch (e) {
        select.innerHTML = '<option value="">No se pudieron cargar los alumnos</option>';
        if (pendiente) {
            mostrarResultadoRegistro("Error al cargar los alumnos sin rostro: " + e.message, "error");
        }
    }
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

    // La matrícula sale del selector (nunca se digita). Sin alumno, no hay nada.
    const selectAlumno = document.getElementById("select-alumno-registrar");
    let alumnoId = selectAlumno ? selectAlumno.value.trim() : "";
    if (!alumnoId) {
        // Puede ser que aún esté cargando la lista o que no haya pendientes:
        // recargamos y damos un mensaje claro para reintentar.
        cargarAlumnosSinRostro();
        mostrarResultadoRegistro(
            "⚠️ No hay un alumno seleccionado todavía. Espera a que cargue la lista de alumnos sin rostro (o crea un estudiante en el módulo Estudiantes) y vuelve a presionar el botón.",
            "warning"
        );
        return;
    }

    // Copiar el frame actual del video al canvas y convertirlo a base64.
    const contexto = canvas.getContext("2d");
    contexto.drawImage(video, 0, 0, canvas.width, canvas.height);
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
            // Persona ya registrada: se informa como advertencia (con su matrícula).
            if (datos.ya_registrado) {
                mostrarResultadoRegistro("⚠️ " + datos.mensaje, "warning");
                return;
            }
            mostrarResultadoRegistro("❌ " + datos.mensaje, "error");
            return;
        }
        // Éxito: el rostro quedó registrado. Quitamos al alumno del selector
        // (recargando la lista) y quedamos listos para el siguiente.
        mostrarResultadoRegistro("✅ " + datos.mensaje, "success");
        cargarAlumnosSinRostro();
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
                const sidebarMob = document.getElementById('sidebar');
                if (sidebarMob) sidebarMob.classList.remove('open');
                const backdropMob = document.getElementById('sidebar-backdrop');
                if (backdropMob) backdropMob.classList.remove('show');
            }
        });
    });

    // --- 7.2 Botón de menú lateral (versiones móviles / tablet) ---
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            if (sidebarBackdrop) sidebarBackdrop.classList.toggle('show');
        });
    }
    // Cerrar el menú lateral al tocar la capa oscura de fondo (móvil/tablet).
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarBackdrop.classList.remove('show');
        });
    }

    // --- 7.2b Listar las cámaras disponibles y llenar el selector ---
    cargarCamaras();
    // --- 7.2c Cargar alumnos sin rostro para registrar con ID automático ---
    cargarAlumnosSinRostro();
    const selectAlumnoRegistrar = document.getElementById('select-alumno-registrar');
    if (selectAlumnoRegistrar) {
        // Si el usuario elige OTR@ alumno/a a mano, actualizar el aviso visible.
        selectAlumnoRegistrar.addEventListener('change', function () {
            const opcion = this.options[this.selectedIndex];
            if (opcion && opcion.value) {
                mostrarAvisoRegistro("📌 Matrícula a registrar: " + opcion.value);
            } else {
                mostrarAvisoRegistro('');
                const aviso = document.getElementById('alumno-registrar-aviso');
                if (aviso) aviso.style.display = 'none';
            }
        });
    }
    const selectCamara = document.getElementById('camera-select');
    if (selectCamara) {
        selectCamara.addEventListener('change', function () {
            // Si la cámara está encendida, reiniciarla con el dispositivo elegido.
            if (camaraStream) {
                encenderCamara(this.value);
            } else {
                cameraActual = this.value === 'auto' ? null : this.value;
            }
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
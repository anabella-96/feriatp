# 📝 Documentación del Proyecto: Sistema de Control de Asistencia Biométrica

Este documento contiene la explicación del propósito de cada archivo en el proyecto, el código completo y original de cada uno de ellos, y la guía paso a paso sobre cómo integrar la cámara web real en la sección de asistencia del dashboard sin alterar los archivos del proyecto directamente.

---

## 📂 Propósito de los Archivos del Proyecto

El frontend de este sistema de control de asistencia está estructurado de manera modular en tres capas:

1. **`face.html` (Estructura)**:
   * **Propósito**: Define la estructura e interfaz de usuario (UI) del panel de administración (Asistec). Organiza el sistema en múltiples vistas intercambiables (Inicio, Dashboard con estadísticas, Asistencia en tiempo real con cámara, Reportes avanzados, y los módulos de gestión para Cursos, Estudiantes, Profesores, Sesiones, Usuarios y Configuración).
   * **Componentes Clave**: Barra lateral de navegación (`<aside>`), barra superior con notificaciones y buscador (`<header>`), y el área de contenido principal (`<main>`) donde cada sección se renderiza en contenedores `<section>` con la clase `content-section`.

2. **`style.css` (Diseño Visual)**:
   * **Propósito**: Aplica un diseño estético moderno, limpio y premium alineado con las tendencias actuales de diseño UX/UI (paleta de colores armónica usando variables CSS, sombras suaves, bordes redondeados y tipografía estilizada).
   * **Responsividad**: Incluye reglas `@media` para asegurar que el menú lateral se colapse en dispositivos móviles y tabletas, reordenando las tarjetas de datos y la vista de la cámara.

3. **`script.js` (Interactividad)**:
   * **Propósito**: Controla el comportamiento dinámico del cliente.
   * **Funcionalidades**:
     * **Navegación**: Alterna la visualización de las vistas agregando/removiendo la clase `.active` y actualiza la ruta de navegación (Breadcrumbs).
     * **Estadísticas**: Inicializa los gráficos de Chart.js (línea para asistencia mensual y dona para estados de asistencia).
     * **Roles y Permisos**: Ajusta automáticamente la matriz de checkboxes en base al rol seleccionado.
     * **Buscador global**: Evento de escucha para capturar entradas de texto y realizar búsquedas de ejemplo.

---

## 📷 Guía de Integración de la Cámara en el Dashboard

Para hacer que la sección **"Asistencia en Tiempo Real"** funcione con la cámara física e interactúe con el backend del reconocimiento facial, debes realizar los siguientes cambios:

### Paso 1: Modificar el contenedor de la cámara en `face.html`
En `face.html` (dentro de la sección `#section-asistencia`), busca el contenedor original de la cámara:

```html
<div class="camera-container">
    <div class="camera-view">
        <i class="fa-solid fa-video fa-4x text-gray-300"></i>
        <p>Cámara activa - Reconocimiento en curso</p>
        <div class="mt-2 text-xs text-gray-400">Resolución: 1280x720 | FPS: 30</div>
    </div>
    <div class="camera-status">
        <span class="status-badge active">Activo</span>
        ...
    </div>
</div>
```

Debes reemplazarlo agregando una etiqueta `<video>` para mostrar la cámara, un `<canvas>` oculto para procesar las capturas, y elementos con IDs para manipular la respuesta:

```html
<div class="camera-container">
    <div class="camera-view" style="position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; background-color: var(--gray-900); border-radius: var(--radius); height: 350px;">
        <!-- Video en tiempo real -->
        <video id="video" autoplay playsinline style="width: 100%; height: 100%; object-fit: cover; display: none;"></video>
        <!-- Lienzo oculto de captura -->
        <canvas id="canvas" width="640" height="480" style="display: none;"></canvas>
        
        <!-- Estado de carga/apagado de la cámara -->
        <div id="camera-placeholder" style="position: absolute; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem; color: white; width: 100%; height: 100%; top: 0; left: 0;">
            <i class="fa-solid fa-video fa-4x text-gray-300"></i>
            <p id="camera-placeholder-text">Cámara inactiva - Presiona "Iniciar cámara"</p>
        </div>
    </div>
    
    <div class="camera-status">
        <span class="status-badge" id="asistencia-status-badge" style="background-color: var(--gray-200); color: var(--gray-700);">Inactivo</span>
        <p id="asistencia-nombre">Última detección: Ninguna</p>
        <p class="text-xs" id="asistencia-hora">Hora: --:--:--</p>
        <p class="text-xs" id="asistencia-confianza">Confianza: --%</p>
        <div class="mt-4">
            <p class="text-sm font-medium" id="asistencia-contador">Total registrados: 32 / 45</p>
            <div class="progress-bar mt-1"><div id="asistencia-progreso-bar" style="width:71%"></div></div>
        </div>
        <!-- Indicador de respuesta del servidor -->
        <div id="resultado-reconocimiento" style="margin-top: 0.5rem; padding: 0.5rem; border-radius: var(--radius); text-align: center; font-size: 0.85rem; font-weight: 500; display: none;"></div>
    </div>
</div>
```

Además, en la sección de **Controles de sesión**, añade IDs a los botones para poder manipularlos desde el script:
```html
<div class="controls-list">
    <button class="btn btn-primary w-full" id="btn-iniciar-camara">Iniciar sesión / cámara</button>
    <button class="btn btn-secondary w-full" id="btn-detener-camara">Pausar reconocimiento</button>
    <button class="btn btn-warning w-full" id="btn-capturar-asistencia">📸 Registrar asistencia</button>
    <button class="btn btn-outline w-full">Exportar registro</button>
    <button class="btn btn-danger w-full">Finalizar sesión</button>
</div>
```

### Paso 2: Agregar lógica de control en `script.js`
Agrega la siguiente sección de JavaScript al final de tu archivo `script.js` para dar vida a los controles anteriores:

```javascript
// ==============================================
// Control de Cámara y Reconocimiento Facial
// ==============================================
(function() {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const cameraPlaceholder = document.getElementById("camera-placeholder");
    const cameraPlaceholderText = document.getElementById("camera-placeholder-text");
    const btnIniciar = document.getElementById("btn-iniciar-camara");
    const btnDetener = document.getElementById("btn-detener-camara");
    const btnCapturar = document.getElementById("btn-capturar-asistencia");
    const statusBadge = document.getElementById("asistencia-status-badge");
    const nombreDeteccion = document.getElementById("asistencia-nombre");
    const horaDeteccion = document.getElementById("asistencia-hora");
    const confianzaDeteccion = document.getElementById("asistencia-confianza");
    const resultadoReconocimiento = document.getElementById("resultado-reconocimiento");

    let stream = null;

    // Enciende la cámara
    if (btnIniciar && video) {
        btnIniciar.addEventListener("click", function() {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
                    .then(function(s) {
                        stream = s;
                        video.srcObject = s;
                        video.style.display = "block";
                        cameraPlaceholder.style.display = "none";
                        
                        statusBadge.textContent = "Activo";
                        statusBadge.style.backgroundColor = "var(--success)";
                        statusBadge.style.color = "white";
                        
                        resultadoReconocimiento.style.display = "block";
                        resultadoReconocimiento.style.backgroundColor = "rgba(16, 185, 129, 0.1)";
                        resultadoReconocimiento.style.color = "var(--success)";
                        resultadoReconocimiento.textContent = "Cámara iniciada correctamente.";
                    })
                    .catch(function(err) {
                        cameraPlaceholderText.textContent = "Error de cámara: " + err.message;
                        resultadoReconocimiento.style.display = "block";
                        resultadoReconocimiento.style.backgroundColor = "rgba(239, 68, 68, 0.1)";
                        resultadoReconocimiento.style.color = "var(--danger)";
                        resultadoReconocimiento.textContent = "Error: " + err.message;
                    });
            }
        });
    }

    // Apaga la cámara
    if (btnDetener && video) {
        btnDetener.addEventListener("click", function() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            video.srcObject = null;
            video.style.display = "none";
            cameraPlaceholder.style.display = "flex";
            statusBadge.textContent = "Inactivo";
            statusBadge.style.backgroundColor = "var(--gray-200)";
            statusBadge.style.color = "var(--gray-700)";
            resultadoReconocimiento.style.display = "none";
        });
    }

    // Captura el frame, convierte a Base64 y envía a Flask (POST /reconocer)
    if (btnCapturar && canvas && video) {
        btnCapturar.addEventListener("click", function() {
            if (!stream) {
                resultadoReconocimiento.style.display = "block";
                resultadoReconocimiento.style.backgroundColor = "rgba(245, 158, 11, 0.1)";
                resultadoReconocimiento.style.color = "var(--warning)";
                resultadoReconocimiento.textContent = "⚠️ La cámara debe estar encendida para registrar asistencia.";
                return;
            }
            
            // Renderizar imagen del video en canvas
            const context = canvas.getContext("2d");
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Generar string Base64 (JPEG)
            const dataUrl = canvas.toDataURL("image/jpeg");
            
            resultadoReconocimiento.style.display = "block";
            resultadoReconocimiento.style.backgroundColor = "rgba(59, 130, 246, 0.1)";
            resultadoReconocimiento.style.color = "var(--info)";
            resultadoReconocimiento.textContent = "Procesando reconocimiento...";
            
            // Envío AJAX
            fetch("/reconocer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ imagen: dataUrl })
            })
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    resultadoReconocimiento.style.backgroundColor = "rgba(239, 68, 68, 0.1)";
                    resultadoReconocimiento.style.color = "var(--danger)";
                    resultadoReconocimiento.textContent = "❌ " + data.mensaje;
                    return;
                }
                
                if (data.ya_registrado) {
                    resultadoReconocimiento.style.backgroundColor = "rgba(245, 158, 11, 0.1)";
                    resultadoReconocimiento.style.color = "var(--warning)";
                    resultadoReconocimiento.textContent = "⚠️ " + data.nombre + " ya registrado hoy.";
                    return;
                }
                
                // Actualizar interfaz con datos del backend
                resultadoReconocimiento.style.backgroundColor = "rgba(16, 185, 129, 0.1)";
                resultadoReconocimiento.style.color = "var(--success)";
                resultadoReconocimiento.textContent = "✅ " + data.mensaje;
                
                nombreDeteccion.textContent = "Última detección: " + data.nombre;
                horaDeteccion.textContent = "Hora: " + data.hora;
                confianzaDeteccion.textContent = "Estado: " + data.estado.toUpperCase();
            })
            .catch(err => {
                resultadoReconocimiento.style.backgroundColor = "rgba(239, 68, 68, 0.1)";
                resultadoReconocimiento.style.color = "var(--danger)";
                resultadoReconocimiento.textContent = "Error de red: " + err.message;
            });
        });
    }
})();
```

---

## 🛠️ Código Original del Proyecto

### 🌐 HTML Completo: `face.html`
*Ubicación del archivo:* [face.html](file:///c:/Users/TP-4B/OneDrive/Escritorio/Facial%20recognition/face.html)
```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BIOMETRIC- Sistema de Control de Asistencia</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="app-container">
        <!--  Barra lateral de navegación -->
        <aside id="sidebar" class="sidebar">
            <div class="sidebar-header">
                <div class="logo-box">
                    <i class="fa-solid fa-users"></i>
                </div>
                <div>
                    <h1>Asistec</h1>
                    <p>Control de Asistencia</p>
                </div>
            </div>

            <nav class="sidebar-nav">
                <div class="nav-section">
                    <h3>Panel Principal</h3>
                    <ul>
                        <li><a href="#inicio" class="nav-link active" data-section="inicio"><i class="fa-solid fa-home"></i> Inicio</a></li>
                        <li><a href="#dashboard" class="nav-link" data-section="dashboard"><i class="fa-solid fa-chart-line"></i> Dashboard</a></li>
                        <li><a href="#asistencia" class="nav-link" data-section="asistencia"><i class="fa-solid fa-video"></i> Asistencia en tiempo real</a></li>
                        <li><a href="#reportes" class="nav-link" data-section="reportes"><i class="fa-solid fa-file-text"></i> Reportes</a></li>
                    </ul>
                </div>

                <div class="nav-section">
                    <h3>Gestión Académica</h3>
                    <ul>
                        <li><a href="#cursos" class="nav-link" data-section="cursos"><i class="fa-solid fa-book"></i> Cursos</a></li>
                        <li><a href="#estudiantes" class="nav-link" data-section="estudiantes"><i class="fa-solid fa-graduation-cap"></i> Estudiantes</a></li>
                        <li><a href="#profesores" class="nav-link" data-section="profesores"><i class="fa-solid fa-chalkboard-user"></i> Profesores</a></li>
                        <li><a href="#sesiones" class="nav-link" data-section="sesiones"><i class="fa-solid fa-calendar-check"></i> Sesiones</a></li>
                    </ul>
                </div>

                <div class="nav-section">
                    <h3>Administración</h3>
                    <ul>
                        <li><a href="#usuarios" class="nav-link" data-section="usuarios"><i class="fa-solid fa-users-gear"></i> Usuarios</a></li>
                        <li><a href="#roles" class="nav-link" data-section="roles"><i class="fa-solid fa-shield-halved"></i> Roles y permisos</a></li>
                        <li><a href="#historial" class="nav-link" data-section="historial"><i class="fa-solid fa-clock-rotate-left"></i> Historial de cambios</a></li>
                        <li><a href="#configuracion" class="nav-link" data-section="configuracion"><i class="fa-solid fa-cog"></i> Configuración</a></li>
                    </ul>
                </div>
            </nav>

            <div class="sidebar-footer">
                <div class="user-mini">
                    <img src="https://picsum.photos/id/1005/200/200" alt="Administrador">
                    <div>
                        <p>Anabella Palacios</p>
                        <span>Administrador</span>
                    </div>
                    <i class="fa-solid fa-chevron-down"></i>
                </div>
            </div>
        </aside>

        <!--  Contenido principal -->
        <main class="main-content">
            <header class="top-bar">
                <button id="menu-toggle" class="menu-btn">
                    <i class="fa-solid fa-bars"></i>
                </button>

                <nav class="breadcrumbs" id="breadcrumbs">
                    <span>Inicio</span>
                </nav>

                <div class="top-bar-actions">
                    <div class="search-box">
                        <input type="text" id="buscadorGlobal" placeholder="Buscar en todo el sistema...">
                        <i class="fa-solid fa-magnifying-glass"></i>
                    </div>
                    <button class="icon-btn">
                        <i class="fa-solid fa-bell"></i>
                        <span class="badge">3</span>
                    </button>
                    <button class="icon-btn">
                        <i class="fa-solid fa-circle-question"></i>
                    </button>
                </div>
            </header>

            <div class="page-content">
                
                <!-- SECCIÓN: INICIO -->
                
                <section id="section-inicio" class="content-section active">
                    <h2 class="section-title">Bienvenido al Sistema Biometric</h2>
                    <p class="section-subtitle">Resumen general del control de asistencia y gestión académica</p>

                    <div class="stats-row">
                        <div class="stat-card">
                            <div class="stat-icon bg-blue">
                                <i class="fa-solid fa-users"></i>
                            </div>
                            <div>
                                <h3>1.248</h3>
                                <p>Estudiantes registrados</p>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon bg-green">
                                <i class="fa-solid fa-chalkboard-user"></i>
                            </div>
                            <div>
                                <h3>86</h3>
                                <p>Profesores activos</p>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon bg-purple">
                                <i class="fa-solid fa-book"></i>
                            </div>
                            <div>
                                <h3>124</h3>
                                <p>Cursos vigentes</p>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon bg-orange">
                                <i class="fa-solid fa-calendar-check"></i>
                            </div>
                            <div>
                                <h3>89.2%</h3>
                                <p>Asistencia promedio</p>
                            </div>
                        </div>
                    </div>

                    <div class="grid-layout mt-6">
                        <div class="col-main">
                            <div class="card">
                                <h3 class="card-title">Actividad reciente</h3>
                                <ul class="activity-list">
                                    <li>
                                        <i class="fa-solid fa-check-circle text-success"></i>
                                        <div>
                                            <p>Asistencia registrada: Fernando Ojeda - Programación I</p>
                                            <span>Hoy, 10:15 AM</span>
                                        </div>
                                    </li>
                                    <li>
                                        <i class="fa-solid fa-user-plus text-primary"></i>
                                        <div>
                                            <p>Nuevo estudiante agregado: Antonella Lobos</p>
                                            <span>Ayer, 03:45 PM</span>
                                        </div>
                                    </li>
                                    <li>
                                        <i class="fa-solid fa-video text-warning"></i>
                                        <div>
                                            <p>Sesión iniciada: Matemáticas - Grupo B</p>
                                            <span>Ayer, 08:00 AM</span>
                                        </div>
                                    </li>
                                    <li>
                                        <i class="fa-solid fa-file-export text-purple"></i>
                                        <div>
                                            <p>Reporte mensual generado correctamente</p>
                                            <span>05/07/2026</span>
                                        </div>
                                    </li>
                                    <li>
                                        <i class="fa-solid fa-user-shield text-gray-500"></i>
                                        <div>
                                            <p>Cambio de rol: Usuario Ana Ruiz → Profesor</p>
                                            <span>04/07/2026</span>
                                        </div>
                                    </li>
                                </ul>
                            </div>
                        </div>
                        <div class="col-side">
                            <div class="card">
                                <h3 class="card-title">Próximas sesiones</h3>
                                <ul class="schedule-list">
                                    <li>
                                        <span class="time">08:00 - 09:30</span>
                                        <div>
                                            <p>Matemáticas</p>
                                            <span>Prof. Gonzalo lufin</span>
                                        </div>
                                    </li>
                                    <li>
                                        <span class="time">10:00 - 11:30</span>
                                        <div>
                                            <p>Programación Web</p>
                                            <span>Prof. Carolina Moreno</span>
                                        </div>
                                    </li>
                                    <li>
                                        <span class="time">14:00 - 15:30</span>
                                        <div>
                                            <p>Base de Datos</p>
                                            <span>Prof. Carolina Moreno</span>
                                        </div>
                                    </li>
                                    <li>
                                        <span class="time">16:00 - 17:30</span>
                                        <div>
                                            <p>Ciencias</p>
                                            <span>Prof. Lucas Reyes</span>
                                        </div>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </section>

                
                <!-- SECCIÓN: DASHBOARD -->
                
                <section id="section-dashboard" class="content-section">
                    <h2 class="section-title">Panel de Control</h2>
                    <p class="section-subtitle">Estadísticas detalladas y tendencias del sistema</p>

                    <div class="grid-layout mt-6">
                        <div class="col-main">
                            <div class="card">
                                <h3 class="card-title">Evolución de asistencia mensual</h3>
                                <div class="chart-container">
                                    <canvas id="chartAsistencia"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-side">
                            <div class="card">
                                <h3 class="card-title">Distribución de estados</h3>
                                <div class="chart-container">
                                    <canvas id="chartEstados"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card mt-6">
                        <h3 class="card-title">Rendimiento por curso</h3>
                        <div class="table-container">
                            <table class="data-table" id="tablaCursosRendimiento">
                                <thead>
                                    <tr>
                                        <th>Curso</th>
                                        <th>Estudiantes</th>
                                        <th>Asistencia</th>
                                        <th>Presentes</th>
                                        <th>Ausentes</th>
                                        <th>Tardanzas</th>
                                        <th>Estado</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>Programación I</td>
                                        <td>45</td>
                                        <td><div class="progress-bar"><div style="width:94%"></div></div> 94%</td>
                                        <td>42</td>
                                        <td>2</td>
                                        <td>1</td>
                                        <td><span class="status active">Activo</span></td>
                                    </tr>
                                    <tr>
                                        <td>Matemáticas</td>
                                        <td>38</td>
                                        <td><div class="progress-bar"><div style="width:88%"></div></div> 88%</td>
                                        <td>33</td>
                                        <td>4</td>
                                        <td>1</td>
                                        <td><span class="status active">Activo</span></td>
                                    </tr>
                                    <tr>
                                        <td>Base de Datos</td>
                                        <td>42</td>
                                        <td><div class="progress-bar"><div style="width:91%"></div></div> 91%</td>
                                        <td>38</td>
                                        <td>3</td>
                                        <td>1</td>
                                        <td><span class="status active">Activo</span></td>
                                    </tr>
                                    <tr>
                                        <td>Ciencias</td>
                                        <td>50</td>
                                        <td><div class="progress-bar"><div style="width:85%"></div></div> 85%</td>
                                        <td>42</td>
                                        <td>6</td>
                                        <td>2</td>
                                        <td><span class="status active">Activo</span></td>
                                    </tr>
                                    <tr>
                                        <td>Redes de Computadoras</td>
                                        <td>36</td>
                                        <td><div class="progress-bar"><div style="width:92%"></div></div> 92%</td>
                                        <td>33</td>
                                        <td>2</td>
                                        <td>1</td>
                                        <td><span class="status active">Activo</span></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                
                <!--  SECCIÓN: ASISTENCIA EN TIEMPO REAL -->
               
                <section id="section-asistencia" class="content-section">
                    <h2 class="section-title">Asistencia en Tiempo Real</h2>
                    <p class="section-subtitle">Registro automático mediante reconocimiento facial</p>

                    <div class="grid-layout mt-6">
                        <div class="col-main">
                            <div class="card">
                                <div class="flex-between">
                                    <h3 class="card-title">Sesión actual: Programación </h3>
                                    <select class="form-control w-auto">
                                        <option>Cambiar sesión</option>
                                        <option>Matemáticas - Grupo B</option>
                                        <option>Base de Datos - Grupo C</option>
                                    </select>
                                </div>
                                <p class="text-sm text-gray-500 mb-4">Fecha: 07/07/2026 | Hora: 10:00 - 11:30 | Profesor: Fernando Ojeda</p>
                                
                                <div class="camera-container">
                                    <div class="camera-view">
                                        <i class="fa-solid fa-video fa-4x text-gray-300"></i>
                                        <p>Cámara activa - Reconocimiento en curso</p>
                                        <div class="mt-2 text-xs text-gray-400">Resolución: 1280x720 | FPS: 30</div>
                                    </div>
                                    <div class="camera-status">
                                        <span class="status-badge active">Activo</span>
                                        <p>Última detección: Fernando Ojeda</p>
                                        <p class="text-xs">Hora: 10:15:22</p>
                                        <p class="text-xs">Confianza: 98%</p>
                                        <div class="mt-4">
                                            <p class="text-sm font-medium">Total registrados: 32 / 45</p>
                                            <div class="progress-bar mt-1"><div style="width:71%"></div></div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-6">
                                <h3 class="card-title">Registro de asistencia hoy</h3>
                                <div class="table-container">
                                    <table class="data-table" id="tablaRegistroHoy">
                                        <thead>
                                            <tr>
                                                <th>Hora</th>
                                                <th>Estudiante</th>
                                                <th>ID</th>
                                                <th>Curso</th>
                                                <th>Confianza</th>
                                                <th>Estado</th>
                                                <th>Acciones</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td>10:15:22</td>
                                                <td>Fernando Ojeda</td>
                                                <td>20231045</td>
                                                <td>Programación </td>
                                                <td>98%</td>
                                                <td><span class="status present">Registrado</span></td>
                                                <td><button class="btn-icon"><i class="fa-solid fa-pen"></i></button></td>
                                            </tr>
                                            <tr>
                                                <td>10:16:05</td>
                                                <td>Carolina Moreno</td>
                                                <td>20231052</td>
                                                <td>Base de datos</td>
                                                <td>96%</td>
                                                <td><span class="status present">Registrado</span></td>
                                                <td><button class="btn-icon"><i class="fa-solid fa-pen"></i></button></td>
                                            </tr>
                                            <tr>
                                                <td>10:17:12</td>
                                                <td>Liza Molina</td>
                                                <td>20231061</td>
                                                <td>Base de datos</td>
                                                <td>92%</td>
                                                <td><span class="status present">Registrado</span></td>
                                                <td><button class="btn-icon"><i class="fa-solid fa-pen"></i></button></td>
                                            </tr>
                                            <tr>
                                                <td>10:18:45</td>
                                                <td>Lucas Reyes</td>
                                                <td>20231078</td>
                                                <td>Ciencias </td>
                                                <td>89%</td>
                                                <td><span class="status warning">Verificación</span></td>
                                                <td><button class="btn-icon"><i class="fa-solid fa-check"></i></button></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <div class="col-side">
                            <div class="card">
                                <h3 class="card-title">Resumen de sesión</h3>
                                <div class="stats-grid">
                                    <div class="stat-box bg-green">
                                        <p class="stat-value">32</p>
                                        <p class="stat-label">Presentes</p>
                                    </div>
                                    <div class="stat-box bg-red">
                                        <p class="stat-value">8</p>
                                        <p class="stat-label">Ausentes</p>
                                    </div>
                                    <div class="stat-box bg-yellow">
                                        <p class="stat-value">2</p>
                                        <p class="stat-label">Tardanzas</p>
                                    </div>
                                    <div class="stat-box bg-blue">
                                        <p class="stat-value">78%</p>
                                        <p class="stat-label">Asistencia</p>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-6">
                                <h3 class="card-title">Controles de sesión</h3>
                                <div class="controls-list">
                                    <button class="btn btn-primary w-full">Iniciar sesión</button>
                                    <button class="btn btn-secondary w-full">Pausar reconocimiento</button>
                                    <button class="btn btn-warning w-full">Reiniciar detección</button>
                                    <button class="btn btn-outline w-full">Exportar registro</button>
                                    <button class="btn btn-danger w-full">Finalizar sesión</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                
                <!--  SECCIÓN: REPORTES -->
                
                <section id="section-reportes" class="content-section">
                    <h2 class="section-title">Reportes y Estadísticas</h2>
                    <p class="section-subtitle">Genera, visualiza y descarga informes detallados</p>

                    <div class="card mt-6">
                        <h3 class="card-title">Filtros avanzados</h3>
                        <div class="filters-grid">
                            <div class="filter-group">
                                <label>Tipo de reporte</label>
                                <select class="form-control">
                                    <option>Asistencia por curso</option>
                                    <option>Asistencia por estudiante</option>
                                    <option>Reporte mensual</option>
                                    <option>Reporte semestral</option>
                                    <option>Comparativa de periodos</option>
                                </select>
                            </div>
                            <div class="filter-group">
                                <label>Fecha inicio</label>
                                <input type="date" class="form-control" value="2026-07-01">
                            </div>
                            <div class="filter-group">
                                <label>Fecha fin</label>
                                <input type="date" class="form-control" value="2026-07-07">
                            </div>
                            <div class="filter-group">
                                <label>Curso</label>
                                <select class="form-control">
                                    <option>Todos los cursos</option>
                                    <option>Programación </option>
                                    <option>Matemáticas </option>
                                    <option>Base de Datos</option>
                                    <option>Ciencias </option>
                                </select>
                            </div>
                            <div class="filter-group">
                                <label>Profesor</label>
                                <select class="form-control">
                                    <option>Todos los profesores</option>
                                    <option>Lucas Reyes</option>
                                    <option>Carolina Moreno</option>
                                    <option>Liza Molina</option>
                                </select>
                            </div>
                            <div class="filter-group">
                                <label>Formato de salida</label>
                                <select class="form-control">
                                    <option>PDF</option>
                                    <option>Excel</option>
                                    <option>CSV</option>
                                    <option>Imagen</option>
                                </select>
                            </div>
                        </div>
                        <div class="mt-4 flex-between">
                            <button class="btn btn-primary">Generar reporte</button>
                            <button class="btn btn-outline">Restablecer filtros</button>
                        </div>
                    </div>

                    <div class="card mt-6">
                        <h3 class="card-title">Reportes generados recientemente</h3>
                        <div class="table-container">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Nombre del reporte</th>
                                        <th>Fecha creación</th>
                                        <th>Generado por</th>
                                        <th>Formato</th>
                                        <th>Tamaño</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>Reporte mensual - Junio 2026</td>
                                        <td>01/07/2026 09:24</td>
                                        <td>Carlos Ramírez</td>
                                        <td>PDF</td>
                                        <td>2.4 MB</td>
                                        <td>
                                            <button class="btn-icon" title="Ver"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon" title="Descargar"><i class="fa-solid fa-download"></i></button>
                                            <button class="btn-icon" title="Eliminar"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>Asistencia ProgramaciónI - Semestre 1</td>
                                        <td>28/06/2026 15:12</td>
                                        <td>Carolina Moreno</td>
                                        <td>Excel</td>
                                        <td>1.8 MB</td>
                                        <td>
                                            <button class="btn-icon" title="Ver"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon" title="Descargar"><i class="fa-solid fa-download"></i></button>
                                            <button class="btn-icon" title="Eliminar"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>Estadísticas generales - 2026</td>
                                        <td>15/06/2026 11:45</td>
                                        <td>Lucas Reyes</td>
                                        <td>PDF</td>
                                        <td>3.1 MB</td>
                                        <td>
                                            <button class="btn-icon" title="Ver"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon" title="Descargar"><i class="fa-solid fa-download"></i></button>
                                            <button class="btn-icon" title="Eliminar"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                
                <!-- 🟦 SECCIÓN: GESTIÓN DE CURSOS -->
               
                <section id="section-cursos" class="content-section">
                    <h2 class="section-title">Gestión de Cursos</h2>
                    <p class="section-subtitle">Administra la información, grupos y asignación de profesores</p>

                    <div class="flex-between mt-6 mb-4">
                        <div class="search-box">
                            <input type="text" placeholder="Buscar curso por nombre o código...">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </div>
                        <button class="btn btn-primary">+ Nuevo Curso</button>
                    </div>

                    <div class="card">
                        <div class="table-container">
                            <table class="data-table" id="tablaCursos">
                                <thead>
                                    <tr>
                                        <th>Código</th>
                                        <th>Nombre del curso</th>
                                        <th>Profesor asignado</th>
                                        <th>Estudiantes</th>
                                        <th>Semestre</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>PROG-101</td>
                                        <td>Matematicas </td>
                                        <td>Gonzalo Lufin</td>
                                        <td>45</td>
                                        <td>1° 2026</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>MAT-202</td>
                                        <td>ProgramaciónI</td>
                                        <td>Carolina Moreno</td>
                                        <td>38</td>
                                        <td>1° 2026</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>BD-301</td>
                                        <td>Base de Datos</td>
                                        <td>Liza molina</td>    
                                        <td>42</td>
                                        <td>1° 2026</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>ING-103</td>
                                        <td>Ciencias</td>
                                        <td>Lucas Reyes</td>
                                        <td>50</td>
                                        <td>1° 2026</td>
                                        <td><span class="status inactive">Finalizado</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                
                <!-- SECCIÓN: GESTIÓN DE ESTUDIANTES -->
                
                <section id="section-estudiantes" class="content-section">
                    <h2 class="section-title">Gestión de Estudiantes</h2>
                    <p class="section-subtitle">Registro, edición y seguimiento de asistencia por alumno</p>

                    <div class="flex-between mt-6 mb-4">
                        <div class="filters-inline">
                            <input type="text" class="form-control w-250" placeholder="Buscar por nombre o ID...">
                            <select class="form-control w-150">
                                <option>Todos los cursos</option>
                                <option>Programación </option>
                                <option>Matemáticas </option>
                                <option>Base de Datos</option>
                                <option>Ciencias </option>
                            </select>
                            <select class="form-control w-150">
                                <option>Todos los estados</option>
                                <option>Activo</option>
                                <option>Inactivo</option>
                                <option>Ausente</option>
                            </select>
                        </div>
                        <button class="btn btn-primary">+ Nuevo Estudiante</button>
                    </div>

                    <div class="card">
                        <div class="table-container">
                            <table class="data-table" id="tablaEstudiantes">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Nombre completo</th>
                                        <th>Correo electrónico</th>
                                        <th>Curso asignado</th>
                                        <th>Asistencia</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>20231045</td>
                                        <td>Fernando Ojeda</td>
                                        <td>Fernando.Ojeda@sip.cl</td>
                                        <td>Programación </td>
                                        <td>94%</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-user-circle"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>20231052</td>
                                        <td>Gonzalo lufin</td>
                                        <td>maria.gonzalez@correo.edu</td>
                                        <td>Matemáticas </td>
                                        <td>88%</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-user-circle"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>20231061</td>
                                        <td>Pedro López Silva</td>
                                        <td>pedro.lopez@correo.edu</td>
                                        <td>Base de Datos</td>
                                        <td>91%</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-user-circle"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>20231078</td>
                                        <td>Ana Martínez Torres</td>
                                        <td>ana.martinez@correo.edu</td>
                                        <td>Inglés Técnico</td>
                                        <td>85%</td>
                                        <td><span class="status inactive">Inactivo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-user-circle"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                <!-- ============================================== -->
                <!-- 🟦 SECCIÓN: GESTIÓN DE PROFESORES -->
                <!-- ============================================== -->
                <section id="section-profesores" class="content-section">
                    <h2 class="section-title">Gestión de Profesores</h2>
                    <p class="section-subtitle">Administra los docentes de la institución y sus asignaciones</p>

                    <div class="flex-between mt-6 mb-4">
                        <div class="search-box">
                            <input type="text" placeholder="Buscar profesor por nombre o especialidad...">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </div>
                        <button class="btn btn-primary">+ Nuevo Profesor</button>
                    </div>

                    <div class="card">
                        <div class="table-container">
                            <table class="data-table" id="tablaProfesores">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Nombre completo</th>
                                        <th>Especialidad</th>
                                        <th>Cursos a cargo</th>
                                        <th>Correo</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>PROF-001</td>
                                        <td>Luis Martínez Ojeda</td>
                                        <td>Informática</td>
                                        <td>4</td>
                                        <td>luis.martinez@correo.edu</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>PROF-002</td>
                                        <td>Ana Ruiz Herrera</td>
                                        <td>Matemáticas</td>
                                        <td>3</td>
                                        <td>ana.ruiz@correo.edu</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>PROF-003</td>
                                        <td>Carlos Torres Silva</td>
                                        <td>Bases de Datos</td>
                                        <td>2</td>
                                        <td>carlos.torres@correo.edu</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>PROF-004</td>
                                        <td>Sofía Herrera Díaz</td>
                                        <td>Idiomas</td>
                                        <td>1</td>
                                        <td>sofia.herrera@correo.edu</td>
                                        <td><span class="status inactive">Licencia</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                <!-- ============================================== -->
                <!-- 🟦 SECCIÓN: GESTIÓN DE SESIONES -->
                <!-- ============================================== -->
                <section id="section-sesiones" class="content-section">
                    <h2 class="section-title">Gestión de Sesiones</h2>
                    <p class="section-subtitle">Programación, seguimiento y control de cada clase</p>

                    <div class="flex-between mt-6 mb-4">
                        <div class="filters-inline">
                            <input type="date" class="form-control w-150">
                            <select class="form-control w-200">
                                <option>Todos los cursos</option>
                                <option>Programación I</option>
                                <option>Matemáticas II</option>
                            </select>
                            <select class="form-control w-150">
                                <option>Todos los estados</option>
                                <option>Programada</option>
                                <option>En curso</option>
                                <option>Finalizada</option>
                            </select>
                        </div>
                        <button class="btn btn-primary">+ Nueva Sesión</button>
                    </div>

                    <div class="card">
                        <div class="table-container">
                            <table class="data-table" id="tablaSesiones">
                                <thead>
                                    <tr>
                                        <th>Fecha</th>
                                        <th>Horario</th>
                                        <th>Curso</th>
                                        <th>Profesor</th>
                                        <th>Total alumnos</th>
                                        <th>Asistencia</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>07/07/2026</td>
                                        <td>10:00 - 11:30</td>
                                        <td>Programación I</td>
                                        <td>Luis Martínez</td>
                                        <td>45</td>
                                        <td>78%</td>
                                        <td><span class="status ongoing">En curso</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-play text-success"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>07/07/2026</td>
                                        <td>08:00 - 09:30</td>
                                        <td>Matemáticas II</td>
                                        <td>Ana Ruiz</td>
                                        <td>38</td>
                                        <td>-</td>
                                        <td><span class="status scheduled">Programada</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-calendar-check text-primary"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-trash text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>06/07/2026</td>
                                        <td>14:00 - 15:30</td>
                                        <td>Base de Datos</td>
                                        <td>Carlos Torres</td>
                                        <td>42</td>
                                        <td>91%</td>
                                        <td><span class="status completed">Finalizada</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-file-export"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-eye"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                <!-- ============================================== -->
                <!-- 🟦 SECCIÓN: GESTIÓN DE USUARIOS -->
                <!-- ============================================== -->
                <section id="section-usuarios" class="content-section">
                    <h2 class="section-title">Gestión de Usuarios</h2>
                    <p class="section-subtitle">Control de accesos, cuentas y datos de acceso al sistema</p>

                    <div class="flex-between mt-6 mb-4">
                        <div class="search-box">
                            <input type="text" placeholder="Buscar por usuario o correo...">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </div>
                        <button class="btn btn-primary">+ Nuevo Usuario</button>
                    </div>

                    <div class="card">
                        <div class="table-container">
                            <table class="data-table" id="tablaUsuarios">
                                <thead>
                                    <tr>
                                        <th>Usuario</th>
                                        <th>Nombre completo</th>
                                        <th>Correo</th>
                                        <th>Rol asignado</th>
                                        <th>Último acceso</th>
                                        <th>Estado</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>carlosr</td>
                                        <td>Carlos Ramírez</td>
                                        <td>admin@asistec.edu</td>
                                        <td>Administrador</td>
                                        <td>07/07/2026 08:10</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-key"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-ban text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>luism</td>
                                        <td>Luis Martínez</td>
                                        <td>luis@asistec.edu</td>
                                        <td>Profesor</td>
                                        <td>07/07/2026 07:45</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-key"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-ban text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>anar</td>
                                        <td>Ana Ruiz</td>
                                        <td>ana@asistec.edu</td>
                                        <td>Profesor</td>
                                        <td>06/07/2026 16:20</td>
                                        <td><span class="status active">Activo</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-key"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-ban text-danger"></i></button>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>sofiah</td>
                                        <td>Sofía Herrera</td>
                                        <td>sofia@asistec.edu</td>
                                        <td>Profesor</td>
                                        <td>01/07/2026 09:05</td>
                                        <td><span class="status blocked">Bloqueado</span></td>
                                        <td>
                                            <button class="btn-icon"><i class="fa-solid fa-key"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-pen"></i></button>
                                            <button class="btn-icon"><i class="fa-solid fa-unlock text-success"></i></button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                <!-- ============================================== -->
                <!-- 🟦 SECCIÓN: ROLES Y PERMISOS -->
                <!-- ============================================== -->
                <section id="section-roles" class="content-section">
                    <h2 class="section-title">Roles y Permisos</h2>
                    <p class="section-subtitle">Define qué acciones puede realizar cada tipo de usuario</p>

                    <div class="grid-layout mt-6">
                        <div class="col-main">
                            <div class="card">
                                <h3 class="card-title">Configuración de permisos</h3>
                                <div class="form-group mb-4">
                                    <label class="font-medium">Seleccionar rol:</label>
                                    <select class="form-control w-250 mt-1" id="selectorRol">
                                        <option value="admin">Administrador</option>
                                        <option value="profesor">Profesor</option>
                                        <option value="estudiante">Estudiante</option>
                                        <option value="invitado">Invitado</option>
                                    </select>
                                </div>

                                <div class="permisos-grid">
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_ver" checked>
                                        <label for="permiso_ver">Ver información general</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_editar" checked>
                                        <label for="permiso_editar">Editar registros</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_eliminar" checked>
                                        <label for="permiso_eliminar">Eliminar registros</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_crear_usuarios" checked>
                                        <label for="permiso_crear_usuarios">Crear y gestionar usuarios</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_roles" checked>
                                        <label for="permiso_roles">Modificar roles y permisos</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_reportes" checked>
                                        <label for="permiso_reportes">Generar y descargar reportes</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_asistencia" checked>
                                        <label for="permiso_asistencia">Gestionar sesiones y asistencia</label>
                                    </div>
                                    <div class="permiso-item">
                                        <input type="checkbox" id="permiso_configuracion" checked>
                                        <label for="permiso_configuracion">Acceder a configuración del sistema</label>
                                    </div>
                                </div>

                                <div class="mt-6 flex-end">
                                    <button class="btn btn-primary">Guardar cambios de permisos</button>
                                </div>
                            </div>
                        </div>

                        <div class="col-side">
                            <div class="card">
                                <h3 class="card-title">Resumen de roles</h3>
                                <ul class="roles-list">
                                    <li>
                                        <span class="role-name">Administrador</span>
                                        <span class="role-count">2 usuarios</span>
                                        <p class="text-xs text-gray-500">Acceso total al sistema</p>
                                    </li>
                                    <li>
                                        <span class="role-name">Profesor</span>
                                        <span class="role-count">86 usuarios</span>
                                        <p class="text-xs text-gray-500">Gestiona cursos y asistencia</p>
                                    </li>
                                    <li>
                                        <span class="role-name">Estudiante</span>
                                        <span class="role-count">1248 usuarios</span>
                                        <p class="text-xs text-gray-500">Solo consulta de su información</p>
                                    </li>
                                    <li>
                                        <span class="role-name">Invitado</span>
                                        <span class="role-count">3 usuarios</span>
                                        <p class="text-xs text-gray-500">Acceso limitado solo a reportes públicos</p>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </section>

               
                <!-- SECCIÓN: HISTORIAL DE CAMBIOS -->
                
                <section id="section-historial" class="content-section">
                    <h2 class="section-title">Historial de Cambios</h2>
                    <p class="section-subtitle">Registro de todas las acciones realizadas en el sistema</p>

                    <div class="card mt-6">
                        <div class="filters-inline mb-4">
                            <input type="date" class="form-control w-180">
                            <select class="form-control w-200">
                                <option>Todas las acciones</option>
                                <option>Creación</option>
                                <option>Edición</option>
                                <option>Eliminación</option>
                                <option>Inicio de sesión</option>
                            </select>
                            <select class="form-control w-200">
                                <option>Todos los usuarios</option>
                                <option>Carlos Ramírez</option>
                                <option>Luis Martínez</option>
                                <option>Ana Ruiz</option>
                            </select>
                            <button class="btn btn-outline">Filtrar</button>
                        </div>

                        <div class="table-container">
                            <table class="data-table" id="tablaHistorial">
                                <thead>
                                    <tr>
                                        <th>Fecha y hora</th>
                                        <th>Usuario</th>
                                        <th>Acción realizada</th>
                                        <th>Módulo afectado</th>
                                        <th>Detalles</th>
                                        <th>Dirección IP</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>07/07/2026 08:22:15</td>
                                        <td>Carlos Ramírez</td>
                                        <td><span class="badge bg-success">Edición</span></td>
                                        <td>Usuarios</td>
                                        <td>Modificación de rol para usuario: sofiah</td>
                                        <td>192.168.1.45</td>
                                    </tr>
                                    <tr>
                                        <td>07/07/2026 08:10:02</td>
                                        <td>Carlos Ramírez</td>
                                        <td><span class="badge bg-info">Inicio sesión</span></td>
                                        <td>Acceso</td>
                                        <td>Ingreso exitoso al sistema</td>
                                        <td>192.168.1.45</td>
                                    </tr>
                                    <tr>
                                        <td>06/07/2026 16:20:44</td>
                                        <td>Ana Ruiz</td>
                                        <td><span class="badge bg-warning">Creación</span></td>
                                        <td>Sesiones</td>
                                        <td>Programada nueva sesión: Matemáticas II</td>
                                        <td>192.168.1.52</td>
                                    </tr>
                                    <tr>
                                        <td>06/07/2026 15:45:10</td>
                                        <td>Luis Martínez</td>
                                        <td><span class="badge bg-primary">Reporte</span></td>
                                        <td>Reportes</td>
                                        <td>Generado reporte de asistencia mensual</td>
                                        <td>192.168.1.38</td>
                                    </tr>
                                    <tr>
                                        <td>05/07/2026 11:30:05</td>
                                        <td>Carlos Ramírez</td>
                                        <td><span class="badge bg-danger">Eliminación</span></td>
                                        <td>Estudiantes</td>
                                        <td>Eliminado registro: ID 20231022</td>
                                        <td>192.168.1.45</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                
                <!-- SECCIÓN: CONFIGURACIÓN DEL SISTEMA -->
                
                
                <section id="section-configuracion" class="content-section">
                    <h2 class="section-title">Configuración del Sistema</h2>
                    <p class="section-subtitle">Ajustes generales, seguridad y preferencias de funcionamiento</p>

                    <div class="grid-layout mt-6">
                        <div class="col-main">
                            <div class="card">
                                <h3 class="card-title">Configuración General</h3>
                                <div class="form-grid">
                                    <div class="form-group">
                                        <label>Nombre de la institución</label>
                                        <input type="text" class="form-control" value="Instituto Tecnológico de Santiago">
                                    </div>
                                    <div class="form-group">
                                        <label>Año académico actual</label>
                                        <input type="text" class="form-control" value="2026">
                                    </div>
                                    <div class="form-group">
                                        <label>Semestre actual</label>
                                        <select class="form-control">
                                            <option value="1" selected>Primer Semestre</option>
                                            <option value="2">Segundo Semestre</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label>Zona horaria</label>
                                        <select class="form-control">
                                            <option selected>UTC-4 (Chile Continental)</option>
                                            <option>UTC-3</option>
                                            <option>UTC-5</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label>Porcentaje mínimo de asistencia aprobatoria</label>
                                        <input type="number" class="form-control" value="75" min="0" max="100">
                                        <p class="text-xs text-gray-500 mt-1">Porcentaje requerido para aprobar el curso</p>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-6">
                                <h3 class="card-title">Configuración de Reconocimiento Facial</h3>
                                <div class="form-grid">
                                    <div class="form-group">
                                        <label>Nivel de confianza mínimo</label>
                                        <input type="number" class="form-control" value="85" min="50" max="100">
                                        <p class="text-xs text-gray-500 mt-1">Porcentaje de coincidencia para registrar asistencia</p>
                                    </div>
                                    <div class="form-group">
                                        <label>Tiempo de tolerancia de tardanza (minutos)</label>
                                        <input type="number" class="form-control" value="15" min="0" max="60">
                                    </div>
                                    <div class="form-group">
                                        <label>Activar verificación manual para coincidencias bajas</label>
                                        <div class="switch-control mt-2">
                                            <input type="checkbox" id="verificacionManual" checked>
                                            <label for="verificacionManual">Habilitar</label>
                                        </div>
                                    </div>
                                    <div class="form-group">
                                        <label>Guardar capturas de reconocimiento</label>
                                        <div class="switch-control mt-2">
                                            <input type="checkbox" id="guardarCapturas" checked>
                                            <label for="guardarCapturas">Habilitar</label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="col-side">
                            <div class="card">
                                <h3 class="card-title">Seguridad</h3>
                                <div class="form-group mb-4">
                                    <label>Duración de sesión activa (minutos)</label>
                                    <input type="number" class="form-control" value="120" min="15" max="480">
                                </div>
                                <div class="form-group mb-4">
                                    <label>Requerir cambio de contraseña cada (días)</label>
                                    <input type="number" class="form-control" value="90" min="0" max="365">
                                </div>
                                <div class="form-group mb-4">
                                    <div class="switch-control">
                                        <input type="checkbox" id="autenticacion2fa" checked>
                                        <label for="autenticacion2fa">Autenticación de dos pasos</label>
                                    </div>
                                </div>
                                <div class="form-group mb-4">
                                    <div class="switch-control">
                                        <input type="checkbox" id="registroActividad" checked>
                                        <label for="registroActividad">Registrar todas las acciones en el historial</label>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-6">
                                <h3 class="card-title">Respaldo de Datos</h3>
                                <div class="form-group mb-4">
                                    <label>Frecuencia de respaldo automático</label>
                                    <select class="form-control">
                                        <option>Diario</option>
                                        <option selected>Semanal</option>
                                        <option>Mensual</option>
                                    </select>
                                </div>
                                <div class="form-group mb-4">
                                    <label>Almacenamiento de respaldos</label>
                                    <select class="form-control">
                                        <option selected>Servidor local</option>
                                        <option>Almacenamiento en la nube</option>
                                    </select>
                                </div>
                                <button class="btn btn-primary w-full">Realizar respaldo ahora</button>
                                <button class="btn btn-outline w-full mt-2">Restaurar respaldo</button>
                            </div>
                        </div>
                    </div>

                    <div class="mt-6 flex-end">
                        <button class="btn btn-outline mr-2">Restablecer valores por defecto</button>
                        <button class="btn btn-primary">Guardar toda la configuración</button>
                    </div>
                </section>
            </div>
        </main>
    </div>

    <script src="script.js"></script>
</body>
</html>
```

---

### 🎨 CSS Completo: `style.css`
*Ubicación del archivo:* [style.css](file:///c:/Users/TP-4B/OneDrive/Escritorio/Facial%20recognition/style.css)
```css
/* ============================================== */
/* Estilos generales */
/* ============================================== */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'Inter', sans-serif;
}

:root {
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --info: #3b82f6;
    --purple: #8b5cf6;
    --orange: #f97316;
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    --radius: 0.5rem;
    --radius-lg: 0.75rem;
}

body {
    background-color: var(--gray-100);
    color: var(--gray-800);
    line-height: 1.5;
}

.app-container {
    display: flex;
    min-height: 100vh;
}

/* ============================================== */
/* Barra lateral */
/* ============================================== */
.sidebar {
    width: 280px;
    background-color: white;
    border-right: 1px solid var(--gray-200);
    padding: 1.5rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
    box-shadow: var(--shadow);
}

.sidebar-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--gray-200);
}

.logo-box {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, var(--primary), var(--purple));
    border-radius: var(--radius);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.25rem;
}

.sidebar-header h1 {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--gray-900);
}

.sidebar-header p {
    font-size: 0.75rem;
    color: var(--gray-500);
}

.nav-section {
    margin-bottom: 1.5rem;
}

.nav-section h3 {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--gray-500);
    font-weight: 600;
    margin-bottom: 0.75rem;
    padding-left: 0.75rem;
}

.sidebar-nav ul {
    list-style: none;
}

.nav-link {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: var(--radius);
    color: var(--gray-600);
    text-decoration: none;
    font-weight: 500;
    transition: all 0.2s ease;
    margin-bottom: 0.25rem;
}

.nav-link:hover {
    background-color: var(--gray-100);
    color: var(--primary);
}

.nav-link.active {
    background-color: rgba(37, 99, 235, 0.1);
    color: var(--primary);
    font-weight: 600;
}

.sidebar-footer {
    margin-top: auto;
    padding-top: 1rem;
    border-top: 1px solid var(--gray-200);
}

.user-mini {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem;
    border-radius: var(--radius);
    cursor: pointer;
    transition: background 0.2s;
}

.user-mini:hover {
    background-color: var(--gray-100);
}

.user-mini img {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    object-fit: cover;
}

.user-mini p {
    font-weight: 500;
    font-size: 0.9rem;
}

.user-mini span {
    font-size: 0.75rem;
    color: var(--gray-500);
}

/* ============================================== */
/* Contenido principal */
/* ============================================== */
.main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.top-bar {
    background-color: white;
    padding: 1rem 2rem;
    border-bottom: 1px solid var(--gray-200);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    box-shadow: var(--shadow-sm);
}

.menu-btn {
    background: none;
    border: none;
    font-size: 1.25rem;
    color: var(--gray-600);
    cursor: pointer;
    display: none;
}

.breadcrumbs {
    font-size: 0.9rem;
    color: var(--gray-500);
}

.top-bar-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.search-box {
    position: relative;
}

.search-box input {
    padding: 0.5rem 1rem 0.5rem 2.25rem;
    border: 1px solid var(--gray-200);
    border-radius: var(--radius);
    background-color: var(--gray-50);
    width: 280px;
    font-size: 0.9rem;
}

.search-box input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
}

.search-box i {
    position: absolute;
    left: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--gray-400);
}

.icon-btn {
    position: relative;
    background: none;
    border: none;
    width: 36px;
    height: 36px;
    border-radius: var(--radius);
    font-size: 1rem;
    color: var(--gray-600);
    cursor: pointer;
    transition: background 0.2s;
}

.icon-btn:hover {
    background-color: var(--gray-100);
}

.badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background-color: var(--danger);
    color: white;
    font-size: 0.7rem;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
}

.page-content {
    padding: 2rem;
    flex: 1;
}

.content-section {
    display: none;
}

.content-section.active {
    display: block;
    animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.section-title {
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    color: var(--gray-900);
}

.section-subtitle {
    color: var(--gray-500);
    margin-bottom: 2rem;
}

/* ============================================== */
/* Componentes generales */
/* ============================================== */
.mt-6 { margin-top: 1.5rem; }
.mb-4 { margin-bottom: 1rem; }
.mr-2 { margin-right: 0.5rem; }
.w-auto { width: auto; }
.w-full { width: 100%; }
.w-150 { width: 150px; }
.w-180 { width: 180px; }
.w-200 { width: 200px; }
.w-250 { width: 250px; }

.flex-between {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}

.flex-end {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    flex-wrap: wrap;
}

.grid-layout {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.5rem;
}

.stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.25rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: white;
    padding: 1.5rem;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow);
    display: flex;
    align-items: center;
    gap: 1rem;
    border: 1px solid var(--gray-200);
}

.stat-icon {
    width: 56px;
    height: 56px;
    border-radius: var(--radius);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    color: white;
}

.bg-blue { background-color: var(--info); }
.bg-green { background-color: var(--success); }
.bg-purple { background-color: var(--purple); }
.bg-orange { background-color: var(--orange); }
.bg-red { background-color: var(--danger); }
.bg-yellow { background-color: var(--warning); }

.stat-card h3 {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.stat-card p {
    color: var(--gray-500);
    font-size: 0.9rem;
}

.card {
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow);
    padding: 1.5rem;
    border: 1px solid var(--gray-200);
}

.card-title {
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 1.25rem;
    color: var(--gray-800);
}

/* ============================================== */
/* Tablas y formularios */
/* ============================================== */
.table-container {
    overflow-x: auto;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table th,
.data-table td {
    padding: 0.875rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--gray-200);
    font-size: 0.9rem;
}

.data-table th {
    background-color: var(--gray-50);
    font-weight: 600;
    color: var(--gray-600);
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0.5px;
}

.data-table tr:hover {
    background-color: var(--gray-50);
}

.form-control {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--gray-200);
    border-radius: var(--radius);
    font-size: 0.9rem;
    background-color: white;
    transition: border 0.2s;
}

.form-control:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.btn {
    padding: 0.6rem 1.25rem;
    border-radius: var(--radius);
    font-weight: 500;
    font-size: 0.9rem;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.btn-primary {
    background-color: var(--primary);
    color: white;
}

.btn-primary:hover {
    background-color: var(--primary-dark);
}

.btn-secondary {
    background-color: var(--gray-200);
    color: var(--gray-700);
}

.btn-secondary:hover {
    background-color: var(--gray-300);
}

.btn-warning {
    background-color: var(--warning);
    color: white;
}

.btn-warning:hover {
    background-color: #d97706;
}

.btn-danger {
    background-color: var(--danger);
    color: white;
}

.btn-danger:hover {
    background-color: #dc2626;
}

.btn-outline {
    background-color: white;
    border: 1px solid var(--gray-300);
    color: var(--gray-700);
}

.btn-outline:hover {
    background-color: var(--gray-50);
    border-color: var(--gray-400);
}

.btn-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius);
    border: none;
    background: none;
    cursor: pointer;
    color: var(--gray-500);
    transition: all 0.2s;
    font-size: 0.9rem;
}

.btn-icon:hover {
    background-color: var(--gray-100);
    color: var(--primary);
}

/* ============================================== */
/* Estados y etiquetas */
/* ============================================== */
.status {
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: capitalize;
}

.status.active {
    background-color: rgba(16, 185, 129, 0.1);
    color: var(--success);
}

.status.inactive {
    background-color: rgba(107, 114, 128, 0.1);
    color: var(--gray-600);
}

.status.present {
    background-color: rgba(16, 185, 129, 0.1);
    color: var(--success);
}

.status.warning {
    background-color: rgba(245, 158, 11, 0.1);
    color: var(--warning);
}

.status.ongoing {
    background-color: rgba(59, 130, 246, 0.1);
    color: var(--info);
}

.status.scheduled {
    background-color: rgba(139, 92, 246, 0.1);
    color: var(--purple);
}

.status.completed {
    background-color: rgba(16, 185, 129, 0.1);
    color: var(--success);
}

.status.blocked {
    background-color: rgba(239, 68, 68, 0.1);
    color: var(--danger);
}

.badge {
    padding: 0.25rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    color: white;
}

.bg-success { background-color: var(--success); }
.bg-info { background-color: var(--info); }
.bg-warning { background-color: var(--warning); }
.bg-primary { background-color: var(--primary); }
.bg-danger { background-color: var(--danger); }

.progress-bar {
    width: 100%;
    height: 8px;
    background-color: var(--gray-200);
    border-radius: 9999px;
    overflow: hidden;
}

.progress-bar div {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--purple));
    border-radius: 9999px;
    transition: width 0.5s ease;
}

/* ============================================== */
/* Estilos específicos de secciones */
/* ============================================== */
.activity-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.activity-list li {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--gray-100);
}

.activity-list li:last-child {
    border: none;
    padding-bottom: 0;
}

.activity-list i {
    font-size: 1.25rem;
    margin-top: 0.15rem;
}

.activity-list p {
    font-weight: 500;
    margin-bottom: 0.25rem;
}

.activity-list span {
    font-size: 0.8rem;
    color: var(--gray-500);
}

.schedule-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.schedule-list li {
    display: flex;
    gap: 1rem;
    align-items: center;
    padding: 0.75rem;
    background-color: var(--gray-50);
    border-radius: var(--radius);
}

.schedule-list .time {
    font-weight: 600;
    color: var(--primary);
    font-size: 0.85rem;
    min-width: 90px;
}

.chart-container {
    height: 300px;
    width: 100%;
}

.camera-container {
    display: grid;
    grid-template-columns: 3fr 1fr;
    gap: 1.5rem;
    margin-top: 1rem;
}

.camera-view {
    background-color: var(--gray-900);
    border-radius: var(--radius);
    height: 350px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: white;
    gap: 1rem;
}

.camera-status {
    background-color: var(--gray-50);
    border-radius: var(--radius);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    border: 1px solid var(--gray-200);
}

.status-badge {
    padding: 0.35rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 600;
    text-align: center;
}

.status-badge.active {
    background-color: rgba(16, 185, 129, 0.1);
    color: var(--success);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
}

.stat-box {
    padding: 1rem;
    border-radius: var(--radius);
    color: white;
    text-align: center;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.stat-label {
    font-size: 0.85rem;
    opacity: 0.9;
}

.controls-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.filters-inline {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.filters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
}

.permisos-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
}

.permiso-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem;
    background-color: var(--gray-50);
    border-radius: var(--radius);
    border: 1px solid var(--gray-200);
}

.roles-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.roles-list li {
    padding: 1rem;
    background-color: var(--gray-50);
    border-radius: var(--radius);
    border: 1px solid var(--gray-200);
}

.role-name {
    font-weight: 600;
    display: block;
    margin-bottom: 0.25rem;
}

.role-count {
    font-size: 0.8rem;
    color: var(--gray-500);
    font-weight: 500;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1.25rem;
}

.switch-control {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
}

.text-sm { font-size: 0.875rem; }
.text-xs { font-size: 0.75rem; }
.text-gray-500 { color: var(--gray-500); }
.text-success { color: var(--success); }
.text-primary { color: var(--primary); }
.text-warning { color: var(--warning); }
.text-danger { color: var(--danger); }
.text-purple { color: var(--purple); }
.text-gray-300 { color: var(--gray-300); }
.text-gray-400 { color: var(--gray-400); }
.font-medium { font-weight: 500; }

/* ============================================== */
/* Responsive */
/* ============================================== */
@media (max-width: 1024px) {
    .grid-layout {
        grid-template-columns: 1fr;
    }

    .camera-container {
        grid-template-columns: 1fr;
    }

    .sidebar {
        position: fixed;
        left: -280px;
        top: 0;
        height: 100vh;
        z-index: 100;
        transition: left 0.3s ease;
    }

    .sidebar.open {
        left: 0;
    }

    .menu-btn {
        display: block;
    }

    .search-box input {
        width: 200px;
    }
}

@media (max-width: 640px) {
    .top-bar {
        padding: 1rem;
    }

    .page-content {
        padding: 1rem;
    }

    .search-box input {
        width: 150px;
    }

    .stats-row {
        grid-template-columns: 1fr;
    }
}
```

---

### ⚡ JS Original: `script.js`
*Ubicación del archivo:* [script.js](file:///c:/Users/TP-4B/OneDrive/Escritorio/Facial%20recognition/script.js)
```javascript
// ==============================================
// Navegación entre secciones
// ==============================================
const navLinks = document.querySelectorAll('.nav-link');
const sections = document.querySelectorAll('.content-section');
const breadcrumbs = document.getElementById('breadcrumbs');

navLinks.forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Quitar clase activa de todos los enlaces
        navLinks.forEach(l => l.classList.remove('active'));
        // Agregar clase activa al enlace actual
        this.classList.add('active');

        // Ocultar todas las secciones
        sections.forEach(sec => sec.classList.remove('active'));
        // Mostrar la sección correspondiente
        const sectionId = this.getAttribute('data-section');
        document.getElementById(`section-${sectionId}`).classList.add('active');

        // Actualizar ruta de navegación
        breadcrumbs.innerHTML = `<span>${this.textContent.trim()}</span>`;

        // Cerrar menú lateral en móviles
        if (window.innerWidth < 1024) {
            document.getElementById('sidebar').classList.remove('open');
        }
    });
});

// ==============================================
// Menú lateral para dispositivos móviles
// ==============================================
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.getElementById('sidebar');

menuToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
});

// ==============================================
// Gráficos con Chart.js
// ==============================================
document.addEventListener('DOMContentLoaded', () => {
    // Gráfico de evolución de asistencia
    const ctxAsistencia = document.getElementById('chartAsistencia');
    if (ctxAsistencia) {
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
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: {
                    y: {
                        beginAtZero: false,
                        min: 70,
                        max: 100
                    }
                }
            }
        });
    }

    // Gráfico de distribución de estados
    const ctxEstados = document.getElementById('chartEstados');
    if (ctxEstados) {
        new Chart(ctxEstados, {
            type: 'doughnut',
            data: {
                labels: ['Presentes', 'Ausentes', 'Tardanzas'],
                datasets: [{
                    data: [89.2, 8.5, 2.3],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    }

    // ==============================================
    // Cambio de permisos según rol seleccionado
    // ==============================================
    const selectorRol = document.getElementById('selectorRol');
    const permisos = document.querySelectorAll('.permiso-item input[type="checkbox"]');

    if (selectorRol) {
        const permisosPorRol = {
            admin: { ver: true, editar: true, eliminar: true, crear_usuarios: true, roles: true, reportes: true, asistencia: true, configuracion: true },
            profesor: { ver: true, editar: true, eliminar: false, crear_usuarios: false, roles: false, reportes: true, asistencia: true, configuracion: false },
            estudiante: { ver: true, editar: false, eliminar: false, crear_usuarios: false, roles: false, reportes: false, asistencia: false, configuracion: false },
            invitado: { ver: true, editar: false, eliminar: false, crear_usuarios: false, roles: false, reportes: true, asistencia: false, configuracion: false }
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

    // ==============================================
    // Buscador global
    // ==============================================
    const buscadorGlobal = document.getElementById('buscadorGlobal');
    if (buscadorGlobal) {
        buscadorGlobal.addEventListener('input', function() {
            const texto = this.value.toLowerCase().trim();
            if (texto.length < 2) return;
            
            console.log('Buscando:', texto);
            // Aquí se puede agregar lógica para filtrar tablas o resultados
        });
    }
});

// ==============================================
// Funciones de ejemplo para botones
// ==============================================
document.addEventListener('click', function(e) {
    // Botones de acción en tablas
    if (e.target.closest('.btn-icon')) {
        const accion = e.target.closest('button').title || e.target.closest('button').getAttribute('aria-label');
        if (accion) console.log('Acción seleccionada:', accion);
    }

    // Botones principales
    if (e.target.closest('.btn')) {
        const texto = e.target.closest('button').textContent.trim();
        if (texto) console.log('Botón presionado:', texto);
    }
});
```

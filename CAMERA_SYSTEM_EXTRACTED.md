# 📷 SISTEMA DE CÁMARA - CÓDIGO EXTRAÍDO
## Archivo de reconocimiento facial mediante cámara web

---

## 🎯 RESUMEN DE LA LÓGICA
El sistema funciona en 3 pasos:
1. **Captura**: JavaScript obtiene stream de cámara y captura un frame
2. **Envío**: Frame se convierte a base64 y se envía al servidor
3. **Procesamiento**: Python identifica el rostro y registra la asistencia

---

## 📁 ARCHIVOS INVOLUCRADOS

### 1️⃣ FRONTEND: `templates/index.html`
```html
{% extends "base.html" %}
{% block titulo %}Cámara{% endblock %}

{% block contenido %}
<h3>Marcar asistencia</h3>

<p>Mira a la cámara y presiona el botón.</p>

<!-- La cámara se muestra en este elemento video -->
<video id="video" width="400" height="300" autoplay></video>

<!-- Canvas oculto donde copiamos el frame para enviarlo -->
<canvas id="canvas" width="400" height="300" style="display:none;"></canvas>

<br>
<button onclick="capturar()">📸 Registrar asistencia</button>

<!-- Aquí aparece el resultado después del reconocimiento -->
<p id="resultado"></p>

<script>
// 1. Pedir permiso a la cámara y mostrar el video
const video  = document.getElementById("video");
const canvas = document.getElementById("canvas");

// Usar asincronía
navigator.mediaDevices.getUserMedia({ video: true })
  .then(function(stream) {
    video.srcObject = stream;
  })
  .catch(function(err) {
    document.getElementById("resultado").textContent = "Error con la cámara: " + err;
  });

// 2. Capturar un frame y enviarlo al servidor
function capturar() {
  // Copiar el frame actual del video al canvas
  canvas.getContext("2d").drawImage(video, 0, 0, 400, 300);

  // Convertir el canvas a base64 (imagen comprimida como JPEG)
  const imagenBase64 = canvas.toDataURL("image/jpeg");

  document.getElementById("resultado").textContent = "Procesando...";

  // Enviar al servidor con fetch (petición AJAX a POST /reconocer)
  fetch("/reconocer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ imagen: imagenBase64 })
  })
  .then(function(respuesta) { return respuesta.json(); })
  .then(function(datos) {
    if (!datos.ok) {
      document.getElementById("resultado").textContent = "❌ " + datos.mensaje;
      return;
    }
    if (datos.ya_registrado) {
      document.getElementById("resultado").textContent = "⚠ " + datos.nombre + " — ya registrado hoy";
      return;
    }
    document.getElementById("resultado").textContent =
      "✅ " + datos.nombre + " | " + datos.curso + " | " + datos.hora + " | " + datos.estado;
  })
  .catch(function(err) {
    document.getElementById("resultado").textContent = "Error de red: " + err;
  });
}
</script>
{% endblock %}
```

---

### 2️⃣ BACKEND: `server.py` - Secciones clave

#### 🔹 IMPORTACIONES NECESARIAS (líneas 74-98)
```python
import os       # para trabajar con rutas de archivos y carpetas
import base64   # para decodificar imágenes que vienen en texto
from datetime import date, datetime  # para manejar fechas y horas

import numpy as np          # matemáticas con vectores (los embeddings)
import pymysql              # conexión a MySQL
import pymysql.cursors      # para DictCursor

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, flash
)
from werkzeug.utils import secure_filename

from deepface import DeepFace  # Librería para reconocimiento facial
```

#### 🔹 CONFIGURACIÓN GLOBAL (líneas 110-141)
```python
app = Flask(__name__)
app.secret_key = "cambiar_en_produccion"

# Ruta absoluta a la carpeta donde guardamos las fotos de los alumnos
CARPETA_IMAGENES = os.path.join(os.path.dirname(__file__), "imagenes_conocidas")

# Solo aceptamos estos formatos de imagen
EXTENSIONES_OK = {"jpg", "jpeg", "png"}

# Umbral de distancia para reconocimiento (0.0-2.0)
# 0.40 = reconoce si la distancia es menor que 0.40
UMBRAL_DISTANCIA = 0.40
```

#### 🔹 LISTA EN MEMORIA (línea 199)
```python
# Esta lista vive en la memoria RAM del servidor mientras está corriendo
# Cada elemento es: {"alumno_id": 3, "embedding": array([...])}
rostros_en_memoria = []
```

#### 🔹 FUNCIÓN: Cargar rostros (líneas 202-259)
```python
def cargar_rostros():
    """
    Lee todas las fotos de imagenes_conocidas/ y convierte cada una
    en un embedding (512 números). Guarda los resultados en rostros_en_memoria.

    FLUJO:
      foto.jpg → RetinaFace detecta el rostro → ArcFace lo convierte
      en 512 números → guardamos esos números en la lista
    """
    rostros_en_memoria.clear()  # limpiamos antes de recargar

    if not os.path.exists(CARPETA_IMAGENES):
        print("⚠️  La carpeta imagenes_conocidas/ no existe todavía.")
        return

    for archivo in os.listdir(CARPETA_IMAGENES):
        # Verificar que sea una imagen válida
        ext = archivo.rsplit(".", 1)[-1].lower()
        if ext not in EXTENSIONES_OK:
            continue  # saltar archivos que no sean imágenes

        # El nombre del archivo es el id del alumno: "3.jpg" → id=3
        try:
            alumno_id = int(os.path.splitext(archivo)[0])
        except ValueError:
            continue

        ruta = os.path.join(CARPETA_IMAGENES, archivo)
        try:
            # DeepFace.represent() hace dos cosas:
            #   1. RetinaFace detecta y recorta el rostro
            #   2. ArcFace convierte ese rostro en 512 números (embedding)
            resultado = DeepFace.represent(
                img_path         = ruta,
                model_name       = "ArcFace",
                detector_backend = "retinaface",
                enforce_detection = True
            )
            embedding = np.array(resultado[0]["embedding"])
            rostros_en_memoria.append({
                "alumno_id": alumno_id,
                "embedding": embedding
            })
            print(f"  ✅ alumno_id={alumno_id} cargado correctamente")

        except Exception as e:
            print(f"  ❌ Error al procesar {archivo}: {e}")

    print(f"\n📸 Total de rostros en memoria: {len(rostros_en_memoria)}\n")
```

#### 🔹 FUNCIÓN: Distancia Coseno (líneas 262-290)
```python
def distancia_coseno(vector_a, vector_b):
    """
    Mide qué tan parecidos son dos embeddings (dos rostros).
    
    Resultado:
        0.0  →  vectores idénticos (misma persona, misma foto)
        0.4  →  misma persona, condiciones diferentes
        1.0  →  vectores muy diferentes (personas distintas)
    """
    return 1 - np.dot(vector_a, vector_b) / (
        np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    )
```

#### 🔹 FUNCIÓN: Identificar Rostro (líneas 293-352)
```python
def identificar_rostro(imagen_bytes):
    """
    Recibe bytes de una imagen (capturada desde la cámara),
    intenta encontrar un rostro y lo compara contra todos los
    rostros conocidos.

    Retorna: (alumno_id, mensaje)
      - Si reconoce: (3, "ok")
      - Si no:       (None, "Rostro no reconocido (distancia=0.523)")

    FLUJO:
      bytes de imagen
        → cv2 la convierte a matriz de píxeles
        → RetinaFace detecta el rostro
        → ArcFace extrae el embedding (512 números)
        → comparamos contra cada embedding en rostros_en_memoria
        → si la distancia mínima es menor al umbral → ¡reconocido!
    """
    if not rostros_en_memoria:
        return None, "No hay rostros registrados. Registra un alumno primero."

    try:
        # La imagen llega como bytes crudos.
        # OpenCV (cv2) la convierte a una matriz de píxeles
        import cv2
        arr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # Extraer el embedding de la imagen capturada
        resultado = DeepFace.represent(
            img_path         = img,
            model_name       = "ArcFace",
            detector_backend = "retinaface",
            enforce_detection = True
        )
        embedding_captura = np.array(resultado[0]["embedding"])

    except Exception as e:
        return None, f"No se detectó ningún rostro en la imagen: {e}"

    # Comparar el embedding capturado contra TODOS los conocidos
    # Nos quedamos con el que tenga la distancia más pequeña
    mejor_distancia = float("inf")
    mejor_id = None

    for rostro in rostros_en_memoria:
        d = distancia_coseno(embedding_captura, rostro["embedding"])
        if d < mejor_distancia:
            mejor_distancia = d
            mejor_id = rostro["alumno_id"]

    # Imprimir en terminal para ver qué está pasando
    print(f"  → Mejor coincidencia: alumno_id={mejor_id}, distancia={mejor_distancia:.4f}")
    print(f"  → Umbral: {UMBRAL_DISTANCIA} | ¿Reconocido?: {mejor_distancia <= UMBRAL_DISTANCIA}")

    if mejor_distancia <= UMBRAL_DISTANCIA:
        return mejor_id, "ok"
    else:
        return None, f"Rostro no reconocido (distancia={mejor_distancia:.3f}, umbral={UMBRAL_DISTANCIA})"
```

#### 🔹 RUTA: GET / (líneas 378-387)
```python
@app.route("/")
@app.route("/face")
def index():
    """
    GET /
    
    La página más simple: solo carga el template index.html,
    que tiene la cámara y el botón para capturar.
    """
    return render_template("index.html")
```

#### 🔹 RUTA: POST /reconocer (líneas 391-489)
```python
@app.route("/reconocer", methods=["POST"])
def reconocer():
    """
    POST /reconocer
    
    Esta es la ruta más importante. La llama el JavaScript de index.html
    cuando alguien presiona el botón.

    FLUJO COMPLETO:
      1. Recibe la imagen en formato JSON (base64)
      2. Decodifica el base64 a bytes de imagen
      3. Llama a identificar_rostro() → obtiene alumno_id
      4. Busca al alumno en MySQL
      5. Verifica si ya marcó asistencia hoy
      6. Si no marcó, inserta un registro nuevo
      7. Responde con JSON (el JavaScript lo muestra en pantalla)
    """
    # Obtener el JSON que envió el navegador
    datos = request.get_json()
    if not datos or "imagen" not in datos:
        return jsonify({"ok": False, "mensaje": "No se recibió ninguna imagen"})

    # La imagen viene como data URL: "data:image/jpeg;base64,/9j/4AAQ..."
    # Necesitamos solo la parte después de la coma (el base64 real)
    imagen_base64 = datos["imagen"].split(",")[1]
    imagen_bytes  = base64.b64decode(imagen_base64)

    # Intentar identificar el rostro
    alumno_id, mensaje = identificar_rostro(imagen_bytes)

    if alumno_id is None:
        # No se reconoció a nadie → devolver error
        return jsonify({"ok": False, "mensaje": mensaje})

    # Conectar a MySQL para guardar la asistencia
    conn = get_db()
    try:
        # Paso 1: obtener los datos del alumno reconocido
        with conn.cursor() as c:
            c.execute("SELECT * FROM alumnos WHERE id = %s", (alumno_id,))
            alumno = c.fetchone()

        if not alumno:
            return jsonify({"ok": False, "mensaje": "Alumno reconocido pero no está en la BD"})

        # Paso 2: verificar si ya marcó asistencia hoy
        with conn.cursor() as c:
            c.execute(
                "SELECT id FROM asistencias WHERE alumno_id = %s AND fecha = %s",
                (alumno_id, date.today())
            )
            ya_marco = c.fetchone()

        if ya_marco:
            return jsonify({
                "ok": True,
                "ya_registrado": True,
                "nombre": f"{alumno['nombre']} {alumno['apellido']}",
                "mensaje": "Ya registraste asistencia hoy"
            })

        # Paso 3: calcular el estado (presente o tarde)
        hora_actual = datetime.now().time()
        hora_limite = datetime.strptime("08:15", "%H:%M").time()
        estado = "tarde" if hora_actual > hora_limite else "presente"

        # Paso 4: insertar el registro de asistencia
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO asistencias (alumno_id, fecha, hora, estado) VALUES (%s, %s, %s, %s)",
                (alumno_id, date.today(), hora_actual, estado)
            )
        conn.commit()

        # Paso 5: responder con los datos para mostrar en pantalla
        return jsonify({
            "ok": True,
            "ya_registrado": False,
            "nombre": f"{alumno['nombre']} {alumno['apellido']}",
            "curso": alumno["curso"],
            "estado": estado,
            "hora": hora_actual.strftime("%H:%M"),
            "mensaje": f"¡Asistencia registrada! Estado: {estado}"
        })

    finally:
        # finally se ejecuta SIEMPRE, aunque haya un error
        # Garantizamos que la conexión se cierra
        conn.close()
```

---

## 🔄 FLUJO COMPLETO DE LA CÁMARA

### 1. Usuario accede a `/` o `/face`
```
Navegador → GET / → Flask retorna index.html
```

### 2. Página se carga en el navegador
```javascript
// JavaScript pide acceso a la cámara
navigator.mediaDevices.getUserMedia({ video: true })
  → Usuario aprueba permiso
  → Stream de cámara se muestra en <video>
```

### 3. Usuario presiona botón "📸 Registrar asistencia"
```javascript
// Se ejecuta función capturar()
canvas.drawImage(video, 0, 0)           // Copiar frame del video
imagenBase64 = canvas.toDataURL(...)    // Convertir a base64
fetch("/reconocer", { ... })            // Enviar al servidor
```

### 4. Servidor recibe la imagen
```python
@app.route("/reconocer", methods=["POST"])
def reconocer():
    imagen_base64 = datos["imagen"].split(",")[1]
    imagen_bytes = base64.b64decode(imagen_base64)
    alumno_id, mensaje = identificar_rostro(imagen_bytes)
    # ... guardar en BD ...
    return jsonify({...})
```

### 5. Servidor identifica el rostro
```python
def identificar_rostro(imagen_bytes):
    # Decodificar bytes a imagen
    img = cv2.imdecode(...)
    
    # Extraer embedding (512 números) usando DeepFace
    resultado = DeepFace.represent(img, ...)
    embedding_captura = resultado[0]["embedding"]
    
    # Comparar contra todos los embeddings guardados
    for rostro in rostros_en_memoria:
        d = distancia_coseno(embedding_captura, rostro["embedding"])
        if d < mejor_distancia:
            mejor_distancia = d
            mejor_id = rostro["alumno_id"]
    
    # Si distancia es menor al umbral → reconocido
    if mejor_distancia <= UMBRAL_DISTANCIA:
        return mejor_id, "ok"
```

### 6. Servidor guarda la asistencia
```python
INSERT INTO asistencias (alumno_id, fecha, hora, estado)
VALUES (3, 2024-01-15, 10:22:35, "presente")
```

### 7. JavaScript muestra el resultado
```javascript
// Si OK:
"✅ Juan García | Programación | 10:22 | presente"

// Si error:
"❌ Rostro no reconocido (distancia=0.523)"
```

---

## 🛠️ TECNOLOGÍAS UTILIZADAS

| Componente | Tecnología | Función |
|-----------|-----------|---------|
| **Frontend** | HTML + JavaScript | Captura stream de cámara y frame |
| **API Web** | Flask (Python) | Sirve página y endpoint POST |
| **IA/ML** | DeepFace | Extrae embeddings de rostros |
| **Detector** | RetinaFace | Detecta y recorta rostros |
| **Red Neural** | ArcFace | Convierte rostro en 512 números |
| **Visión Computacional** | OpenCV (cv2) | Decodifica bytes a imagen |
| **Matemáticas** | NumPy | Calcula distancia coseno |
| **Base de Datos** | MySQL | Guarda asistencia |

---

## 🎛️ PARÁMETROS CONFIGURABLES

```python
UMBRAL_DISTANCIA = 0.40  # Ajustar para más o menos estricto
# 0.30 = MÁS ESTRICTO (rechaza más)
# 0.50 = MÁS PERMISIVO (acepta más)

# Hora límite para marcar como "tarde"
hora_limite = datetime.strptime("08:15", "%H:%M").time()

# Dimensiones del video en el navegador
width="400" height="300"

# Formato de imagen para captura
canvas.toDataURL("image/jpeg")  # Puedes cambiar a "image/png"
```

---

## 📝 RESUMEN DE ARCHIVOS

| Archivo | Líneas | Función |
|---------|--------|---------|
| `templates/index.html` | 1-69 | Frontend: HTML + JavaScript de captura |
| `server.py` | 74-98 | Importaciones |
| `server.py` | 110-141 | Configuración |
| `server.py` | 199 | Lista en memoria |
| `server.py` | 202-259 | Función `cargar_rostros()` |
| `server.py` | 262-290 | Función `distancia_coseno()` |
| `server.py` | 293-352 | Función `identificar_rostro()` |
| `server.py` | 378-387 | Ruta GET `/` |
| `server.py` | 391-489 | Ruta POST `/reconocer` |

---

## 🚀 PARA USAR ESTE CÓDIGO

1. **Asegúrate que los embeddings están cargados:**
   ```python
   cargar_rostros()  # Se ejecuta al iniciar el servidor
   ```

2. **Usuario accede a la cámara:**
   ```
   http://localhost:5000
   ```

3. **Debe dar permiso a la cámara en el navegador**

4. **Presiona botón y el sistema captura/reconoce**

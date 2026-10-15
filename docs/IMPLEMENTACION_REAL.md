# Hoja de ruta: de la simulación al equipo real

Cada paso sustituye **una** simulación por su implementación real, es
independiente de los demás y se verifica solo.

| Paso | Estado |
|---|---|
| 1. Cámara real | ✅ hecho — `adapters/camara_opencv.py` |
| 2. Detección local con YOLO | ✅ hecho — `adapters/detector_yolo.py` |
| 3. Placas reales | ✅ hecho — `enlace_serie` (USB) y `enlace_tcp` (WiFi), varias a la vez (falta probarlo con una placa delante) |
| 4. Voz | ✅ hecho — `adapters/voz_edge_tts.py` |
| 5. Detección por API | ⬜ pendiente |
| 6. Selección de la ROI sobre el vídeo | ⬜ pendiente |
| 7. Pendientes menores | ⬜ |

Las secciones de los pasos ya hechos se conservan porque documentan **por qué**
están escritos así y qué hay que mirar si fallan.

---

## 1. Cámara real — `adapters/camara_opencv.py` ✅

```bash
uv pip install -e ".[vision]"
```

Implementar `FuenteVideo` con `cv2.VideoCapture(config.indice)`.

Dos cosas que no son obvias:

- **Descartar el búfer.** La cámara entrega cuadros almacenados; si se llama
  directamente a `read()` se fotografía la escena de hace medio segundo, es
  decir, antes de que el usuario terminara de colocar los objetos. En
  `capturar_estable` hay que llamar `grab()` tantas veces como diga
  `cuadros_a_descartar` y solo entonces `retrieve()`.
- **El orden de los canales.** OpenCV entrega BGR y todo el resto del programa
  asume RGB. Hay que convertir con `cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)` al
  salir del adaptador, no más adelante.

En Windows conviene abrir con `cv2.CAP_DSHOW` para que la cámara arranque en
menos de un segundo.

**Verificación**: `modo = "real"`, `detector.backend = "mock"`. El panel VIDEO EN
VIVO muestra la webcam y CAPTURA congela lo que había en el momento de pulsar.

---

## 2. Detección local — `adapters/detector_yolo.py` ✅

```bash
uv pip install -e ".[yolo]"
```

Implementar `Detector` con `ultralytics.YOLO(config.pesos)`. En `cargar()` se
descargan los pesos la primera vez (unos 6 MB para YOLO11n) y conviene hacer una
inferencia en blanco para que la primera captura real no pague el arranque.

De `resultado.boxes` salen `cls`, `conf` y `xyxy`; hay que pasar las cajas a
`Rect(x, y, ancho, alto)` y el nombre de clase a través de `modelo.names[cls]`,
que son justamente los nombres de COCO que `services/lexico.py` ya sabe
traducir.

`torch` ocupa unos 2 GB. Si el disco es un problema, exportar el modelo a ONNX y
usar `onnxruntime` da un paquete mucho más pequeño a cambio de algo de trabajo.

**Verificación**: poner objetos reales sobre la mesa y comprobar que las cajas
caen donde deben y que el tiempo de inferencia que muestra la insignia es
plausible (100–400 ms sin GPU).

---

## 3. Placas reales — `adapters/enlace_serie.py` y `enlace_tcp.py` ✅

```bash
# pyserial ya está en las dependencias base
```

Hecho en tres capas: `enlace_lineas.py` tiene el protocolo (cola de salida,
hilo lector, vigilante con `PING`, reconexión) y `enlace_serie.py` /
`enlace_tcp.py` solo el medio. `enlace_multiple.py` permite varias placas a la
vez. Ver `docs/ARQUITECTURA.md`.

Enumerar siempre con `serial.tools.list_ports.comports()`. No codificar `COM3`.

En Linux, el usuario debe pertenecer al grupo que posee el dispositivo
(`uucp` o `dialout` según la distribución) o la apertura falla con permiso
denegado.

Antes de nada, cargar `arduino/vision_contador/vision_contador.ino` desde el IDE
de Arduino y comprobar el cableado que describe la cabecera del sketch.

**Verificación**: desde la consola serial de la aplicación, enviar a mano
`LCD1:Hola` y `LED:VERDE`, y ver que la pantalla y el LED responden. Después,
presionar el pulsador físico y comprobar que llega `BTN` y arranca una captura.

---

## 4. Voz — `adapters/voz_edge_tts.py` ✅

```bash
uv pip install -e ".[voz]"
```

`edge-tts` es asíncrono y devuelve un MP3. El patrón que funciona:

1. Calcular un hash de la frase y mirar si ya existe en `cache/voz/`.
2. Si no existe, sintetizarlo con `edge_tts.Communicate(frase, voz)` y guardarlo.
3. Reproducirlo con `QMediaPlayer` de PySide6, que ya está instalado y evita una
   dependencia más.

El caché no es una optimización: en el aula la misma frase se repite mucho y no
conviene que cada captura dependa de que la red responda.

`descripcion` debe devolver `"edge-tts · desde caché"` o `"edge-tts · sintetizada"`
según el caso, porque la tarjeta FRASE GENERADA muestra ese texto.

**Respaldo sin red**: si `edge_tts` falla, caer a `pyttsx3`. La voz es
claramente sintética, pero la demostración no se cae.

---

## 5. Detección por API — `adapters/detector_api.py` ⬜

```bash
uv pip install -e ".[api]"
export ANTHROPIC_API_KEY=...
```

Codificar la imagen preprocesada en PNG (ya hay `services/imagen_io.guardar_png`)
y pedir al modelo que devuelva JSON con una lista de `{clase, confianza, caja}`.

Es útil como punto de comparación en el informe —contrastar un detector local
especializado contra un modelo general— pero no debería ser el camino principal:
la latencia es de 1 a 3 segundos y depende de la red.

**La clave se lee de la variable de entorno**, nunca del archivo de
configuración, que acaba en el repositorio.

---

## 6. Selección de la región de interés sobre el video

Hoy el botón «Definir región en el video» solo deja constancia en la consola.
Falta: poner `VisorImagen` en modo selección, capturar `mousePressEvent`,
`mouseMoveEvent` y `mouseReleaseEvent`, dibujar el rectángulo mientras se
arrastra y convertir las coordenadas del widget a coordenadas de la imagen con
la inversa de `_a_widget`.

---

## 7. Pendientes menores

- **`preproc_opencv`**: la cadena en numpy tarda unos 200 ms por captura, lo que
  sobra para una captura por pulsación. Solo hace falta si alguna vez se quiere
  preprocesar el video en vivo a 30 FPS.
- **Transformación geométrica real**: hoy corrige una inclinación fija de 1.8°.
  Lo correcto es calibrar con un patrón de tablero de ajedrez
  (`cv2.findChessboardCorners`) y aplicar la homografía resultante.
- **Empaquetado para Windows**: `PyInstaller --windowed` produce un ejecutable;
  hay que incluir a mano los pesos de YOLO y el sketch.

---

## Observaciones de la primera prueba en modo real

Medido con la webcam de la laptop (1280×720, 10 FPS reales) y YOLO11n en CPU:

| Operación | Tiempo |
|---|---|
| Abrir la cámara (con calentamiento) | 1,5 s |
| Cargar YOLO11n y hacer la inferencia en blanco | 5 s, en segundo plano al arrancar |
| `capturar_estable` (descarta 5 cuadros a 10 FPS) | 0,5 s |
| Preprocesamiento completo en numpy | 0,2 s |
| Inferencia | 50–70 ms |
| Síntesis de voz, primera vez | 1,5 s |
| Síntesis de voz, desde caché | 0,2 ms |

### La máscara de ROI le cuesta confianza al detector

Sobre la misma imagen, la mejor confianza de detección fue:

| Entrada | Mejor confianza |
|---|---|
| Imagen original | 0,63 |
| Tras la transformación geométrica | 0,69 |
| Tras el suavizado | 0,70 |
| **Tras la máscara de región** | **0,57** |
| Cadena completa con la ROI cubriendo toda la imagen | 0,70 |

Oscurecer al 38 % lo que queda fuera de la región le da al modelo una imagen que
no se parece a nada de su entrenamiento, y con el umbral en 0,50 la detección
queda al filo: en una de las pruebas el mismo objeto pasó de detectarse a no
detectarse entre dos capturas seguidas.

No es un fallo: es exactamente el tipo de compromiso que el informe del curso
debería discutir. Hay tres palancas, todas ya expuestas en la interfaz:

- **Desactivar la casilla «Máscara de región de interés»** en la pestaña
  Preprocesamiento y comparar. Para eso está.
- **Bajar la confianza mínima** de 0,50 a 0,35.
- **Ampliar la región de interés**. La que viene por defecto
  (`x=120, y=80, ancho=1040, alto=560`) sale del diseño original, pensado para
  una mesa vista desde arriba; con la cámara frontal de una laptop recorta
  demasiado.

Si se quisiera lo mejor de ambos mundos, lo correcto sería **recortar** a la
región en vez de atenuarla, y volver a situar las cajas en coordenadas de la
imagen completa al dibujarlas. Queda apuntado como posible mejora, no está
implementado.

### Puertos serie fantasma en Linux

`serial.tools.list_ports.comports()` devuelve en esta máquina 32 puertos
`/dev/ttyS*` del chipset que no existen físicamente. `puertos_del_sistema()` los
filtra quedándose solo con los que declaran fabricante USB, y ordena primero los
VID conocidos de Arduino, CH340, FTDI y CP210x. Sin ese filtro el desplegable es
inservible y la autoselección elige un puerto fantasma.

---

## Lo que queda por verificar con hardware

Todo lo de arriba está probado salvo lo que es físicamente imposible probar sin
las placas. Conviene saber exactamente dónde está esa frontera:

| Pieza | Cómo está probada | Qué falta |
|---|---|---|
| `enlace_tcp.py` | Contra un servidor TCP real en `127.0.0.1` que habla el protocolo (`tests/placa_falsa.py`): conexión, saludo `ID`, órdenes, acuses, `BTN` espontáneo y pérdida de conexión | Nada del adaptador. Falta el firmware del ESP32 |
| `enlace_serie.py` | Contra un pseudoterminal (`os.openpty`), que es un dispositivo de verdad que pyserial abre como puerto | El comportamiento del DTR al abrir, que reinicia la placa |
| `enlace_multiple.py` | Reparto, tolerancia a una placa caída y deduplicación del `BTN` | Nada |
| `vision_contador.ino` | `tests/test_protocolo.py` comprueba que reconoce todas las órdenes y emite todas las respuestas | Compilarlo y cargarlo |
| `vision_contador_esp32.ino` | Lo mismo | **Todo**: no se ha compilado nunca |

La prueba de humo con dos placas (una serie inexistente y un ESP32 simulado por
TCP) recorre el pipeline completo y confirma que el ESP32 recibe
`ID`, `PENSANDO`, `LED:AMARILLO`, `LCD1:`, `LCD2:`, `LED:ROJO` y `PING`, y que
el Arduino caído no impide nada.

### Al recibir la primera placa

1. Cargar `arduino/vision_contador/vision_contador.ino` desde el IDE de Arduino.
2. `uv run vision-contador --real`.
3. En la consola serial: `LCD1:Hola`, `LED:VERDE`. La pantalla y el LED deben responder.
4. Pulsar el pulsador físico: debe llegar `BTN` y arrancar una captura.
5. Desenchufar el cable a mitad: la interfaz debe pasar a desconectada sola y
   reconectar al volver a enchufarlo.

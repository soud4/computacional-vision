# Visión Contador

Sistema académico de **detección, clasificación y conteo de objetos** para el curso de
Procesamiento Digital de Imágenes.

La laptop concentra todo el procesamiento: captura la imagen con la webcam, la mejora con técnicas
de PDI, ejecuta el detector, cuenta los objetos por clase, genera la frase de respuesta, la
reproduce por los parlantes y muestra la interfaz gráfica. El **Arduino actúa únicamente como
actuador e interfaz física**: lee el pulsador, muestra mensajes en la LCD 16x2 y enciende los LEDs
según las órdenes que recibe por el puerto serial.

## Estado actual

| Pieza | Modo demo | Modo real |
|---|---|---|
| Cámara | escena sintética | ✅ `camara_opencv` — webcam, cámara de red o imagen subida |
| Preprocesamiento | — | ✅ `preproc_numpy` — las cinco técnicas, implementadas de verdad |
| Detección | 4 objetos fijos | ✅ `detector_yolo` — YOLO11n local |
| Placas actuadoras | puerto simulado | ✅ `enlace_serie` (USB) y `enlace_tcp` (WiFi), varias a la vez |
| Voz | sin audio | ✅ `voz_edge_tts` — con caché en disco |
| Detección por API | — | ⬜ pendiente (`docs/IMPLEMENTACION_REAL.md`) |
| Selección de ROI sobre el vídeo | — | ⬜ pendiente |

El **modo demo** no necesita hardware, ni modelos descargados, ni conexión a internet: sirve para
enseñar la interfaz y para desarrollar sin la cámara delante.

Lo que queda por hacer está en [`docs/IMPLEMENTACION_REAL.md`](docs/IMPLEMENTACION_REAL.md).

## Requisitos

- Python 3.12 o 3.13 (no 3.14 todavía: faltan ruedas de `torch`/`ultralytics`).
- [`uv`](https://docs.astral.sh/uv/) para gestionar el entorno.

## Puesta en marcha

### Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # si no tienes uv
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run vision-contador
```

### Windows

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run vision-contador
```

## Uso

```bash
uv run vision-contador              # modo demo (todo simulado)
uv run vision-contador --real       # webcam, YOLO, Arduino y voz reales
uv run vision-contador --estado b   # abre forzando la variante "Arduino desconectado"
```

El modo real necesita las dependencias opcionales:

```bash
uv pip install -e ".[vision,yolo,voz]"
```

La primera vez descarga los pesos de YOLO11n (5,4 MB) y tarda unos segundos en cargar el modelo;
se hace en segundo plano, con la ventana ya abierta. La captura funciona aunque no haya Arduino
conectado.

### Permisos del puerto serie en Linux

Abrir el puerto falla con «permiso denegado» si el usuario no pertenece al grupo dueño del
dispositivo. En Arch y derivadas ese grupo es `uucp`; en Debian y Ubuntu, `dialout`:

```bash
sudo usermod -aG uucp $USER     # luego hay que volver a iniciar sesión
```

### De dónde sale la imagen

La fuente se elige sin reiniciar la aplicación y el resto del flujo no cambia:

- **Subir una imagen.** En el desplegable del botón **Capturar** → «Subir imagen…» (o `Ctrl+O`, o
  arrastrando el archivo a la ventana). La imagen se procesa al momento y queda como fuente
  activa; «Volver a la cámara» deshace el cambio. Útil para repetir un caso difícil o preparar la
  demostración sin montar la mesa.
- **Otra cámara.** Pestaña **Fuente** → «Buscar» lista las cámaras conectadas (en Linux, los
  `/dev/video*` con su nombre). **Probar** abre la fuente y dice a qué resolución responde antes
  de cambiarla.
- **La cámara del celular**, que suele ser mejor que la webcam de la laptop. Va por WiFi, no por
  Bluetooth: instale *IP Webcam* o *DroidCam* en el teléfono, conecte ambos equipos a la misma
  red y pegue en la pestaña Fuente la dirección que muestra la aplicación del teléfono, del
  estilo `http://192.168.1.40:8080/video`. No hace falta instalar nada en la laptop.

La cámara elegida se guarda en `config/usuario.toml` y vuelve a usarse en la siguiente sesión; la
imagen subida no, porque es siempre una elección del momento.

Atajos de teclado para la presentación en aula:

| Tecla | Acción |
|---|---|
| `Espacio` | Capturar (equivale al pulsador físico) |
| `Ctrl+O` | Subir una imagen y procesarla |
| `F1` | Estado normal — listo |
| `F2` | Forzar el estado "Pensando…" |
| `F3` | Forzar "Arduino desconectado" |
| `F4` | Forzar "sin detecciones" |

## Dependencias opcionales

Las bibliotecas pesadas están separadas para que la instalación base sea rápida:

```bash
uv pip install -e ".[vision]"   # OpenCV: cámara y preprocesamiento reales
uv pip install -e ".[yolo]"     # ultralytics + torch: detección local
uv pip install -e ".[voz]"      # edge-tts: síntesis de voz
uv pip install -e ".[api]"      # detección por API en la nube
```

## Estructura

```
src/vision_contador/
├── core/        modelos, configuración y el orquestador del flujo
├── ports/       interfaces abstractas (cámara, preproceso, detector, Arduino, voz)
├── adapters/    implementaciones: una simulada y una real por cada puerto
├── services/    conteo, generación de la frase, histogramas, registro CSV
└── ui/          interfaz PySide6
arduino/         sketch del Arduino que implementa el protocolo serial
docs/            protocolo serial, mockups de referencia y hoja de ruta
```

## Documentación

- [`docs/protocolo.md`](docs/protocolo.md) — contrato laptop ↔ placas actuadoras.
- [`docs/PLAN_ESP32.md`](docs/PLAN_ESP32.md) — añadir un ESP32: topologías, pines y compras.
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — puertos y adaptadores, hilos, máquina de estados.
- [`docs/IMPLEMENTACION_REAL.md`](docs/IMPLEMENTACION_REAL.md) — cómo reemplazar cada simulación.

# Arquitectura

## El problema que resuelve

El sistema tiene que crecer sin que cada funcionalidad nueva estorbe a las
demás: hoy la detección es simulada y mañana será YOLO local, luego habrá que
poder comparar contra una API en la nube, y la cámara, la voz y el Arduino
siguen el mismo camino. Si la interfaz llamara directamente a OpenCV o a
`pyserial`, cada uno de esos cambios obligaría a tocar la ventana.

La respuesta es una arquitectura de **puertos y adaptadores**: el núcleo define
qué necesita, y cada recurso externo entra por una interfaz.

```
                 ┌──────────────────────────────────┐
                 │              ui/                 │   PySide6
                 │  ventana_principal · widgets     │
                 └───────────────┬──────────────────┘
                                 │ solo habla con el núcleo
                 ┌───────────────▼──────────────────┐
                 │             core/                │   sin Qt, sin OpenCV,
                 │  modelos · config · pipeline     │   sin pyserial
                 │             services/            │
                 │  contador · frase · histograma   │
                 └───────────────┬──────────────────┘
                                 │ depende de abstracciones
                 ┌───────────────▼──────────────────┐
                 │             ports/               │   FuenteVideo
                 │   cinco interfaces abstractas    │   Preprocesador
                 └───────────────┬──────────────────┘   Detector
                                 │ las implementan       EnlaceArduino
                 ┌───────────────▼──────────────────┐   SintetizadorVoz
                 │           adapters/              │
                 │   una versión simulada y una     │
                 │   real por cada puerto           │
                 └──────────────────────────────────┘
```

`fabrica.py` es el único módulo que conoce ambos lados: lee la configuración y
decide qué adaptador instanciar. Cambiar de la simulación al equipo real es
cambiar `modo = "demo"` por `modo = "real"` en `config/default.toml`.

## Los cinco puertos

| Puerto | Qué abstrae | Simulado | Real |
|---|---|---|---|
| `FuenteVideo` | De dónde salen los cuadros | `camara_mock` | `camara_opencv`, `fuente_imagen` |
| `Preprocesador` | La cadena de técnicas de PDI | — | `preproc_numpy` |
| `Detector` | Detección y clasificación | `detector_mock` | `detector_yolo`, `detector_api` |
| `EnlaceArduino` | El canal con las placas | `arduino_mock` | `enlace_serie`, `enlace_tcp` |
| `SintetizadorVoz` | La voz por los parlantes | `voz_mock` | `voz_edge_tts` |

## La fuente de vídeo se cambia en caliente

La ventana construye sus dependencias una sola vez y el hilo de vídeo lee de esa
misma instancia desde otro hilo, así que la cámara no se puede sustituir sin más.
Lo que guarda `Dependencias.camara` es un `fuente_conmutable.FuenteConmutable`:
una envoltura que delega en la fuente activa y la reemplaza bajo cerrojo.

```
         FuenteConmutable          lo que ve el resto del programa
                 │
    ┌────────────┼────────────┐
camara_opencv  camara_opencv  fuente_imagen
 (webcam)      (URL del       (una imagen
               celular)        subida)
```

`cambiar()` abre la fuente nueva **antes** de cerrar la anterior: si la cámara de
red no responde, la que estaba funcionando sigue en pie. Un destino con esquema
(`http://`, `rtsp://`) es una cámara de red y se abre con `CAP_ANY` y un tiempo
límite; un índice o un `/dev/video*` van con el backend nativo del sistema.

## Un protocolo, varios transportes, varias placas

El enlace con las placas actuadoras está partido en tres capas, porque mezclar
el medio con el protocolo obligaba a duplicar doscientas líneas de concurrencia
por cada forma nueva de conectarse:

```
            EnlaceArduino            el puerto: lo que el núcleo necesita
                  ▲
      ┌───────────┴───────────┐
EnlaceLineas            EnlaceMultiple
 (el protocolo)          (N placas como si fuera una)
      ▲
 ┌────┴────┐
EnlaceSerie  EnlaceTcp               solo el medio: abrir, leer, escribir, cerrar
 (pyserial)   (socket)
```

`EnlaceLineas` tiene la cola de envío, los tres hilos, el saludo, el reparto a
los escuchas y la reconexión. Un transporte nuevo son cuatro métodos.

`EnlaceMultiple` implementa el mismo puerto que un enlace suelto, así que la
ventana y el pipeline no distinguen si detrás hay una placa o tres. Reparte
cada orden a todas las conectadas, basta una viva para considerarse conectado, y
deduplica el `BTN` cuando varias placas tienen pulsador. Con una sola placa
configurada la fábrica devuelve el enlace directo: la capa no se paga si no se
usa.

Añadir una placa es una entrada en `config/default.toml`:

```toml
[[placas]]
nombre = "ESP32"
transporte = "tcp"
destino = "tcp://192.168.4.1:3333"
```

El estudio de cómo conectar un ESP32 —topologías, pines, tensiones y lista de
compras— está en [`PLAN_ESP32.md`](PLAN_ESP32.md).

## Por qué el preprocesamiento no tiene simulación

El preprocesamiento no tiene versión simulada porque no la necesita: las cinco
técnicas del curso están implementadas de verdad en numpy, en unas pocas líneas
de álgebra sobre arreglos. Así la demostración muestra histogramas que cambian
porque la imagen cambió, no porque se hayan inventado los números.

## El pipeline

`core/pipeline.py` es el único módulo que conoce el orden completo de los pasos,
el mismo de la sección 4.3 del documento del proyecto:

1. Se avisa al Arduino (`PENSANDO` + LED amarillo) **antes** del trabajo pesado,
   para que la respuesta física al pulsador sea inmediata.
2. Se captura la imagen, descartando primero los cuadros viejos del búfer.
3. Se preprocesa, guardando todas las etapas intermedias.
4. Se ejecuta el detector sobre la imagen corregida.
5. Se filtra por confianza, se traducen las clases al español y se cuentan.
6. Se arma la frase con concordancia de género y número.
7. Se envían las dos filas a la LCD y se enciende el LED verde, o el rojo si no
   hubo detecciones.
8. Se reproduce la frase y se registra todo en el CSV.

El paso 5 traduce en la frontera del núcleo: el detector habla los nombres de
COCO en inglés, y a partir de ahí todo —las etiquetas sobre las cajas, la lista
de conteo, la frase y el CSV— habla un solo idioma.

## Hilos

`pyserial` y la cámara bloquean, y la inferencia tarda cientos de milisegundos.
Nada de eso puede correr en el hilo de la interfaz o la ventana se congela justo
durante la presentación.

| Hilo | Qué hace | Cómo se comunica |
|---|---|---|
| Principal | La interfaz | — |
| `HiloCamara` | Lee cuadros a ~30 FPS | señal `cuadro_listo` |
| `HiloCaptura` | Una pasada del pipeline | señales `progreso`, `terminado`, `fallo` |
| Hilo del enlace serial | `readline()` bloqueante | `PuenteArduino`, que convierte las llamadas del adaptador en señales de Qt |

**Regla dura**: los widgets se tocan solo desde slots conectados a esas señales.
`PuenteArduino` existe precisamente para eso: el adaptador lo llama desde su
propio hilo y las señales de Qt hacen el cruce al hilo de la interfaz solas.

Mientras corre una captura, el hilo de la cámara se pausa para no competir por
el dispositivo.

## Máquina de estados

```
          ┌──────────────── capturar() ───────────────┐
          │                                           ▼
       LISTO ◄── nueva captura ── MOSTRANDO ◄──── PENSANDO
          ▲                       SIN_DETECCION  ──┘   │
          └─────────────────────── ERROR ◄────────────┘
```

Un único `EstadoApp` manda sobre todo lo que se ve: el color y el texto de la
píldora superior, si el botón Capturar está habilitado, qué LED se enciende, si
el panel DETECCIÓN muestra la cortina de progreso y si las tarjetas de la
derecha están en estado de carga. Por eso reproducir las variantes del diseño es
un cambio de estado y no una pantalla aparte.

`SIN_CÁMARA` y `ARDUINO_DESCONECTADO` son banderas ortogonales, no estados: el
Arduino puede estar caído en cualquier momento y la captura tiene que seguir
funcionando igual.

## Qué no depende de qué

- `core/` y `services/` no importan Qt, OpenCV ni pyserial. Se pueden probar con
  `pytest` sin pantalla y sin hardware.
- `ui/` no importa ningún adaptador concreto salvo `ArduinoMock`, y solo para
  reflejar en la interfaz el estado del hardware simulado.
- `ports/` no importa nada fuera de `core/modelos`.
- Para guardar las imágenes del registro, `services/imagen_io.py` escribe el PNG
  con `zlib` en treinta líneas, en vez de arrastrar OpenCV o Pillow a una capa
  que no debería depender de ellos.

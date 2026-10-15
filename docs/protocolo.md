# Protocolo laptop ↔ placas actuadoras

Este documento es el contrato. Lo implementan de forma idéntica cinco piezas, y
cualquier cambio tiene que entrar en las cinco a la vez:

- `src/vision_contador/adapters/enlace_serie.py` — enlace real por USB.
- `src/vision_contador/adapters/enlace_tcp.py` — enlace real por WiFi.
- `src/vision_contador/adapters/arduino_mock.py` — el simulado.
- `arduino/vision_contador/vision_contador.ino` — firmware del Arduino UNO.
- `arduino/vision_contador_esp32/vision_contador_esp32.ino` — firmware del ESP32.

`tests/test_protocolo.py` comprueba esa sincronía automáticamente: recorre las
constantes del puerto y verifica que aparecen en los dos sketches y en el mock.
Si añade un mensaje y olvida una pieza, las pruebas fallan.

Las constantes y los constructores de órdenes viven en
`src/vision_contador/ports/enlace_arduino.py`, para que ningún módulo escriba
estas cadenas a mano.

El protocolo **no depende del medio**: las mismas líneas viajan por un cable USB
o por un socket TCP. `adapters/enlace_lineas.py` implementa todo lo que sigue, y
los dos transportes solo aportan abrir, leer, escribir y cerrar.

## Capa física

| Parámetro | Por USB | Por WiFi |
|---|---|---|
| Transporte | Puerto serie USB (CDC) | Socket TCP |
| Velocidad | 9600 baudios, 8N1 | — |
| Destino | `COM3`, `/dev/ttyACM0` | `tcp://192.168.4.1:3333` |
| Codificación | ASCII | ASCII |
| Terminador | `\n` (el firmware ignora un `\r` previo) | igual |
| Unidad | Una orden o un mensaje por línea | igual |

El nombre del puerto **nunca** se codifica en el programa: se enumera con
`serial.tools.list_ports.comports()`, que devuelve `COM3`, `COM4`… en Windows y
`/dev/ttyUSB0` o `/dev/ttyACM0` en Linux.

TCP es un flujo de bytes, no de mensajes: una lectura puede traer media línea o
dos y media. `enlace_tcp.py` acumula lo que llega hasta encontrar el salto de
línea; sin ese búfer las órdenes se parten.

## Órdenes — laptop → Arduino

| Orden | Efecto en el Arduino | Respuesta |
|---|---|---|
| `PENSANDO` | Muestra `Pensando...` en la LCD y empieza a parpadear el LED amarillo | `OK` |
| `LCD1:<texto>` | Escribe la primera fila. El texto se rellena o recorta a 16 caracteres | `OK` |
| `LCD2:<texto>` | Escribe la segunda fila, igual | `OK` |
| `LED:AMARILLO` | Enciende el amarillo y apaga los otros dos | `OK` |
| `LED:VERDE` | Enciende el verde y apaga los otros dos | `OK` |
| `LED:ROJO` | Enciende el rojo y apaga los otros dos | `OK` |
| `LED:NINGUNO` | Apaga los tres | `OK` |
| `PING` | Nada; sirve de latido para comprobar que el canal sigue vivo | `OK` |
| `ID` | Nada; pregunta qué placa hay al otro lado | `ID:<nombre>` |

Los LEDs son **exclusivos**: encender uno apaga los demás, igual que en el
hardware, donde solo uno indica el estado en cada momento.

## Mensajes — Arduino → laptop

| Mensaje | Significado |
|---|---|
| `READY` | El Arduino arrancó y está listo. Se envía una sola vez, en `setup()` |
| `BTN` | Se presionó el pulsador físico (ya con antirrebote de 40 ms) |
| `OK` | Acuse de la última orden recibida |
| `ID:<nombre>` | Respuesta a `ID`: `ID:UNO`, `ID:ESP32`… |
| `ERR:<texto>` | La orden no se entendió o el parámetro no es válido |

### Por qué existe `ID`

Con una sola placa bastaba con aceptar cualquier `OK` como señal de vida. Con
dos conectadas a la vez eso ya no distingue quién contestó, así que al abrir el
canal la laptop pregunta `ID` en vez de `PING`.

El saludo acepta `READY`, `OK`, `ID:*` **y también** un `ERR:`, de modo que un
firmware antiguo que no conozca la orden sigue conectando: responder cualquier
cosa ya demuestra que hay alguien al otro lado.

## Secuencia de una captura

```
→  ID                           al abrir el canal, ¿quién está ahí?
←  ID:UNO
←  BTN                          el usuario presiona el pulsador
→  PENSANDO                     la LCD muestra "Pensando..." y parpadea el amarillo
←  OK
→  LED:AMARILLO
←  OK
   … la laptop captura, preprocesa, ejecuta YOLO y cuenta …
→  LCD1:Total: 4 objetos
←  OK
→  LCD2:Bo1 Ta1 Ce1 Li1
←  OK
→  LED:VERDE                    o LED:ROJO si no hubo detecciones
←  OK
```

## Reglas de diseño

**La laptop manda.** El Arduino no decide nada: no cuenta, no interpreta la
imagen y no cambia de estado por su cuenta, salvo el parpadeo del amarillo
mientras dura `PENSANDO`.

**Las filas de la LCD caben siempre.** La pantalla tiene 16 columnas físicas, y
`Bot1 Taz1 Cel1 Lib1` son 19 caracteres. `services/frase.py` prueba abreviaturas
de 3, 2 y 1 letra y usa la más larga que entre entera; si ni con una letra
alcanza, recorta y marca cuántas clases quedaron fuera con `+n`.

**La captura funciona sin Arduino.** Si el puerto no se abre, el pipeline se
salta todos los envíos y la aplicación muestra la franja de aviso, pero la
cámara, el preprocesamiento, la detección y la voz siguen funcionando.

**Reconexión.** El enlace real reintenta la conexión mientras `reconectar` esté
activo en su entrada de `[[placas]]`, y usa `PING` como latido para detectar que
el cable se desconectó o que la red se cayó.

## Varias placas a la vez

`config/default.toml` admite una entrada `[[placas]]` por cada placa, y
`adapters/enlace_multiple.py` las presenta al resto del programa como un solo
enlace. Reglas:

- **Todas reciben las mismas órdenes.** Si una falla, las demás las reciben
  igual: un actuador caído no debe dejar mudos a los otros.
- **Basta una viva** para que el pipeline considere que hay a quién enviar.
- **Las líneas se etiquetan** con el nombre de la placa en la consola
  (`[UNO] → LED:VERDE`). Con una sola placa no se etiqueta nada.
- **`BTN` se deduplica.** Si las dos placas llevan pulsador, dos avisos a menos
  de 500 ms son la misma intención del usuario y producen una sola captura.

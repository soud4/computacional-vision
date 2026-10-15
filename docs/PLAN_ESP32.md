# Plan técnico: Arduino UNO + ESP32 en Visión Contador

> **Alcance de este documento.** Es un plan, no una implementación. No cambia
> ningún archivo del repositorio ni añade código de la aplicación. Describe qué
> habría que escribir, dónde, y qué comprar y cablear para que el proyecto use
> un ESP32 junto al Arduino UNO que ya funciona, siguiendo la arquitectura de
> `docs/ARQUITECTURA.md` y el contrato de `docs/protocolo.md`.

> **Confirme su placa antes de cablear.** Todo el mapa de pines de este
> documento asume un **ESP32-WROOM-32 DevKit V1 de 30 pines** (el clon DOIT,
> con regulador AMS1117-3.3 y conversor CP2102 o CH340). El encabezado de 36
> pines, el ESP32-S3, el C3, el C6 y el S2 **tienen otro mapa de pines, otras
> restricciones y en algunos casos otro juego de periféricos**. Mire la
> serigrafía de su placa y cuente los pines antes de conectar nada. Si su placa
> no es exactamente la de 30 pines, vuelva a verificar cada fila de las tablas
> contra la hoja de datos de su variante.

---

## 1. ¿Es posible usar las dos placas a la vez?

**Sí, es perfectamente posible, y además es fácil** — pero no porque el
proyecto lo necesite, sino porque la arquitectura ya lo permite. Conviene
separar las dos preguntas:

- *¿El software lo soporta?* Sí, y con cambios mínimos. `EnlaceArduino` es una
  interfaz abstracta y `fabrica.py` es el único módulo que instancia
  adaptadores. Nada en `core/`, `services/` o `ui/` sabe que detrás hay un
  cable USB: el pipeline solo llama `enviar()` y escucha `al_pulsar_boton()`.
  Dos placas son dos instancias de `EnlaceArduino`, o una instancia compuesta
  que reparte las órdenes.
- *¿El hardware lo justifica?* Aquí hay que ser honesto: **el ESP32 no aporta
  nada al procesamiento de imágenes**. La laptop hace el 100 % del trabajo
  (PDI, YOLO11n, conteo, frase). El microcontrolador es un actuador tonto. Un
  segundo microcontrolador es, funcionalmente, un segundo actuador tonto. Lo
  que el ESP32 sí aporta y el UNO no puede dar es **el cable fuera**: WiFi.
  Ese es el único argumento sólido para añadirlo, y es un argumento bueno para
  un informe de curso.

Hay un detalle físico que casi nunca se menciona y que decide el plan entero:
**una sola LCD no se puede cablear a las dos placas**. El bus de datos de la
HD44780 es compartido y las dos placas pondrían niveles contradictorios en RS,
E y D4–D7. Lo mismo vale para cada LED y para el pulsador. Así que «las dos a
la vez» obliga a elegir:

1. **Duplicar los periféricos**: dos LCD, seis LEDs, dos pulsadores. Cuesta
   dinero (ver §6) pero es la única opción en la que las dos placas hacen algo
   visible al mismo tiempo.
2. **Repartir los periféricos**: p. ej. la LCD al ESP32 y el pulsador al UNO.
   Funciona, pero deja dos placas haciendo media tarea cada una y añade un
   punto de fallo sin ganar nada. **No lo recomiendo.**
3. **Turnarse**: una placa conectada a la vez, la otra de repuesto. Esto no es
   «las dos a la vez», es tener un repuesto, que de hecho es muy razonable.

### 1.1 Comparación de topologías

| # | Topología | Ventajas reales | Inconvenientes reales | Veredicto |
|---|---|---|---|---|
| A | **Solo ESP32** (sustituye al UNO) | Un solo cable, una sola placa. 240 MHz contra 16 MHz, 520 KB de RAM contra 2 KB. WiFi y Bluetooth disponibles para después. Sobran pines (25 expuestos). Mismo IDE y mismo sketch con cambios menores | Hay que recablear el tablero completo. 3.3 V contra los 5 V de la LCD HD44780 (ver §3.4). GPIO 6–11 inutilizables, 34–39 solo entrada, 0/2/12/15 condicionan el arranque. El UNO queda sin usar | **Técnicamente la mejor** si empezara de cero. Como ya tiene el UNO cableado y funcionando, es un retroceso de trabajo |
| B | **UNO + ESP32, dos puertos USB** | Cero cambios en el UNO, que sigue tal cual. El ESP32 corre el **mismo protocolo** y el mismo firmware portado: el adaptador `arduino_serial.py` sirve sin tocar una línea, solo con otro nombre de puerto. Fácil de depurar: dos consolas serie independientes. Sin WiFi, sin red, sin latencia | Dos cables USB ocupados. `puertos_del_sistema()` ya no puede autoseleccionar a ciegas: hay que distinguir cuál es cuál (§4.3). Duplica los periféricos. El ESP32 así usado no aporta nada que el UNO no haga | **Buena base, pero aburrida.** Es la red de seguridad, no el objetivo |
| C | **UNO ↔ ESP32 por UART o I2C, una sola habla con la laptop** | Suena elegante: un solo puerto USB para dos placas | Hay que adaptar niveles en el enlace entre placas (TX de 5 V del UNO a RX de 3.3 V del ESP32 **daña o degrada** el ESP32; hace falta divisor o level shifter). El protocolo deja de ser punto a punto y necesita enrutado (`a quién va esta orden`). Dos firmwares que hay que depurar a ciegas, porque el intermedio no tiene consola. Si una placa se cuelga, la otra parece muerta. Añade latencia y un reenvío que puede perder líneas | **Mala idea aquí.** Es complejidad de sistema distribuido para mover 20 bytes por captura. No lo haga |
| D | **ESP32 por WiFi (sin cable) + UNO por USB** | Es la única topología donde el ESP32 **hace algo que el UNO no puede**: panel de estado inalámbrico, se puede poner al otro lado del aula. Excelente material para el informe. El UNO no se toca. El protocolo de líneas ASCII viaja por TCP exactamente igual que por serie | Hay que alimentar el ESP32 (USB de pared o powerbank). Depende de una red: el WiFi del campus suele tener aislamiento de clientes y bloquea que la laptop vea al ESP32 — se resuelve con el ESP32 en modo **SoftAP** (crea su propia red, IP fija 192.168.4.1). Latencia y jitter de decenas de ms, irrelevantes aquí. La laptop debe asociarse a esa red, y entonces pierde Internet (importa si usa `edge-tts`, que necesita red: ver §5) | **La recomendada**, con la salvedad del WiFi y la voz |

### 1.2 Recomendación

**Recomiendo la topología D: el UNO se queda exactamente como está, por USB, y
el ESP32 entra como segundo actuador por WiFi en modo SoftAP, hablando el mismo
protocolo de líneas sobre un socket TCP crudo.** Y recomiendo implementarla de
modo que **la topología B sea un interruptor de configuración**, porque el mismo
firmware del ESP32 puede exponer el protocolo por USB y por WiFi a la vez.

Las razones, en orden de peso:

1. **No rompe nada de lo que funciona.** El sketch del UNO, el cableado actual y
   `arduino_serial.py` siguen intactos. Si el ESP32 falla el día de la
   presentación, desconecta el ESP32 y el proyecto es el de siempre.
2. **Es el único añadido con contenido técnico que mostrar.** «Puse dos placas
   iguales por USB» no es un hallazgo. «El actuador es inalámbrico y el mismo
   contrato de protocolo viaja por serie y por TCP sin cambiar el núcleo» sí lo
   es, y demuestra justamente para qué sirve la arquitectura de puertos y
   adaptadores del documento.
3. **Todo sigue en Python en la laptop** (§2), sin broker, sin servidor y sin
   dependencias nuevas: `socket` es de la biblioteca estándar.
4. **SoftAP elimina la dependencia de la red del aula**, que es el riesgo real.

Rechazo explícitamente la topología C y, dentro de la D, rechazo ESP-NOW (§2.5).
Y dejo constancia de que si usted pudiera recablear sin coste, **la topología A
(solo ESP32) sería la decisión de ingeniería correcta**: una placa moderna hace
todo lo que hacen las dos. Por eso en §3.3 tiene también su tabla de pines
completa: es la misma que necesita el ESP32 de la topología D.

---

## 2. ¿Se controla todo desde Python?

**Sí, todo, sin excepción.** En ningún escenario hace falta salir de Python en
la laptop. El reparto es siempre el mismo: la laptop manda (regla de diseño de
`docs/protocolo.md`) y el microcontrolador obedece.

### 2.1 USB: `pyserial`

Ya está resuelto y probado: `adapters/arduino_serial.py` abre el puerto, tiene
hilo lector con `readline()` bloqueante, cola de escritura, `PING` de latido y
reconexión. **El ESP32 por USB funciona con ese adaptador sin modificarlo**,
porque su conversor USB-serie (CP2102 o CH340) se presenta al sistema igual que
el de un clon de Arduino, y los VID de ambos ya están en `VID_CONOCIDOS`:
`0x10C4` (Silicon Labs CP210x) y `0x1A86` (QinHeng CH340).

Dos detalles del ESP32 por USB que conviene saber:

- **El bootloader ROM escribe su propio registro al arrancar a 115200 baudios.**
  Si el puerto está abierto a 9600, esas líneas llegan como basura. No es un
  problema: `_bucle_lector` decodifica con `errors="replace"`, descarta las
  líneas que no reconoce, y `_esperar_saludo()` acepta tanto `READY` como el
  `OK` de un `PING`. Aun así, el firmware debe imprimir `READY` **después** de
  un pequeño retardo para que no se pierda entre el registro del arranque.
- **DTR y RTS están cableados a EN y GPIO0** en estas placas, para que `esptool`
  pueda reiniciarlas y ponerlas en modo descarga. Abrir el puerto con los
  valores por omisión de pyserial puede reiniciar la placa o, en el peor caso,
  dejarla retenida. `SEGUNDOS_SALUDO = 4.0` ya cubre el reinicio; si apareciera
  el caso raro de que la placa no arranque al abrir el puerto, se fuerza
  `dsrdtr=False` y `rtscts=False` al construir `serial.Serial`, o se bajan las
  dos líneas explícitamente tras abrir (son **activas en bajo**).

### 2.2 WiFi: comparación de transportes

| Transporte | Biblioteca Python | A favor | En contra | Veredicto |
|---|---|---|---|---|
| **Socket TCP crudo** | `socket` (estándar) | El protocolo actual **ya es** líneas ASCII terminadas en `\n`: un socket entrega exactamente eso. `sock.makefile("rb").readline()` sustituye a `serial.readline()` y el adaptador es casi una copia de `arduino_serial.py`. Cero dependencias. En el ESP32, `WiFiServer` + `client.readStringUntil('\n')` son cuatro líneas | Hay que gestionar reconexión a mano (igual que ahora con el puerto). No hay descubrimiento automático: IP fija o mDNS | **Recomendado.** Es la opción con menos piezas móviles y la que más reutiliza |
| **WebSocket** | `websocket-client` (síncrono) o `websockets` (asyncio) | Marcos de mensaje delimitados, latidos de protocolo, atraviesa proxys, y permitiría un panel en el navegador o en el móvil | Añade una dependencia y una biblioteca al ESP32 (`ArduinoWebsockets` o `AsyncWebSocket`). El entramado que aporta es exactamente el que ya nos da `\n`. `websockets` es asíncrono y el proyecto es de hilos: mezclar asyncio con Qt es trabajo extra | **Segunda opción.** Solo si alguna vez quiere un cliente en navegador |
| **MQTT** | `paho-mqtt` | Desacopla: varios actuadores escuchando el mismo tema, QoS 1, mensajes retenidos, `last will` para detectar caídas. Escala a N placas sin tocar el cliente | **Necesita un broker** (Mosquitto local o en la nube). Son tres procesos donde había dos. Un broker caído parece un ESP32 caído. Para un actuador y una laptop en la misma mesa es infraestructura sin retorno | **Rechazado** para este proyecto. Sería la opción correcta con cinco placas o telemetría |
| **HTTP REST** | `requests` | Trivial de probar con `curl` o el navegador. `WebServer` del ESP32 es muy conocido | **No tiene empuje del servidor al cliente.** El pulsador (`BTN`) es un evento que nace en la placa, y con REST solo se descubre sondeando: o se sondea cada 100 ms (tráfico y retardo constantes) o la pulsación tarda en notarse. Rompe la simetría del protocolo | **Rechazado** como transporte principal. Útil solo como `GET /estado` de diagnóstico desde el navegador |
| **ESP-NOW** | — | Latencia mínima (~ms), sin AP, sin IP, sin pila TCP | **La laptop no habla ESP-NOW.** Es un protocolo propietario de radio de Espressif: haría falta un **segundo ESP32 conectado por USB** como adaptador, que reenviara serie↔ESP-NOW. Se gasta una placa más y se vuelve a la topología C con sus mismos problemas | **Rechazado.** Solo tiene sentido entre dos ESP32, no desde Python |

**Conclusión de §2**: socket TCP para WiFi, `pyserial` para USB, y el mismo
firmware atendiendo ambos. El adaptador nuevo no necesita ninguna dependencia
que no esté ya instalada.

### 2.3 Dirección y descubrimiento

Con el ESP32 en **SoftAP** la dirección es determinista: el ESP32 es
`192.168.4.1` y la laptop recibe `192.168.4.2` por DHCP. Eso elimina el
descubrimiento por completo y es la razón principal para preferir SoftAP sobre
modo estación. Si algún día va a modo estación (unirse al WiFi del aula), use
**mDNS** (`ESP32.begin("vision-contador")` y conectar a
`vision-contador.local`, resuelto en Linux por Avahi/`nss-mdns`) y deje la IP
fija como respaldo en la configuración, porque el mDNS falla a menudo en redes
corporativas.

### 2.4 ¿MicroPython en el ESP32?

Es tentador —el resto del proyecto es Python— pero **recomiendo C++/Arduino
para el firmware del ESP32**, por cuatro razones concretas:

1. **El sketch ya existe.** `arduino/vision_contador/vision_contador.ino` se
   porta casi literalmente: cambian los números de pin, `LiquidCrystal` por
   `LiquidCrystal_I2C` si va por I2C, y se añade el `WiFiServer`. Reescribirlo
   en MicroPython es volver a empezar y volver a depurar el antirrebote, el
   parpadeo y el recorte a 16 columnas que ya están resueltos y validados.
2. **La paridad con el UNO vale mucho.** Un solo protocolo y dos firmwares
   gemelos en el mismo lenguaje es mucho más fácil de mantener coherentes que
   dos firmwares en dos lenguajes. `docs/protocolo.md` dice que cualquier cambio
   entra en las tres piezas a la vez; con MicroPython serían cuatro piezas en
   tres lenguajes.
3. **El «Python» del proyecto está en la laptop, no en la placa.** El valor
   didáctico es el de PDI y la arquitectura de puertos. El firmware es un
   actuador de 150 líneas; su lenguaje no cambia el informe.
4. **Herramientas.** MicroPython añade `mpremote` o `ampy` para subir archivos,
   un sistema de archivos en flash que se corrompe si se desconecta a mitad, y
   un arranque más lento. El IDE de Arduino ya está instalado y usado.

Dicho eso, **MicroPython es perfectamente viable** si lo prefiere por gusto o
porque el curso lo pide. El equivalente de cada pieza existe y es maduro:
`machine.Pin` para LEDs y pulsador, `machine.I2C` + una biblioteca
`pcf8574`/`esp8266_i2c_lcd` (hay varias con documentación, p. ej. el paquete
`micropython-i2c-lcd` instalable con `mip`) o un `GpioLcd` para la HD44780 en
paralelo de 4 bits, `network.WLAN(network.AP_IF)` para el SoftAP, `socket` para
el servidor TCP, y `_thread` o un bucle con `select` para atender serie y red a
la vez. Si va por ahí, haga la **topología A** (solo ESP32): mantener dos
firmwares gemelos en dos lenguajes distintos no se sostiene.

---

## 3. Tablas de pines

### 3.0 Trampas del ESP32 — léalas antes de cablear

Estas son las que de verdad arruinan una tarde. Todas están verificadas contra
las fuentes de §7.

| Trampa | Qué pasa exactamente | Cómo se evita |
|---|---|---|
| **GPIO 6, 7, 8, 9, 10, 11 — flash SPI** | Están cableados internamente a la memoria flash SPI del módulo. Si los usa como E/S, **la placa no arranca o se cuelga**. En el DevKit V1 de 30 pines **ni siquiera están expuestos** en el conector, justamente para que nadie los use | No los use. En la placa de 30 pines es imposible equivocarse; en la de 36 sí están expuestos y ahí es un error frecuente |
| **GPIO 34, 35, 36, 39 — solo entrada** | No tienen etapa de salida: `digitalWrite()` no hace nada, silenciosamente. Y **no tienen pull-up ni pull-down internos**: un pulsador contra GND en GPIO34 con `INPUT_PULLUP` da lecturas aleatorias | Nunca ponga LEDs ni líneas de la LCD aquí. Si pone el pulsador aquí, necesita una resistencia **externa** de 10 kΩ a 3V3. Mejor: use GPIO27, que sí tiene pull-up interno. (GPIO 37 y 38 no se exponen en esta placa) |
| **GPIO 0, 2, 12, 15 (y 5) — pines de arranque** | Se muestrean en el reinicio y deciden modo de arranque y tensión de la flash. GPIO0 en bajo fuerza el modo descarga; GPIO2 debe estar en bajo al arrancar y además lleva el LED de la placa; GPIO12 debe estar en bajo (en alto selecciona otra tensión de flash y **puede impedir el arranque**); GPIO15 debe estar en alto (en bajo silencia el registro de arranque); GPIO5 debe estar en alto. El síntoma típico: la placa funciona, usted cablea un LED y **deja de subirse el programa** o deja de arrancar | No cuelgue nada de 0, 2, 12 ni 15. En el DevKit V1 de 30 pines **GPIO0 no está expuesto**, lo que ayuda. Si no le queda otra, use 12/15 solo como **salida** hacia una carga de alta impedancia y nunca con resistencia a la otra tensión |
| **GPIO 1 y 3 — UART0** | Son TX0/RX0, el puerto con el que se programa y se depura la placa. Cualquier cosa conectada ahí interfiere con la subida del programa y con la consola serie, que es justo el canal del protocolo | Déjelos libres. Son el puerto USB |
| **El ESP32 no tolera 5 V** | Las especificaciones absolutas dan −0.3 V a 3.6 V en los pines. Meter 5 V a un GPIO degrada los diodos de protección y puede matar el pin o el chip. Importa si piensa conectar el TX del UNO (5 V) al RX del ESP32, o usar una espaldera I2C con pull-ups a 5 V | Divisor resistivo o level shifter bidireccional en toda señal que **entre** al ESP32 desde 5 V. Las señales que **salen** del ESP32 a 5 V no corren peligro (es el otro extremo el que puede no reconocerlas: §3.4) |
| **ADC2 y WiFi son incompatibles** | Los pines del ADC2 (entre ellos GPIO 0, 2, 4, 12–15, 25–27) devuelven error o basura mientras el WiFi está activo. Con la topología D el WiFi **está** activo | No afecta a este proyecto, que no usa entradas analógicas. Anótelo si algún día añade un potenciómetro o un LDR: use ADC1 (GPIO 32–39) |
| **Corriente por pin** | La hoja de datos da **40 mA de corriente continua por GPIO** como máximo absoluto y unos 1200 mA en total. Es el límite de destrucción, no el de diseño: el resultado a 40 mA es un pin caliente y una tensión de salida muy caída | Diseñe a **8–12 mA por LED**. Las resistencias de §3.3 están calculadas así |
| **La numeración de los pines no es estándar** | La fila de 15 pines que en una placa empieza por `EN` en otra está invertida, y hay placas de 30 pines con otro orden. El «pin 12» de una tabla no es el «pin 12» de otra | **Cablee siempre por la serigrafía** (`D13`, `D25`, `GND`…), no por la posición. Las columnas «pin físico» de abajo son orientativas |

### 3.1 Cálculo de las resistencias de los LEDs — y por qué cambia con el ESP32

La fórmula es la ley de Ohm sobre la caída que sobra:

```
R = (V_gpio − V_f) / I
```

Donde `V_f` es la tensión directa del LED (depende del color y del fabricante;
mídala si puede) e `I` la corriente de diseño, 10 mA, que para un LED difuso de
5 mm en un aula iluminada es de sobra.

**Este es el error típico del que avisaba el enunciado**: el UNO entrega 5 V en
sus GPIO y el ESP32 **3.3 V**. Reutilizar las resistencias de 220 Ω calculadas
para 5 V en el ESP32 no quema nada, pero deja los LEDs notablemente más
apagados; y al revés, poner 150 Ω pensados para 3.3 V en el UNO sube la
corriente a ~20 mA, el doble de lo necesario.

| Color | `V_f` típico | R con **UNO (5 V)**, I = 10 mA | R comercial | I real | R con **ESP32 (3.3 V)**, I = 10 mA | R comercial | I real |
|---|---|---|---|---|---|---|---|
| Rojo | 2.0 V | (5 − 2.0)/0.01 = **300 Ω** | 220 Ω (ya montada) | 13.6 mA | (3.3 − 2.0)/0.01 = **130 Ω** | **150 Ω** | 8.7 mA |
| Amarillo | 2.1 V | (5 − 2.1)/0.01 = **290 Ω** | 220 Ω | 13.2 mA | (3.3 − 2.1)/0.01 = **120 Ω** | **150 Ω** | 8.0 mA |
| Verde estándar | 2.1 V | **290 Ω** | 220 Ω | 13.2 mA | **120 Ω** | **150 Ω** | 8.0 mA |
| Verde «brillante» / verde-azulado | 3.0–3.2 V | (5 − 3.1)/0.01 = **190 Ω** | 220 Ω | 8.6 mA | (3.3 − 3.1)/0.01 = **20 Ω** | 22–33 Ω | 6–9 mA, **muy justo** |

**Trampa del verde.** Si su LED verde es de los modernos de alto brillo con
`V_f` de 3.0–3.2 V, en el ESP32 **casi no queda margen**: 3.3 V menos 3.1 V deja
0.2 V para la resistencia, la corriente depende enormemente de la dispersión de
fabricación y el LED se verá tenue o directamente apagado. Tres salidas, en
orden de sensatez: (a) use un LED verde clásico de `V_f ≈ 2.1 V`, que es lo que
viene en los kits; (b) alimente ese LED desde los 5 V del pin `5V` con un
transistor NPN pequeño (BC547, 2N2222) mandado por el GPIO a través de 1 kΩ;
(c) acepte 33 Ω y un verde apagado. Para el proyecto, (a).

Con **220 Ω en el ESP32** (si no quiere comprar nada) la corriente queda en
~5.9 mA con el rojo: el LED enciende y se ve, solo que con menos brillo. Es una
opción válida para una primera prueba.

### 3.2 Topología recomendada (D) — el UNO no se toca

El tablero del UNO **se queda exactamente como está hoy**. Esta tabla es la
verificación del cableado actual contra el sketch
`arduino/vision_contador/vision_contador.ino`: coincide, no hay solapamientos y
no hay nada que cambiar.

| Función | Pin del UNO | Conexión | Notas |
|---|---|---|---|
| LCD RS | D12 | → LCD pin 4 (RS) | Modo 4 bits |
| LCD E | D11 | → LCD pin 6 (E) | |
| LCD D4 | D5 | → LCD pin 11 (DB4) | |
| LCD D5 | D4 | → LCD pin 12 (DB5) | |
| LCD D6 | D3 | → LCD pin 13 (DB6) | |
| LCD D7 | D2 | → LCD pin 14 (DB7) | |
| LCD RW | — | LCD pin 5 → GND | Solo escritura; nunca lee, por eso no hay retorno de datos |
| LCD VSS / K | — | LCD pines 1 y 16 → GND | K es el cátodo de la retroiluminación |
| LCD VDD / A | — | LCD pines 2 y 15 → **5 V** | A es el ánodo de la retroiluminación. Conviene 100 Ω en serie con A para alargar su vida |
| LCD V0 (contraste) | — | LCD pin 3 → cursor del potenciómetro de 10 kΩ, extremos a 5 V y GND | Sin esto la pantalla se ve en blanco y parece averiada |
| LED amarillo | D6 | ánodo ← D6, cátodo → **220 Ω** → GND | 13.2 mA |
| LED verde | D7 | ánodo ← D7, cátodo → **220 Ω** → GND | |
| LED rojo | D8 | ánodo ← D8, cátodo → **220 Ω** → GND | |
| Pulsador | D9 | un terminal a D9, el otro a GND | `INPUT_PULLUP`: sin resistencia externa. Reposo = HIGH, pulsado = LOW |
| Alimentación | USB | — | El USB de la laptop da 500 mA; LCD + 3 LEDs + placa consumen bastante menos |

Y el ESP32 lleva **su propio tablero**, con la tabla de §3.3. En la topología D
el ESP32 no comparte **ningún** cable con el UNO: ni la masa, porque no hay
señal entre ellos. (Si algún día conectara los dos tableros, la masa común
sería obligatoria y además haría falta adaptación de niveles: §3.0.)

### 3.3 Tabla del ESP32 — sirve igual para «solo ESP32» (topología A)

Esta es la tabla que necesita tanto para el ESP32 de la topología D como para
sustituir al UNO por completo. Se eligieron **solo pines sin restricciones**:
nada de 0, 2, 12, 15, nada de 1/3 (UART0), nada de 34–39, y se dejan libres
GPIO 21 y 22 (el I2C por omisión) para la variante de §3.3b.

Los números de «pin físico» siguen el orden publicado para el DOIT DevKit V1 de
30 pines (fila de 1 a 15 empezando en `EN`, fila de 16 a 30 empezando en
`GPIO17`). **Cablee por la serigrafía**, no por este número.

#### 3.3a Variante paralela (LCD en 4 bits, como el UNO)

| Función | GPIO | Serigrafía | Pin físico | Conexión | Notas |
|---|---|---|---|---|---|
| LCD RS | 13 | `D13` | 12 | → LCD pin 4 | Pin seguro, sin funciones de arranque |
| LCD E | 14 | `D14` | 13 | → LCD pin 6 | |
| LCD D4 | 26 | `D26` | 23 | → LCD pin 11 | |
| LCD D5 | 25 | `D25` | 22 | → LCD pin 12 | |
| LCD D6 | 33 | `D33` | 26 | → LCD pin 13 | |
| LCD D7 | 32 | `D32` | 25 | → LCD pin 14 | |
| LCD RW | — | — | — | LCD pin 5 → GND | **Obligatorio** a GND: así el bus es unidireccional y la LCD nunca mete 5 V en el ESP32 |
| LCD VSS | — | `GND` | 2 o 4 | LCD pin 1 → GND | |
| LCD VDD | — | `5V` (`VIN`) | 3 | LCD pin 2 → **5 V** | Ver §3.4 antes de decidir entre 5 V y 3.3 V |
| LCD V0 | — | — | — | LCD pin 3 → cursor de un potenciómetro de 10 kΩ | Extremos del potenciómetro a VDD y GND |
| LCD A (luz +) | — | `5V` | 3 | LCD pin 15 → 5 V, con 100 Ω en serie | |
| LCD K (luz −) | — | `GND` | 2 o 4 | LCD pin 16 → GND | |
| LED amarillo | 18 | `D18` | 17 | ánodo ← GPIO18, cátodo → **150 Ω** → GND | 8.0 mA |
| LED verde | 19 | `D19` | 18 | ánodo ← GPIO19, cátodo → **150 Ω** → GND | Lea la trampa del verde en §3.1 |
| LED rojo | 23 | `D23` | 21 | ánodo ← GPIO23, cátodo → **150 Ω** → GND | 8.7 mA |
| Pulsador | 27 | `D27` | 24 | un terminal a GPIO27, el otro a GND | **`INPUT_PULLUP` interno: sin resistencia externa.** GPIO27 sí tiene pull-up, al contrario que 34–39 |
| Masa | — | `GND` | 2, 4 y 14ª/… | Masa común de todo el tablero | Un solo nodo de masa en la protoboard |
| Alimentación | — | `micro-USB` | — | Cargador de 5 V / 1 A o powerbank | Con WiFi el ESP32 tiene picos de ~250–300 mA; un USB flojo provoca reinicios por caída de tensión (ver §5) |

Pines que quedan libres y son seguros para ampliar: **GPIO 4, 16, 17, 21, 22** y
los de solo entrada **34, 35, 36, 39** (con pull-up externo si hace falta).

#### 3.3b Variante I2C con PCF8574 — la que recomiendo

Una espaldera PCF8574 soldada a la LCD convierte seis cables de señal en dos.
Es la opción que recomiendo para el ESP32: menos cables en la protoboard, menos
puntos de fallo, y libera seis GPIO.

| Función | GPIO | Serigrafía | Pin físico | Conexión | Notas |
|---|---|---|---|---|---|
| I2C SDA | 21 | `D21`/`SDA` | 19 | → `SDA` de la espaldera | Es el SDA por omisión de `Wire` en el ESP32 |
| I2C SCL | 22 | `D22`/`SCL` | 20 | → `SCL` de la espaldera | |
| Alim. espaldera | — | `5V` o `3V3` | 3 o 5 | → `VCC` de la espaldera | **Decisión importante: lea §3.4** |
| Masa espaldera | — | `GND` | 2 o 4 | → `GND` de la espaldera | |
| LED amarillo | 18 | `D18` | 17 | ánodo ← GPIO18, cátodo → **150 Ω** → GND | |
| LED verde | 19 | `D19` | 18 | ánodo ← GPIO19, cátodo → **150 Ω** → GND | |
| LED rojo | 23 | `D23` | 21 | ánodo ← GPIO23, cátodo → **150 Ω** → GND | |
| Pulsador | 27 | `D27` | 24 | a GPIO27 y a GND | `INPUT_PULLUP` |
| Alimentación | — | micro-USB | — | 5 V / 1 A | |

En el firmware, `LiquidCrystal_I2C lcd(0x27, 16, 2)`. La dirección es `0x27` en
la mayoría de las espalderas y `0x3F` en otras; si no aparece nada, haga un
barrido I2C (el ejemplo `i2c_scanner`) antes de sospechar del cableado.

### 3.4 El problema de los 5 V de la LCD con un ESP32 de 3.3 V

Esta es la pregunta del enunciado y merece una respuesta sin rodeos. Hay dos
asuntos distintos que suelen confundirse:

**(a) La LCD necesita 5 V para verse bien.** La HD44780 arranca y funciona
alimentada a 3.3 V en muchos módulos, pero el contraste queda pobre y a veces no
hay ajuste del potenciómetro que lo arregle, porque la tensión del cristal
líquido escala con VDD. **Alimente la LCD desde el pin `5V`/`VIN` del DevKit**,
que es el 5 V del USB pasado directo, no desde `3V3`.

**(b) Los niveles lógicos.** La HD44780 alimentada a 5 V pide `V_IH ≥ 0.7 × VDD
= 3.5 V` para leer un «1», y el ESP32 entrega **3.3 V**. Está **fuera de
especificación por 0.2 V**.

Lo que pasa en la práctica, con honestidad: **funciona casi siempre**. Hay miles
de montajes así y es el caso más documentado en la web. Pero «casi siempre» es
exactamente el tipo de margen que falla delante del profesor, con la protoboard
caliente y los cables largos. Y hay un detalle que lo salva: con **RW a GND**
el bus es de una sola dirección —el ESP32 solo escribe y nunca lee— así que el
riesgo es que la LCD muestre caracteres raros, nunca que los 5 V entren al
ESP32. No hace falta `delay` de lectura ni adaptación en el sentido de vuelta.

Las opciones, de la que recomiendo a la que no:

| Opción | Fiabilidad | Coste | Comentario |
|---|---|---|---|
| **Espaldera PCF8574 alimentada a 3.3 V** | Alta | 0 | La recomendada. El PCF8574 funciona desde 2.5 V, así que a 3.3 V los niveles I2C son correctos **y los pull-ups de la espaldera quedan a 3.3 V**, que es lo que el ESP32 necesita. El único coste es que el contraste y la retroiluminación serán más tenues: se compensa dejando la **retroiluminación** alimentada desde los 5 V (ánodo A a `5V` con su 100 Ω) y ajustando el potenciómetro de la espaldera |
| **Espaldera PCF8574 a 5 V con level shifter bidireccional** en SDA y SCL | Muy alta | ~2 € | La opción de libro. Un módulo de 4 canales con BSS138 es barato y es lo correcto si quiere que el informe sea impecable |
| **LCD paralela a 5 V con el ESP32 escribiendo 3.3 V** (§3.3a tal cual) | Media-alta | 0 | Funciona en la gran mayoría de los módulos. RW a GND hace que sea seguro para el ESP32. Si ve caracteres corruptos o la pantalla se queda a medias, es esto |
| **Espaldera PCF8574 a 5 V conectada directamente al ESP32** | **Mala idea** | 0 | Los pull-ups de la espaldera ponen **5 V en SDA y SCL**, que son **entradas** del ESP32. Esto sí mete 5 V en un pin de 3.3 V. Circula en tutoriales porque «no se quema a la primera», pero degrada el pin. **No lo haga sin level shifter, o quite los pull-ups de la espaldera y pónga 4.7 kΩ a 3V3** |
| LCD entera a 3.3 V, paralela | Baja | 0 | Contraste malo. Solo para comprobar que el firmware funciona |

### 3.5 Diagrama de la protoboard — ESP32 (variante I2C, §3.3b)

```
                        ┌──────────── riel + 5 V (del pin 5V del DevKit) ────────────┐
                        │   ┌──────── riel + 3.3 V (del pin 3V3 del DevKit) ─────┐   │
                        │   │                                                    │   │
   ESP32-WROOM-32 DevKit V1 (30 pines)                                           │   │
   ┌──────────────────────────────────────┐                                       │   │
   │  EN ○                        ○ GPIO23│──┐ LED rojo                           │   │
   │ GND ○────┐                   ○ GPIO22│──┼───────── SCL ─────┐                │   │
   │  5V ○────┼───▶ riel +5 V     ○ GPIO21│──┼───────── SDA ───┐ │                │   │
   │ GND ○────┤                   ○ GPIO19│──┼─┐ LED verde     │ │                │   │
   │ 3V3 ○────┼───▶ riel +3.3 V   ○ GPIO18│──┼─┼─┐ LED amar.   │ │                │   │
   │ TX0 ○ ✗  │                   ○ GPIO17│  │ │ │             │ │                │   │
   │GPIO2○ ✗  │   (strapping)     ○ GPIO16│  │ │ │             │ │                │   │
   │ RX0 ○ ✗  │                    ○ GPIO5│✗ │ │ │             │ │                │   │
   │GPIO4○    │                    ○ GPIO4│  │ │ │             │ │                │   │
   │GPIO5○ ✗  │                   ○ GPIO27│──┼─┼─┼── pulsador  │ │                │   │
   │GPIO12○✗  │   (strapping)     ○ GPIO26│  │ │ │             │ │                │   │
   │GPIO13○   │                   ○ GPIO25│  │ │ │             │ │                │   │
   │GPIO14○   │                   ○ GPIO33│  │ │ │             │ │                │   │
   │GPIO15○✗  │   (strapping)     ○ GPIO32│  │ │ │             │ │                │   │
   │GPIO16○   │                   ○ GPIO34│  │ │ │  (solo in)  │ │                │   │
   └──────────┼───────────────────────────┘  │ │ │             │ │                │   │
              │                              │ │ │            │ │                │   │
      riel GND ◀─────────────────────────────┼─┼─┼────────────┼─┼────────────────┼───┤
              │                              │ │ │            │ │                │   │
              │     ┌────────────────────────┘ │ │            │ │                │   │
              │     │   ┌──────────────────────┘ │            │ │                │   │
              │     │   │   ┌────────────────────┘            │ │                │   │
              │     │   │   │                                 │ │                │   │
              │  ROJO AMA VERDE                               │ │                │   │
              │   ▼   ▼   ▼     (ánodo arriba, cátodo abajo)  │ │                │   │
              │   ▬   ▬   ▬     ← LED 5 mm                    │ │                │   │
              │  150Ω150Ω150Ω   ← resistencias (3.3 V!)       │ │                │   │
              └───┴───┴───┴──▶ riel GND                       │ │                │   │
                                                              │ │                │   │
          Pulsador táctil:  GPIO27 ──┤ ├── riel GND           │ │                │   │
                            (pull-up interno, sin resistencia)│ │                │   │
                                                              │ │                │   │
   LCD 16x2 con espaldera PCF8574 soldada por detrás:         │ │                │   │
   ┌───────────────────────────────────────────────┐          │ │                │   │
   │  ████████████████  Total: 4 objetos           │          │ │                │   │
   │  ████████████████  Bo1 Ta1 Ce1 Li1            │          │ │                │   │
   │                                               │          │ │                │   │
   │  espaldera:  GND ───────────────────▶ riel GND│          │ │                │   │
   │              VCC ───────────────────▶ riel 3.3 V ────────┼─┼────────────────┘   │
   │              SDA ◀───────────────────────────────────────┘ │                    │
   │              SCL ◀─────────────────────────────────────────┘                    │
   │              (retroiluminación A ── 100 Ω ──▶ riel 5 V) ◀───────────────────────┘
   └───────────────────────────────────────────────┘

   ✗ = no usar (UART0 de programación, flash SPI o pin de arranque)
   Masa única: todos los GND en el mismo riel. Si alimenta la LCD desde una
   fuente distinta de la del ESP32, una las dos masas o nada funcionará.
```

Variante paralela de 4 bits (§3.3a), solo la parte de la LCD:

```
   ESP32                     LCD 16x2 (HD44780), 16 pines
   GPIO13 ──────────────────▶ 4  RS
   GPIO14 ──────────────────▶ 6  E
   GPIO26 ──────────────────▶ 11 DB4
   GPIO25 ──────────────────▶ 12 DB5
   GPIO33 ──────────────────▶ 13 DB6
   GPIO32 ──────────────────▶ 14 DB7
   (nada) ──────────────────▶ 7-10 DB0..DB3   sin conectar: modo 4 bits
   GND ─────────────────────▶ 5  RW   ◀── a GND SIEMPRE: bus unidireccional
   GND ─────────────────────▶ 1  VSS
   5V  ─────────────────────▶ 2  VDD
   pot 10 kΩ (cursor) ──────▶ 3  V0   extremos del pot a 5 V y GND
   5V ── 100 Ω ─────────────▶ 15 A
   GND ─────────────────────▶ 16 K
```

---

## 4. Cambios concretos en el repositorio

La regla que gobierna todo esto: **ni `ports/enlace_arduino.py` ni nada de
`core/`, `services/` o `ui/` se toca.** Una placa nueva es un adaptador nuevo.

### 4.1 Archivos nuevos

| Archivo | Qué contiene | Tamaño estimado |
|---|---|---|
| `src/vision_contador/adapters/esp32_wifi.py` | `class Esp32WiFi(EnlaceArduino)`. Estructura calcada de `arduino_serial.py`: hilo lector con `readline()` sobre `sock.makefile("rb")`, cola de escritura, hilo vigilante con `PING` y reconexión. `puertos_disponibles()` devuelve la lista de destinos configurados (`192.168.4.1:3333`) en vez de nombres de dispositivo, y `conectar(puerto, baudios)` interpreta `puerto` como `host:puerto` e ignora `baudios`. Así la firma del puerto se respeta sin cambiarla | ~200 líneas |
| `src/vision_contador/adapters/enlace_multiple.py` | `class EnlaceMultiple(EnlaceArduino)`: compuesto que recibe N enlaces, reenvía cada `enviar()` a todos los que estén conectados, se suscribe a todos y reparte sus eventos. **Aquí vive la deduplicación de `BTN`** (§5). `conectado` es «al menos uno», `puerto_actual` es la concatenación. Es el patrón *composite* y encaja en el puerto sin forzarlo | ~120 líneas |
| `arduino/vision_contador_esp32/vision_contador_esp32.ino` | El sketch del UNO portado: pines de §3.3, `LiquidCrystal_I2C`, `WiFi.softAP()`, `WiFiServer server(3333)`, y un `loop()` que atiende **las dos** fuentes —`Serial` y el cliente TCP— con la misma función `procesar()`. La lógica de órdenes, antirrebote y parpadeo se copia sin cambios conceptuales | ~230 líneas |
| `docs/protocolo_esp32.md` | La capa física del transporte TCP: puerto 3333, SoftAP, SSID/clave, un cliente a la vez, y qué pasa al desconectarse. Enlazado desde `docs/protocolo.md` | corto |

### 4.2 Qué se reutiliza sin tocar una línea

- **`ports/enlace_arduino.py`** entero: las constantes `CMD_PENSANDO`,
  `CMD_PING`, `cmd_lcd()`, `cmd_led()`, `MSG_READY`, `MSG_BTN`, `MSG_OK`,
  `PREFIJO_ERROR`, el `Protocol` `EscuchaArduino` y la excepción
  `ArduinoNoDisponible` sirven igual por TCP. El puerto no menciona pyserial.
- **`core/pipeline.py`**: no se enterará de nada.
- **`ui/`** y `PuenteArduino`: el adaptador nuevo llama a `EscuchaArduino`
  desde su propio hilo, exactamente como el serial, y las señales de Qt hacen
  el cruce. La consola serie de la aplicación mostrará el tráfico de las dos
  placas sin cambios.
- **`adapters/arduino_serial.py`**: sirve tal cual para el UNO **y** para el
  ESP32 por USB (topología B). Los VID de CP2102 y CH340 ya están en
  `VID_CONOCIDOS`.
- **`adapters/arduino_mock.py`**: el modo demo no cambia.
- **El sketch del UNO y su cableado.**
- **`services/frase.py`**: el recorte a 16 columnas con abreviaturas de 3, 2 y 1
  letra vale igual para la segunda pantalla.

### 4.3 Cambios pequeños en archivos existentes

| Archivo | Cambio |
|---|---|
| `core/config.py` | Añadir a `ConfigArduino` un campo `backend: str = "serial"` y una dataclass `ConfigEsp32(host="192.168.4.1", puerto_tcp=3333, activo=False)`. Nada más |
| `config/default.toml` | Un bloque `[esp32]` con `activo`, `host`, `puerto_tcp`, y `[arduino] backend`. Comentado y desactivado por omisión, igual que el resto |
| `fabrica.py` | `crear_arduino()` pasa a: si demo → `ArduinoMock`; si solo serial → como ahora; si `[esp32] activo` → `EnlaceMultiple([ArduinoSerial(...), Esp32WiFi(...)])` cargado con `_cargar()` para conservar los mensajes de error precisos |
| `docs/protocolo.md` | Las dos órdenes nuevas de §4.4 y una nota de que el transporte puede ser serie o TCP |
| `docs/IMPLEMENTACION_REAL.md` | Un paso 8 nuevo con esta hoja de ruta |

### 4.4 ¿Sirve el protocolo tal cual?

**Sí, el protocolo de `docs/protocolo.md` sirve sin cambios para que funcione.**
Es ASCII, una orden por línea terminada en `\n`, sin estado y sin tramas: eso
viaja por TCP exactamente igual que por un UART. Es la mejor propiedad del
diseño actual y la razón por la que todo esto es barato.

Hacen falta **dos extensiones pequeñas**, y solo por tener dos placas:

| Orden nueva | Respuesta | Por qué |
|---|---|---|
| `ID` | `ID:UNO` / `ID:ESP32` (idealmente `ID:ESP32 v1 wifi`) | Con dos puertos serie, `puertos_del_sistema()` ya no puede adivinar. Hoy `_esperar_saludo()` manda `PING` y acepta cualquier `OK`: cualquier placa con el firmware pasa la prueba. Con `ID` la autodetección deja de ser una apuesta y la interfaz puede etiquetar cada línea de la consola con su origen. Es la extensión que de verdad hace falta |
| `BTN:<origen>` (opcional) | — | Si las dos placas tienen pulsador, el pipeline recibe dos `BTN` por cada captura. Se puede resolver solo en `EnlaceMultiple` (§5) sin cambiar el mensaje, pero marcar el origen ayuda a depurar |

Lo que **no** hay que hacer: inventar enrutado (`UNO:LED:VERDE`), números de
secuencia o acuses con identificador. Eso sería necesario en la topología C, y
es otra razón para no elegirla. Con dos enlaces independientes, cada uno con su
contrato punto a punto, el protocolo se queda simple.

Capa física, para la tabla de `docs/protocolo.md`:

| Parámetro | UNO (USB) | ESP32 (WiFi) | ESP32 (USB) |
|---|---|---|---|
| Transporte | Serie USB CDC | TCP sobre WiFi | Serie USB CDC |
| Velocidad / destino | 9600 8N1 | `192.168.4.1:3333` | 115200 8N1 (o 9600) |
| Codificación | ASCII | ASCII | ASCII |
| Terminador | `\n` | `\n` | `\n` |

---

## 5. Riesgos y qué puede salir mal

| # | Riesgo | Probabilidad | Síntoma | Mitigación |
|---|---|---|---|---|
| 1 | **Doble `BTN`**: las dos placas tienen pulsador y el pipeline arranca dos capturas | Alta | Dos capturas seguidas, la segunda con la cámara ya tomada | En `EnlaceMultiple`, descartar todo `BTN` que llegue en los 500 ms siguientes a otro. O, más simple: **dejar el pulsador solo en el UNO** y no montarlo en el ESP32 |
| 2 | **La LCD de 5 V no reconoce los 3.3 V del ESP32** | Media | Caracteres corruptos, filas a medias, o pantalla en blanco | §3.4: espaldera PCF8574 a 3.3 V, o level shifter. RW a GND garantiza que el riesgo es solo cosmético |
| 3 | **Un pin de arranque cableado impide subir el programa** | Media si improvisa pines | `Failed to connect to ESP32: Timed out waiting for packet header`, o la placa no arranca | No usar 0, 2, 12, 15, 1, 3. Si ya pasó: desconecte todo del tablero, suba el programa, vuelva a conectar. Mantener pulsado `BOOT` al iniciar la subida |
| 4 | **Reinicios por caída de tensión** (*brownout*): el ESP32 pide picos de 250–300 mA al transmitir WiFi, y la retroiluminación de la LCD otros 20 mA | Media | `Brownout detector was triggered` en el registro, reinicios cíclicos al conectar el WiFi | Alimentar con un cargador de 5 V / 1 A **de calidad**, cable USB corto y de datos (no de carga), condensador de 470 µF entre 5 V y GND junto a la placa. No alimentar la LCD desde el pin `3V3` |
| 5 | **El WiFi del aula aísla a los clientes o el cortafuegos bloquea el puerto 3333** | Alta si usa modo estación | La conexión TCP falla con `timed out` aunque el `ping` responda | **Usar SoftAP** (el ESP32 crea su red): elimina el problema de raíz. Si ha de ser modo estación, pruebe la red antes del día de la presentación |
| 6 | **Al asociarse al SoftAP, la laptop pierde Internet** y `edge-tts` deja de sintetizar | Alta | La frase no se oye; la tarjeta FRASE GENERADA falla | El caché de `cache/voz/` ya existe precisamente para esto: **precaliente las frases** antes de la demostración. Respaldo `pyttsx3`, que es local. O conecte el WiFi al SoftAP y deje Internet por cable Ethernet / 4G |
| 7 | **Autodetección que elige el puerto equivocado** con dos placas conectadas | Alta | Las órdenes van a la placa que no es; parece que una está muerta | La orden `ID` de §4.4. Mientras no exista, fije el puerto en `[arduino] puerto` y verifique con `ls -l /dev/serial/by-id/`, que da nombres estables por placa |
| 8 | **Permisos del puerto serie en Linux** | Alta la primera vez | `permission denied`, ya explicado en `_explicar()` | `sudo usermod -aG uucp $USER` (o `dialout`) y reiniciar sesión. Ya documentado en `docs/IMPLEMENTACION_REAL.md` |
| 9 | **El monitor serie del IDE de Arduino ocupa el puerto** | Alta | `está ocupado por otra aplicación`, que el adaptador ya detecta | Cerrar el IDE. Con dos placas, cerrar los dos monitores |
| 10 | **La reconexión TCP se queda colgada** porque un socket roto no da error hasta que expira el TCP | Media | La interfaz dice «conectado» y nada responde | `SO_KEEPALIVE`, `settimeout()` en el socket, y el `PING` cada 5 s del vigilante que ya existe: si no llega `OK` en dos latidos, cerrar y reabrir |
| 11 | **El clon del DevKit tiene otro mapa de pines** del supuesto | Media | Un LED que no enciende o un pin que no existe | Verificar la serigrafía antes de cablear. Es el aviso del encabezado de este documento |
| 12 | **LED verde de alto brillo invisible a 3.3 V** | Media | El LED verde apenas se ve, los otros dos bien | §3.1: LED verde clásico de 2.1 V, o transistor desde los 5 V |
| 13 | **Dos firmwares que se desincronizan** del protocolo | Media a largo plazo | Una placa responde `ERR:orden desconocida` | La regla de `docs/protocolo.md` pasa a ser «cualquier cambio entra en **cuatro** piezas»: los dos adaptadores reales, el mock y los dos sketches. Una prueba en `tests/` que recorra las constantes del puerto ayuda |
| 14 | **Complejidad añadida sin retorno** | **La más real de todas** | Se va el fin de semana depurando WiFi en vez de mejorar el preprocesamiento o el informe | Implementar en el orden de §4 y **validar primero la topología B** (ESP32 por USB con el mismo adaptador), que no puede fallar. El WiFi es el último paso y es opcional. Si a mitad de camino se complica, apáguelo en la configuración y el proyecto sigue entregable |

---

## 6. Lista de compras

Lo que ya tiene (UNO, LCD 16x2, 3 LEDs, pulsador, resistencias de 220 Ω,
potenciómetro de 10 kΩ, protoboard, cables) se queda **intacto** en el UNO.

### Imprescindible

| # | Componente | Cant. | Precio orientativo | Por qué |
|---|---|---|---|---|
| 1 | **ESP32-WROOM-32 DevKit V1, 30 pines** | 1 | 5–8 € | La placa. Confirme que es la de 30 pines |
| 2 | **Cable micro-USB de datos**, corto (≤ 1 m) | 1 | 2 € | Muchos cables de cargador son solo de alimentación y la placa no se detecta. Un clásico que cuesta horas |
| 3 | **LCD 16x2 HD44780** | 1 | 3–5 € | El segundo tablero necesita su propia pantalla: una LCD no se puede compartir entre dos placas (§1) |
| 4 | **Espaldera I2C PCF8574** para LCD 16x2 | 1 (o 2) | 1–2 € | Reduce seis cables a dos y resuelve lo de los niveles alimentándola a 3.3 V (§3.4). Compre dos si quiere convertir también la del UNO |
| 5 | **Resistencias de 150 Ω, 1/4 W** | 3 (compre 10) | 1 € | Las de los LEDs a 3.3 V (§3.1). Con 220 Ω también funciona, solo más tenue |
| 6 | **LEDs de 5 mm: amarillo, verde, rojo** | 3 | 1 € | Segundo juego para el ESP32. Que el **verde sea el clásico de ~2.1 V**, no uno de alto brillo |
| 7 | **Pulsador táctil 6x6 mm** | 1 (o ninguno) | 0.5 € | Opcional: ver riesgo 1. Si deja el pulsador solo en el UNO, no lo necesita |
| 8 | **Potenciómetro de 10 kΩ** | 1 | 0.5 € | Solo si monta la LCD en paralelo (§3.3a). La espaldera PCF8574 ya trae el suyo |
| 9 | **Protoboard de 400 puntos y cables macho-macho** | 1 juego | 5 € | El segundo tablero |

### Recomendable

| # | Componente | Cant. | Precio | Por qué |
|---|---|---|---|---|
| 10 | **Level shifter bidireccional de 4 canales (BSS138)** | 1 | 2 € | La solución de libro al asunto de 3.3 V ↔ 5 V. Barato y queda bien en el informe |
| 11 | **Cargador USB de 5 V / 1 A o powerbank** | 1 | 5 € | Para que el ESP32 sea de verdad inalámbrico (topología D) y no reinicie por caída de tensión (riesgo 4) |
| 12 | **Condensador electrolítico de 470 µF / 16 V** | 1 | 0.3 € | Entre 5 V y GND junto al ESP32, contra los picos del WiFi |
| 13 | **Resistencia de 100 Ω** | 1 | — | En serie con el ánodo de la retroiluminación de la LCD |
| 14 | **Hub USB alimentado** | 1 | 8 € | Si va por la topología B, dos placas en los puertos de la laptop ya aprietan |

Total imprescindible: **unos 20–25 €**. Con lo recomendable, unos 40 €.

### Lo que **no** hace falta comprar

- Un segundo ESP32 (solo lo pediría ESP-NOW, rechazado en §2.5).
- Un adaptador de nivel para el enlace entre placas, porque la topología C
  queda descartada: en la topología D las dos placas no se tocan.
- Un broker MQTT ni un servidor: el socket TCP no necesita nada.
- Un ESP32-CAM: la captura la hace la webcam de la laptop y todo el PDI vive en
  Python. Un ESP32-CAM metería un segundo canal de vídeo y una segunda fuente
  de problemas sin aportar al objetivo del curso.

---

## 7. Fuentes

Datos de pines, restricciones de GPIO, tensiones y niveles lógicos verificados
en (consultadas el 11 de octubre de 2026):

- [Last Minute Engineers — ESP32 Pinout Reference](https://lastminuteengineers.com/esp32-pinout-reference/) — pines de solo entrada (34, 35, 36, 39) sin pull-up interno; GPIO 6–11 de la flash SPI; pines de arranque 0, 2, 5, 12, 15 y el efecto de cada uno; ADC2 inutilizable con WiFi; los 600 mA del regulador 3V3; pines seguros para uso general.
- [espboards.dev — DOIT ESP32 DevKit V1](https://www.espboards.dev/esp32/esp32doit-devkit-v1/) — mapa físico de los 30 pines, los 25 GPIO expuestos y los que **no** se exponen (0, 6–11, 20, 24, 28–31, 37, 38); regulador AMS1117-3.3; umbral de *brownout* en ~2.4 V.
- [esp32.co.uk — ESP32 NodeMCU 30-pin pinout, safe GPIOs](https://esp32.co.uk/esp32-nodemcu-30-pin-pinout-safe-gpios/) — confirmación de los pines seguros y del fallo típico del pulsador en GPIO34.
- [Foro de Espressif — Current Limits](https://esp32.com/viewtopic.php?p=25401) — los 40 mA de corriente continua por GPIO como máximo absoluto, y que los 12 mA que circulan por ahí son un dato del ESP8266.
- [Foro de Espressif — límites de tensión en los pines](https://esp32.com/viewtopic.php?p=8144) — el ESP32 **no** tolera 5 V; especificación absoluta de −0.3 V a 3.6 V, con la discrepancia entre la hoja de datos del chip y la del módulo.
- [esptool — Boot Mode Selection](https://docs.espressif.com/projects/esptool/en/latest/advanced-topics/boot-mode-selection.html) — DTR y RTS cableados a GPIO0 y EN, activos en bajo, y la advertencia de que algunos sistemas los activan solos al abrir el puerto.
- [ESP-IDF — Establish Serial Connection with ESP32](https://docs.espressif.com/projects/esp-idf/en/release-v5.4/esp32/get-started/establish-serial-connection.html) — 115200 baudios como velocidad de consola por omisión y el registro de arranque.
- [Foro de Arduino — 3.3 V Arduino, I2C backpack to 5 V LCD](https://forum.arduino.cc/t/3-3v-arduino-i2c-backpack-to-5v-lcd/411866) — el `V_IH` del PCF8574 en 0.7 × VDD (3.5 V a 5 V), y la advertencia de quitar los pull-ups de la espaldera si se pasan a 3.3 V.
- [ShillehTek — ESP32 + LCD1602 con level shifter](https://shillehtek.com/blogs/news/esp32-lcd1602-blink-hello-world-with-logic-level-shifter-shillehtek) y [manual de la espaldera PCF8574](https://shillehtek.com/blogs/shillehtek-product-manuals/pcf8574-i2c-serial-interface-adapter-module-for-1602-2004-lcd-manual) — contraste pobre al alimentar el cristal a 3.3 V; los pull-ups de la espaldera a 5 V en SDA/SCL y la recomendación del adaptador bidireccional.
- [microcontrollerslab — módulos LCD para Arduino, ESP32 y Raspberry Pi](https://microcontrollerslab.com/?p=44666) — módulos que sí están diseñados para 3.3 V.
- [Random Nerd Tutorials — MicroPython: I2C LCD con ESP32](https://randomnerdtutorials.com/micropython-i2c-lcd-esp32-esp8266/) y [micropython-i2c-lcd](https://micropython-i2c-lcd.readthedocs.io/en/latest/readme_link.html) — viabilidad de la alternativa MicroPython y bibliotecas equivalentes.

Las tensiones directas de los LEDs (`V_f`) son valores típicos de catálogo para
LEDs difusos de 5 mm; varían entre fabricantes. Si el brillo no le convence,
mídalas con un multímetro y recalcule con la fórmula de §3.1.

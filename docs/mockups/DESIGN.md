---
name: Vision Contador Precision Laboratory
colors:
  background: '#0F141A'
  panel-bg: '#161D26'
  panel-border: '#263241'
  text-main: '#E6EDF3'
  text-secondary: '#8B98A8'
  primary: '#3B82F6'
  status-processing: '#F5B700'
  status-ok: '#22C55E'
  status-error: '#EF4444'
  console-bg: '#0B0E13'
typography:
  headline-sm: { fontFamily: Inter, fontSize: 13px, fontWeight: '700', letterSpacing: 0.06em }
  body-default: { fontFamily: Inter, fontSize: 13px, fontWeight: '400' }
  body-compact: { fontFamily: Inter, fontSize: 12px, fontWeight: '400' }
  label-code: { fontFamily: JetBrains Mono, fontSize: 12px }
  label-numeric: { fontFamily: JetBrains Mono, fontSize: 13px, fontWeight: '500' }
  label-micro: { fontFamily: JetBrains Mono, fontSize: 10px, fontWeight: '500' }
rounded:
  DEFAULT: 3px
  md: 6px
---

> **Nota.** Este archivo describe los mockups originales, con acento azul y un
> color por estado. La interfaz implementada evolucionó a una escala de grises
> sobre grafito, con las proporciones del modo oscuro de macOS: el estilo
> vigente es el de `src/vision_contador/ui/tema.py`, que es además el único
> sitio donde se tocan los colores y los redondeos. Se conserva como referencia
> de la maquetación y de las pantallas.

## Marca y estilo

Sistema de diseño para instrumentación de escritorio: precisión científica, rigor académico y
retroalimentación visual determinista. Paradigma de estación de trabajo de laboratorio industrial,
con ergonomía densa tipo Qt/PySide6, paneles de instrumentación y analizadores de señal
profesionales. Rechaza los motivos de la web de consumo: nada de *hero*, desenfoques ambientales ni
redondeos exagerados. Densidad estructural, bordes de panel nítidos, estados visuales sin latencia.

## Colores

Modo oscuro calibrado, para reducir la fatiga visual en sesiones largas y dar contraste sin
concesiones contra el video y las cajas de detección.

- **Primario `#3B82F6`** — pipeline de cámara activo, pestaña seleccionada, ROI calibrada,
  disparadores de ejecución primarios.
- **Secundario `#263241`** — separadores, divisores de panel, barras de herramientas, marcos
  inactivos.
- **Neutro `#0F141A`** — lienzo raíz de la ventana.
- **Estados**
  - `status-processing` `#F5B700` — carga de pesos, buffering de cuadros, pasadas de inferencia.
  - `status-ok` `#22C55E` — detecciones sobre el umbral, handshake serial válido.
  - `status-error` `#EF4444` — cámara perdida, paquetes seriales caídos, hardware desconectado.
  - `console-bg` `#0B0E13` — lienzo del terminal serial.

## Tipografía

- **Interfaz (`Inter`)** — controles, inspectores y lecturas de estado. Los encabezados de panel usan
  `headline-sm` en mayúsculas con tracking `0.06em`.
- **Telemetría (`JetBrains Mono`)** — valores numéricos, tiempos de inferencia (ms), confianzas
  (0.00–1.00), coordenadas `[x, y, w, h]` y transacciones del puerto COM. Monoespaciado para que la
  métrica fluctuante no reacomode el layout.

## Layout y espaciado

Subrejilla densa de 4/8 px típica de un espacio de trabajo Qt.

- Margen del lienzo: 12 px entre el marco de la ventana y los paneles hijos.
- Separación entre paneles: 12 px.
- Padding interno: 4 px (ítems), 6 px (botones, combos, celdas), 8 px (filas de control),
  12 px (interior de paneles), 16 px (visores de video y gráficos).

## Elevación

La profundidad se transmite con capas tonales planas y trazos de perímetro de bajo contraste, nunca
con sombras arrojadas ni desenfoques translúcidos.

- **Base `#0F141A`** — superficie anfitriona.
- **Nivel 1 — paneles `#161D26`** — barras de herramientas, inspectores, grupos de parámetros.
  Contorno continuo de 1 px en `#263241`.
- **Nivel 2 — controles hundidos `#0B0E13`** — campos de texto, monitor serial, visores. Se hunden
  dentro del nivel 1 con borde de 1 px `#263241`.
- **Sombras** — omitidas por completo.

## Formas

- Paneles, grupos y visores: radio uniforme de **6 px**.
- Controles interactivos (botones, desplegables, campos): **6 px**, en continuidad con su contenedor.
- Insignias, etiquetas y viñetas de estado: **3 px** o completamente cuadradas. Nunca forma de
  píldora, salvo el indicador de estado principal de la barra superior.

## Componentes

### Botones
- **Primario** — relleno `#3B82F6`, texto `#E6EDF3`, radio 6 px. Hover `#2563EB`, pulsado `#1D4ED8`.
- **Secundario** — fondo `#161D26`, borde 1 px `#263241`, texto `#E6EDF3`. Hover rellena `#263241`.

### Campos y steppers
- Fondo `#0B0E13`, borde 1 px `#263241`, texto `#E6EDF3`, `JetBrains Mono 12px`.
- El foco de teclado lleva el borde a `#3B82F6`, sin halo difuso.

### Paneles
- Fondo `#161D26`, borde 1 px `#263241`.
- Barra de encabezado: alto 28 px, fondo `#121820`, texto `#8B98A8` en `headline-sm` mayúsculas.

### Casillas y radios
- Casilla 14x14 px, fondo `#0B0E13`, borde 1 px `#263241`, radio 3 px. Marcada: relleno `#3B82F6`
  con palomita blanca.

### Indicadores de estado
- LED de conexión: círculo de 8x8 px. Verde `#22C55E` conectado, amarillo `#F5B700` en handshake,
  rojo `#EF4444` desconectado.

### Consola serial
- Fondo `#0B0E13`, borde 1 px `#263241`, `JetBrains Mono 12px`.
- Marcas de tiempo en `#8B98A8`, comandos enviados en `#3B82F6`, recibidos en `#22C55E`,
  errores en `#EF4444`.

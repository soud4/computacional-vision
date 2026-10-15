/*
 * Visión Contador — firmware del ESP32 (actuador por WiFi)
 *
 * Hace exactamente lo mismo que el sketch del Arduino UNO y habla EL MISMO
 * protocolo de docs/protocolo.md. La única diferencia es por dónde viajan las
 * líneas: aquí por un socket TCP en vez de por el cable USB.
 *
 * El ESP32 crea su propia red WiFi (modo SoftAP), de modo que no depende del
 * WiFi del aula, que casi siempre aísla a los clientes entre sí y bloquearía
 * la conexión. La laptop se asocia a esa red y conecta a 192.168.4.1:3333.
 *
 *   OJO: mientras la laptop esté asociada a esta red no tendrá Internet, y
 *   edge-tts necesita red para sintetizar frases nuevas. Reproduzca una vez
 *   cada frase antes de la demostración para que queden en cache/voz/.
 *
 * ---------------------------------------------------------------------------
 * CONEXIONES — ESP32-WROOM-32 DevKit V1 de 30 pines
 *
 * Confirme la serigrafía de SU placa antes de cablear: el mapa de pines cambia
 * entre variantes y entre clones. Guíese por los nombres (D13, D25…), no por la
 * posición física.
 *
 *   LCD 16x2 con espaldera I2C PCF8574  (recomendado: solo dos cables)
 *     SDA -> GPIO21    SCL -> GPIO22
 *     VCC -> 3V3       GND -> GND
 *     Alimente la espaldera a 3.3 V, NO a 5 V: sus resistencias de pull-up
 *     meterían 5 V en SDA/SCL, que son entradas del ESP32, y el ESP32 no
 *     tolera 5 V (máximo absoluto 3.6 V).
 *
 *   LEDs, cada uno con 150 Ω en serie hacia GND
 *     Amarillo -> GPIO25    Verde -> GPIO26    Rojo -> GPIO27
 *     150 Ω, no 220 Ω: el GPIO da 3.3 V, no los 5 V del UNO.
 *     Use un LED verde clásico (Vf ≈ 2.1 V). Uno de alto brillo (Vf ≈ 3.1 V)
 *     se verá apagado porque a 3.3 V apenas queda margen.
 *
 *   Pulsador -> GPIO32 contra GND, con el pull-up interno (sin resistencia).
 *
 * PINES QUE NO SE DEBEN USAR
 *   GPIO 6–11   flash SPI interna; en la placa de 30 pines ni se exponen.
 *   GPIO 34–39  solo entrada y SIN pull-up interno: digitalWrite() no hace
 *               nada y un pulsador ahí da lecturas aleatorias.
 *   GPIO 0,2,12,15  pines de arranque. Cablear algo ahí puede impedir que el
 *               programa se suba o que la placa arranque.
 *   GPIO 1,3    UART0, el puerto de programación y la consola serie.
 *
 * Los pines elegidos arriba (21, 22, 25, 26, 27, 32) están libres de todas
 * estas restricciones.
 *
 * BIBLIOTECA NECESARIA: "LiquidCrystal I2C" de Frank de Brabander.
 * Si monta la LCD en paralelo en vez de por I2C, use <LiquidCrystal.h> como en
 * el sketch del UNO y revise los niveles (ver docs/PLAN_ESP32.md §3.4).
 * ---------------------------------------------------------------------------
 */

#include <WiFi.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// --- Identidad -------------------------------------------------------------
const char IDENTIDAD[] = "ESP32";

// --- Red -------------------------------------------------------------------
const char SSID_AP[] = "VisionContador";
const char CLAVE_AP[] = "contador2026";   // mínimo 8 caracteres
const uint16_t PUERTO_TCP = 3333;

// --- Pines -----------------------------------------------------------------
const uint8_t PIN_SDA = 21;
const uint8_t PIN_SCL = 22;

const uint8_t PIN_LED_AMARILLO = 25;
const uint8_t PIN_LED_VERDE    = 26;
const uint8_t PIN_LED_ROJO     = 27;
const uint8_t PIN_PULSADOR     = 32;

// --- Constantes ------------------------------------------------------------
const uint8_t COLUMNAS = 16;
const uint8_t FILAS = 2;
const uint8_t DIRECCION_LCD = 0x27;   // 0x3F en algunas espalderas

const unsigned long MS_ANTIRREBOTE = 40;
const unsigned long MS_PARPADEO = 250;

LiquidCrystal_I2C lcd(DIRECCION_LCD, COLUMNAS, FILAS);
WiFiServer servidor(PUERTO_TCP);
WiFiClient cliente;

// --- Estado ----------------------------------------------------------------
String entrada = "";
bool pensando = false;
unsigned long ultimoParpadeo = 0;
bool estadoParpadeo = false;

int lecturaPulsador = HIGH;
int ultimaLecturaPulsador = HIGH;
unsigned long cambioPulsador = 0;

// --- Utilidades ------------------------------------------------------------
void apagarLeds() {
  digitalWrite(PIN_LED_AMARILLO, LOW);
  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_ROJO, LOW);
}

void encenderSolo(uint8_t pin) {
  apagarLeds();
  digitalWrite(pin, HIGH);
}

void escribirFila(uint8_t fila, const String &texto) {
  lcd.setCursor(0, fila);
  // Se rellena hasta las 16 columnas para borrar lo que hubiera antes: la LCD
  // no limpia sola el resto de la línea.
  for (uint8_t i = 0; i < COLUMNAS; i++) {
    lcd.write(i < texto.length() ? texto[i] : ' ');
  }
}

void responder(const String &linea) {
  if (cliente && cliente.connected()) {
    cliente.print(linea);
    cliente.print('\n');
  }
}

// --- Órdenes ---------------------------------------------------------------
// Idéntico al del UNO salvo que la respuesta sale por el socket.
void procesar(const String &orden) {
  if (orden.length() == 0) {
    return;
  }

  if (orden == "PING") {
    responder("OK");
    return;
  }

  if (orden == "ID") {
    responder(String("ID:") + IDENTIDAD);
    return;
  }

  if (orden == "PENSANDO") {
    pensando = true;
    ultimoParpadeo = millis();
    lcd.clear();
    escribirFila(0, "Pensando...");
    responder("OK");
    return;
  }

  if (orden.startsWith("LCD1:")) {
    pensando = false;
    escribirFila(0, orden.substring(5));
    responder("OK");
    return;
  }

  if (orden.startsWith("LCD2:")) {
    pensando = false;
    escribirFila(1, orden.substring(5));
    responder("OK");
    return;
  }

  if (orden.startsWith("LED:")) {
    pensando = false;
    String color = orden.substring(4);
    if (color == "AMARILLO") {
      encenderSolo(PIN_LED_AMARILLO);
    } else if (color == "VERDE") {
      encenderSolo(PIN_LED_VERDE);
    } else if (color == "ROJO") {
      encenderSolo(PIN_LED_ROJO);
    } else if (color == "NINGUNO") {
      apagarLeds();
    } else {
      responder("ERR:color desconocido");
      return;
    }
    responder("OK");
    return;
  }

  responder(String("ERR:orden desconocida ") + orden);
}

// --- Ciclo principal -------------------------------------------------------
void setup() {
  pinMode(PIN_LED_AMARILLO, OUTPUT);
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  pinMode(PIN_PULSADOR, INPUT_PULLUP);
  apagarLeds();

  Wire.begin(PIN_SDA, PIN_SCL);
  lcd.init();
  lcd.backlight();
  escribirFila(0, "Vision Contador");
  escribirFila(1, "Creando red...");

  entrada.reserve(32);
  Serial.begin(115200);   // solo para depurar por USB

  WiFi.mode(WIFI_AP);
  WiFi.softAP(SSID_AP, CLAVE_AP);
  servidor.begin();
  servidor.setNoDelay(true);   // sin esto Nagle retrasa las líneas cortas

  IPAddress ip = WiFi.softAPIP();
  Serial.print("SoftAP en ");
  Serial.println(ip);
  escribirFila(0, SSID_AP);
  escribirFila(1, ip.toString());
}

void loop() {
  // --- Un solo cliente a la vez: la laptop ---
  if (!cliente || !cliente.connected()) {
    WiFiClient nuevo = servidor.available();
    if (nuevo) {
      cliente.stop();
      cliente = nuevo;
      entrada = "";
      responder("READY");
    }
  }

  // --- Órdenes que llegan por el socket, una por línea ---
  while (cliente && cliente.connected() && cliente.available() > 0) {
    char c = cliente.read();
    if (c == '\n') {
      entrada.trim();
      procesar(entrada);
      entrada = "";
    } else if (c != '\r') {
      entrada += c;
    }
  }

  // --- Pulsador con antirrebote ---
  int lectura = digitalRead(PIN_PULSADOR);
  if (lectura != ultimaLecturaPulsador) {
    cambioPulsador = millis();
    ultimaLecturaPulsador = lectura;
  }
  if ((millis() - cambioPulsador) > MS_ANTIRREBOTE && lectura != lecturaPulsador) {
    lecturaPulsador = lectura;
    // INPUT_PULLUP: el pulsador cierra a GND, así que pulsar da LOW.
    if (lecturaPulsador == LOW) {
      responder("BTN");
    }
  }

  // --- Parpadeo del LED amarillo mientras la laptop piensa ---
  if (pensando) {
    if (millis() - ultimoParpadeo >= MS_PARPADEO) {
      ultimoParpadeo = millis();
      estadoParpadeo = !estadoParpadeo;
      apagarLeds();
      digitalWrite(PIN_LED_AMARILLO, estadoParpadeo ? HIGH : LOW);
    }
  }
}

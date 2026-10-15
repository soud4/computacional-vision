/*
 * Visión Contador — firmware del Arduino
 *
 * El Arduino actúa SOLO como actuador e interfaz física. No procesa imágenes
 * ni toma decisiones: lee el pulsador, muestra lo que le mandan en la LCD y
 * enciende el LED que le indican. Todo el procesamiento ocurre en la laptop.
 *
 * El protocolo está documentado en docs/protocolo.md y lo implementan igual
 * este sketch, adapters/arduino_serial.py y adapters/arduino_mock.py.
 *
 * Conexiones (Arduino UNO):
 *
 *   LCD 16x2 en modo 4 bits (ahorra cuatro pines frente al modo 8 bits):
 *     RS -> D12    E -> D11
 *     D4 -> D5     D5 -> D4     D6 -> D3     D7 -> D2
 *     VSS, RW y K a GND; VDD y A a 5 V; V0 al cursor de un potenciómetro de
 *     10 kΩ para el contraste.
 *
 *   LED amarillo -> D6, LED verde -> D7, LED rojo -> D8
 *     cada uno con una resistencia de 220 Ω en serie hacia GND.
 *
 *   Pulsador -> D9 contra GND. No lleva resistencia: se usa el pull-up interno,
 *     de modo que el pin está en HIGH en reposo y cae a LOW al pulsar.
 *
 * Los pines de datos de la LCD (D2..D5) y los de los LEDs y el pulsador
 * (D6..D9) no se solapan, así que el cableado entra tal cual en una protoboard.
 */

#include <LiquidCrystal.h>

// --- Pines -----------------------------------------------------------------
const uint8_t PIN_LCD_RS = 12;
const uint8_t PIN_LCD_E  = 11;
const uint8_t PIN_LCD_D4 = 5;
const uint8_t PIN_LCD_D5 = 4;
const uint8_t PIN_LCD_D6 = 3;
const uint8_t PIN_LCD_D7 = 2;

const uint8_t PIN_LED_AMARILLO = 6;
const uint8_t PIN_LED_VERDE    = 7;
const uint8_t PIN_LED_ROJO     = 8;
const uint8_t PIN_PULSADOR     = 9;

// --- Constantes ------------------------------------------------------------
const unsigned long BAUDIOS = 9600;

// Nombre con el que esta placa se identifica al responder a la orden ID.
// Si conecta dos placas a la vez, cada una debe tener el suyo.
const char IDENTIDAD[] = "UNO";
const uint8_t COLUMNAS = 16;
const uint8_t FILAS = 2;

// Tiempo que debe mantenerse estable el pulsador para darlo por válido.
// Sin este antirrebote una sola pulsación dispara tres capturas seguidas.
const unsigned long MS_ANTIRREBOTE = 40;

// Período de parpadeo del LED amarillo mientras la laptop está procesando.
const unsigned long MS_PARPADEO = 250;

LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_E, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

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

// --- Órdenes ---------------------------------------------------------------
void procesar(const String &orden) {
  if (orden.length() == 0) {
    return;
  }

  if (orden == "PING") {
    Serial.println("OK");
    return;
  }

  // La laptop pregunta ID al conectar para saber cuál de las placas contestó.
  if (orden == "ID") {
    Serial.print("ID:");
    Serial.println(IDENTIDAD);
    return;
  }

  if (orden == "PENSANDO") {
    pensando = true;
    ultimoParpadeo = millis();
    lcd.clear();
    escribirFila(0, "Pensando...");
    Serial.println("OK");
    return;
  }

  if (orden.startsWith("LCD1:")) {
    pensando = false;
    escribirFila(0, orden.substring(5));
    Serial.println("OK");
    return;
  }

  if (orden.startsWith("LCD2:")) {
    pensando = false;
    escribirFila(1, orden.substring(5));
    Serial.println("OK");
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
      Serial.println("ERR:color desconocido");
      return;
    }
    Serial.println("OK");
    return;
  }

  Serial.print("ERR:orden desconocida ");
  Serial.println(orden);
}

// --- Ciclo principal -------------------------------------------------------
void setup() {
  pinMode(PIN_LED_AMARILLO, OUTPUT);
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  // El pull-up interno evita tener que montar una resistencia para el pulsador.
  pinMode(PIN_PULSADOR, INPUT_PULLUP);
  apagarLeds();

  lcd.begin(COLUMNAS, FILAS);
  lcd.clear();
  escribirFila(0, "Vision Contador");
  escribirFila(1, "Listo");

  entrada.reserve(32);
  Serial.begin(BAUDIOS);
  Serial.println("READY");
}

void loop() {
  // --- Órdenes que llegan de la laptop, una por línea ---
  while (Serial.available() > 0) {
    char c = Serial.read();
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
      Serial.println("BTN");
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

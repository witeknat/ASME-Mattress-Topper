const int C0 = 13;
const int C1 = 12;
const int C2 = 11;
const int C3 = 10;

int valuesAnalog[8]; // Stores readings from channels 0-3 and 8-11
int valuesA0[8]; // Stores readings from channels 0-3 and 8-11

int analogPins[8] = {A8, A9, A10, A11, A12, A13, A14, A15};

void setup() {
    pinMode(C0, OUTPUT);
    pinMode(C1, OUTPUT);
    pinMode(C2, OUTPUT);
    pinMode(C3, OUTPUT);
    Serial.begin(9600);
}

void loop() {
    // Read from channels 0-3
    for (int i = 0; i < 4; i++) {
        digitalWrite(C0, bitRead(i, 0));
        digitalWrite(C1, bitRead(i, 1));
        digitalWrite(C2, bitRead(i, 2));
        digitalWrite(C3, bitRead(i, 3));

        delay(50); // Allow MUX to settle
        valuesA0[i] = analogRead(A0); // Store reading
        valuesAnalog[i] = analogRead(analogPins[i]);
    }


    // Read from channels 8-11
    for (int i = 8; i < 12; i++) {
        digitalWrite(C0, bitRead(i, 0));
        digitalWrite(C1, bitRead(i, 1));
        digitalWrite(C2, bitRead(i, 2));
        digitalWrite(C3, bitRead(i, 3));

        delay(50);
        valuesA0[i - 4] = analogRead(A0); // Store readings in next set of indices
        valuesAnalog[i - 4] = analogRead(analogPins[i-4]);
    }

    

    Serial.println("Sensors 0-7 Readings:");
    for (int i = 0; i < 8; i++) {
        Serial.print("A0 Value[");
        Serial.print(i);
        Serial.print("] = ");
        Serial.println(valuesA0[i]);
    }
   
     Serial.println("Sensors 8-15 Readings:");
     for (int i = 0; i < 8; i++) {
         Serial.print("Analog Value[");
         Serial.print(i);
         Serial.print("] = ");
        Serial.println(valuesAnalog[i]);
     }
    delay(500); // Small pause before next loop
}




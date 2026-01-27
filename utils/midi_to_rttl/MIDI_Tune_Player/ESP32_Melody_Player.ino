// ESP32_Melody_Player.ino
// ----------------------------------------------------------------------
// Plays the melody data using the standard Arduino tone()/noTone() API.
// Note: ESP32 cores often implement tone() using the LEDC/Timer peripheral
// internally, but this sketch avoids direct LEDC calls.
// ----------------------------------------------------------------------

// Includes the generated data files
#include "pitches.h"
#include "melody_data.h" 

// --- Configuration ---
// The GPIO pin connected to the passive buzzer or speaker
// Recommended pins for simple output on ESP32 (avoid input-only pins like GPIO 34-39)
const int BUZZZER_PIN = 25; 

// --- Setup ---
void setup() {
  Serial.begin(115200);
  Serial.println("\n--- ESP32 Melody Player (Arduino Tone API) ---");
  
  // Initialize the buzzer pin as an output.
  pinMode(BUZZZER_PIN, OUTPUT);
}

// --- Main Loop ---
void loop() {
  playMelody();
  
  // Halt the loop after the song finishes to prevent continuous playback.
  while(true) {
    delay(1000); 
  }
}

// --- Melody Play Function ---
void playMelody() {
  // Iterate through the notes in the melody_data array.
  for (int thisNote = 0; thisNote < melody_length; thisNote++) {
    
    // Read pitch and duration from the arrays.
    int pitch = melody[thisNote];
    int noteDuration = durations[thisNote];
    
    // Check if the pitch is a rest (REST is defined as 0 in pitches.h).
    if (pitch != REST) {
      // Plays a tone (PWM signal) at the specified pitch for the duration.
      // On ESP32, this tone() function may use one of the available timers.
      tone(BUZZZER_PIN, pitch, noteDuration);
      
      Serial.printf("Playing Note: %d Hz for %d ms\n", pitch, noteDuration);
    } else {
      // Stop the tone for a REST.
      noTone(BUZZZER_PIN); 
      Serial.printf("Rest for %d ms\n", noteDuration);
    }

    // Pause for the exact duration of the note/rest.
    delay(noteDuration);

    // Stop the tone explicitly to ensure a clean break before the next note/pause.
    noTone(BUZZZER_PIN); 

    // Pause for a small interval before the next note starts.
    // Assuming PAUSE_BETWEEN_NOTES_MS is defined in melody_data.h (or using a fixed value).
    #ifdef PAUSE_BETWEEN_NOTES_MS
      delay(PAUSE_BETWEEN_NOTES_MS);
    #else
      delay(20); // Default pause if macro not found (20ms)
    #endif
  }
  
  Serial.println("Melody finished.");
}

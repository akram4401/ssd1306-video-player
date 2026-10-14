/*
 * ESP32 SD-Card "Video" Player for SSD1306 128x64 OLED
 * ---------------------------------------------------
 * Plays raw .dat frame files: each frame = exactly 1024 bytes
 * (128 * 64 / 8), which is a straight dump of the SSD1306 buffer.
 *
 * Target board: generic ESP32 (ESP32 Dev Module / WROOM-32).
 * Also works on ESP32-S3 — just change the pin numbers below.
 */

#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ------------------------------------------------------------------
// Display geometry
// ------------------------------------------------------------------
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT   64
#define OLED_ADDR      0x3C

// ------------------------------------------------------------------
// Pin configuration  --  CHANGE THESE TO MATCH YOUR WIRING
// ------------------------------------------------------------------
// I2C (OLED)
#define I2C_SDA        21
#define I2C_SCL        22

// SPI (SD card)
#define SPI_MOSI       23
#define SPI_MISO       19
#define SPI_SCK        18
#define SPI_CS          5

// ------------------------------------------------------------------
// Globals
// ------------------------------------------------------------------
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

File infile;

const int SD_RETRY_COUNT    = 5;
const int SD_RETRY_DELAY_MS = 1000;

// Forward declaration (Arduino auto-prototypes, but explicit is safer)
void playVideo(const char* filename);

// ==================================================================
// SD card init with retry
// ==================================================================
bool initializeSD() {
  // Configure the SPI bus with our pins (SCK, MISO, MOSI, SS)
  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI, SPI_CS);

  for (int attempt = 1; attempt <= SD_RETRY_COUNT; attempt++) {
    Serial.printf("Attempting SD card initialization (attempt %d/%d)...\n",
                  attempt, SD_RETRY_COUNT);

    if (SD.begin(SPI_CS, SPI, 4000000)) {   // 4 MHz SPI clock
      Serial.println("[OK] SD card mounted successfully!");
      return true;
    }

    Serial.println("[FAIL] SD card mount failed.");
    SD.end();                                // release before retrying
    if (attempt < SD_RETRY_COUNT) delay(SD_RETRY_DELAY_MS);
  }

  Serial.println("[FAIL] SD card initialization failed after all attempts.");
  return false;
}

// ==================================================================
// setup()
// ==================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== ESP32 SD Video Player ===");

  // ---------------- OLED ----------------
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);                     // 400 kHz

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("SSD1306 init failed at 0x3C, trying 0x3D...");
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println("SSD1306 init failed on both addresses! Halting.");
      while (true) delay(1000);
    }
  }
  Serial.println("[OK] OLED initialized.");

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("ESP32 Video Player");
  display.setCursor(0, 20);
  display.println("Initializing SD...");
  display.display();
  delay(800);

  // ---------------- SD ----------------
  if (!initializeSD()) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("SD Card Error!");
    display.setCursor(0, 20);
    display.println("Check card and");
    display.setCursor(0, 32);
    display.println("restart device.");
    display.display();

    while (true) {
      Serial.println("SD init failed. Check the card and restart.");
      delay(5000);
    }
  }

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("SD Ready!");
  display.setCursor(0, 20);
  display.println("Scanning for");
  display.setCursor(0, 32);
  display.println("video files...");
  display.display();
  delay(800);

  // ---------------- Scan root directory ----------------
  Serial.println("\nScanning for .dat video files...");

  File root = SD.open("/");
  if (!root) {
    Serial.println("Failed to open root directory!");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("No files found!");
    display.display();
    delay(2000);
    return;
  }

  int  fileCount  = 0;
  bool videoFound = false;

  File file = root.openNextFile();
  while (file) {
    if (!file.isDirectory()) {

      // Core 3.x returns the full path from name(); normalize it.
      String rawName = file.name();
      int slashIdx   = rawName.lastIndexOf('/');
      String baseName = (slashIdx >= 0) ? rawName.substring(slashIdx + 1) : rawName;
      String fullPath = (slashIdx >= 0) ? rawName : ("/" + rawName);

      if (baseName.endsWith(".dat") || baseName.endsWith(".DAT")) {
        fileCount++;
        videoFound = true;

        Serial.printf("Found video: %s\n", fullPath.c_str());

        char line[24];
        snprintf(line, sizeof(line), "%.21s", baseName.c_str());

        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Found:");
        display.setCursor(0, 12);
        display.println(line);
        display.setCursor(0, 34);
        display.println("Starting playback...");
        display.display();
        delay(800);

        playVideo(fullPath.c_str());

        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Video complete!");
        display.setCursor(0, 20);
        display.println("Next video...");
        display.display();
        delay(2000);
      }
    }
    file = root.openNextFile();
  }

  root.close();

  if (!videoFound) {
    Serial.println("No .dat video files found!");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("No videos found!");
    display.display();
    delay(2000);
  }

  // ---------------- Done ----------------
  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(20, 20);
  display.println("Done!");
  display.display();

  Serial.printf("\nPlayback complete. Processed %d video(s).\n", fileCount);
}

// ==================================================================
// loop()
// ==================================================================
void loop() {
  delay(1000);   // all work happens in setup()
}

// ==================================================================
// playVideo()
// ==================================================================
void playVideo(const char* filename) {
  Serial.printf("\nPlaying: %s\n", filename);

  infile = SD.open(filename, FILE_READ);
  if (!infile) {
    Serial.printf("Failed to open file: %s\n", filename);
    return;
  }

  const int frameSize = (SCREEN_WIDTH * SCREEN_HEIGHT) / 8;   // 1024 bytes
  uint8_t buffer[frameSize];

  int frameCount = 0;

  const unsigned long ftime = 1000000UL / 60UL;   // target ~60 fps
  unsigned long t1             = micros();
  unsigned long lastUpdateTime = millis();
  int           lastFrameCount = 0;

  Serial.println("Starting playback...");

  while (infile.available()) {
    int bytesRead = infile.read(buffer, frameSize);

    if (bytesRead <= 0) {
      Serial.println("No bytes read — end of file.");
      break;
    }

    if (bytesRead != frameSize) {
      Serial.printf("Incomplete frame (%d bytes, expected %d). Stopping.\n",
                    bytesRead, frameSize);
      break;
    }

    frameCount++;

    // ---- Frame pacing ----
    unsigned long targetTime = t1 + (ftime * (unsigned long)frameCount);
    while ((long)(micros() - targetTime) < 0) {
      // busy-wait for accurate timing; add yield() if you need
      // to keep the WiFi/BT stack alive
      // yield();
    }

    // ---- Push frame to the OLED ----
    memcpy(display.getBuffer(), buffer, frameSize);
    display.display();

    // ---- Stats once per second ----
    if (millis() - lastUpdateTime >= 1000) {
      float fps = (frameCount - lastFrameCount) * 1000.0f /
                  (float)(millis() - lastUpdateTime);
      Serial.printf("Playing: %d frames, %.1f fps\n", frameCount, fps);
      lastUpdateTime = millis();
      lastFrameCount = frameCount;
    }

    // ---- Allow user to stop with 's' over serial ----
    if (Serial.available()) {
      char c = Serial.read();
      if (c == 's' || c == 'S') {
        Serial.println("Playback stopped by user.");
        break;
      }
    }
  }

  infile.close();

  // ---- Playback statistics ----
  unsigned long totalTime = micros() - t1;
  float secs      = totalTime / 1000000.0f;
  float actualFps = (frameCount > 0 && secs > 0) ? frameCount / secs : 0.0f;

  Serial.printf("Playback complete:\n");
  Serial.printf("  Frames : %d\n", frameCount);
  Serial.printf("  Time   : %.2f s\n", secs);
  Serial.printf("  Avg FPS: %.2f\n", actualFps);
  Serial.printf("  File   : %s\n\n", filename);
}
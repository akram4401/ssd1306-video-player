#include <FS.h>
#include <LittleFS.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// file
File infile;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("RUN: LittleFS video player");

  // OLED init
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 init failed!");
    for(;;);
  }
  display.clearDisplay();
  display.display();

  // LittleFS init
  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed!");
    return;
  }
  Serial.println("LittleFS mounted.");

  // play video
  playVideo("/11.dat");

  // Done
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(10, 30);
  display.println("Done!");
  display.display();
}

void loop() {
  // nothing
}

void playVideo(const char* filename) {
  infile = LittleFS.open(filename, "r");
  if (!infile) {
    Serial.println("Failed to open .dat file");
    return;
  }

  const int frameSize = 1024;  // 128*64 / 8 = 1024
  uint8_t buffer[frameSize];
  int frameCount = 0;
  unsigned long ftime = 1000000 / 60; // target ~60 fps
  unsigned long t1 = micros();

  while (infile.available()) {
    int bytesRead = infile.read(buffer, frameSize);
    frameCount++;

    // wait sync
    while (micros() < t1 + (ftime * frameCount)) {
      // busy wait
    }

    // copy frame data to SSD1306 buffer
    if (bytesRead == frameSize) {
      memcpy(display.getBuffer(), buffer, frameSize);
      display.display();
    } else {
      Serial.println("Frame incomplete, stopping.");
      break;
    }
  }
  infile.close();

  float secs = (micros() - t1) / 1000000.0;
  Serial.printf("RATE: %d frames, %.2f sec, %.2f fps\n", frameCount, secs, frameCount / secs);
}

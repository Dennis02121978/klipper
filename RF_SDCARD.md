# SD-Karte im Drucker (rf_sdcard)

RF1000, RF2000 und RF2000 v2 haben auf dem Board einen Kartenleser. Unter der RF-Firmware wurde von dort gedruckt. Mit diesem Modul liest Klipper die Karte über den ATmega2560. Eine neue MCU-Firmware ist dafür nicht nötig, es nutzt die SPI-Befehle, die schon drin sind. Die Karte wird nur gelesen, nie beschrieben.

## Einrichten

In die `printer.cfg`:

```
[rf_sdcard]
cs_pin: PB0
detect_pin: ^!PD2
```

- `cs_pin`: Chip-Select der Karte, beim ATmega2560 der RF-Drucker `PB0`.
- `detect_pin`: Kartenerkennung, beim RF2000 und RF2000 v2 `^!PD2`. Der RF1000 hat keine, dann die Zeile weglassen. Die Karte wird dann beim Öffnen des Menüs gesucht.
- `folder` (Vorgabe `SD-Karte`): Unterordner im G-Code-Ordner für die Kopien.
- `spi_speed` (Vorgabe 4000000), `pace_factor` (Vorgabe 1.3), `burst` (Vorgabe 24): nur zum Feintuning.

Im Menü erscheint die Karte in der Dateiliste (`type: vsdlist`) als eigener Eintrag, wenn `card_text` gesetzt ist, siehe `config/rf_display.cfg`.

## Befehle

- `RF_SD_LIST`: Dateien auf der Karte anzeigen (`.gcode`, `.gco`, `.g`, `.nc`, auch in Unterordnern bis Tiefe 3).
- `RF_SD_PRINT FILE="Ordner/Name.gcode"`: Datei auf den Raspberry Pi kopieren und drucken.
- `RF_SD_COPY FILE="Name.gcode"`: nur kopieren. `FILE=*` kopiert alle Dateien, danach stehen sie in Mainsail unter `SD-Karte`.
- `RF_SD_TEST KB=256`: Lesegeschwindigkeit messen.

Status für Makros: `printer.rf_sdcard.present`, `.ready`, `.files`, `.busy`, `.progress`, `.error`.

## Warum wird kopiert und nicht direkt von der Karte gedruckt?

Alle Daten der Karte laufen über die serielle Verbindung zum ATmega (250000 Baud), dieselbe, über die auch alle Fahrbefehle gehen. Beim Drucken direkt von der Karte würden sich beide die Leitung teilen. Deshalb wird die Datei vorher kopiert und dann normal gedruckt. Eine Datei, die schon kopiert und unverändert ist (Größe und Änderungszeit), wird nicht noch einmal kopiert.

## Geschwindigkeit

Gemessen am RF2000: etwa 13 KB/s, also gut 2 Minuten für 1,7 MB. Dafür muss der USB-Wandler (FTDI) auf 1 ms Wartezeit stehen (`latency_timer`). Das Paket „Firmware Updater ATmega“ von 3D-Artmaker stellt das ab v1.5.5 ein. Mit der Vorgabe von 16 ms sind es nur etwa 4 KB/s. Der Sendepuffer des ATmega fasst nur eine Antwort, deshalb schickt das Modul die Lesebefehle im Takt der seriellen Leitung (`pace_factor`).

## Grenzen

- Nur FAT12, FAT16 und FAT32. exFAT (oft bei Karten über 32 GB) und NTFS gehen nicht.
- Während eines Drucks wird die Karte nicht gelesen.
- Ältere Karten (SD 1.0) mögen kein Einstecken im Betrieb. Dann `FIRMWARE_RESTART` mit eingesteckter Karte.

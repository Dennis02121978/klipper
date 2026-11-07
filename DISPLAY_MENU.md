# Display und Menü wie in der RF-Firmware

Mit `config/rf_display.cfg` zeigt das 20x4-Display eines RF2000 / RF2000 v2 unter Klipper die gleichen Startseiten und das gleiche Menü wie die RF-Repetier-Firmware. Texte und Aufbau stammen aus `uimenu.h` und `uilang.h` der Original-Firmware (deutsch).

## Einbauen

1. Klipper aus diesem Fork verwenden. Nötig sind die Änderungen in `display/hd44780.py` (Umlaute), `display/menu.py` (Seiten blättern) und `z_sense_offset.py` (`SET_Z_SENSE_OFFSET`).
2. `rf_display.cfg` in den Config-Ordner legen und in der `printer.cfg` einbinden:

```ini
[include rf_display.cfg]
```

3. Unter `[display]` eintragen:

```ini
display_group: rf_page1
menu_root: rf
menu_pages: rf_page1, rf_page_mod, rf_page2, rf_page3, rf_page4
menu_show_back: False
menu_reverse_input: True
hd44780_charset: western
```

`hd44780_charset: western` ist der Zeichensatz des RF2000-Displays (Repetier `UI_DISPLAY_CHARSET 2`), beim RF1000 `a00`. `menu_show_back: False` entfernt den Eintrag „..“ aus den Listen, zurück geht über die Zurück-Taste. Das Gradzeichen kommt wie in Repetier aus einem eigenen Zeichen (`~degrees~`), Mikrometer stehen als „um“.

Die Seiten sind für 20 Spalten gebaut (Repetier-Vorlagen für `UI_COLS 20`). Am RF1000 mit 16 Spalten würden Zeilen abgeschnitten.

4. Klipper-Dienst neu starten: `sudo systemctl restart klipper`.

## Bedienung

- **Startanzeige:** Hoch und runter blättern durch die Seiten, zurück springt auf Seite 1, OK öffnet das Menü.
- **Im Menü:** Hoch und runter wählen aus, OK öffnet oder ändert, zurück geht eine Ebene zurück.

## Startseiten

| Seite | Inhalt |
|---|---|
| 1 | Temperatur aktiver Extruder und Bett (Ist/Soll), Z mit Ausgleich (`K` = Bettnetz aktiv, `?` = nicht referenziert), Kraft `P` und Lüfter `L`, Statuszeile |
| 2 | Kraft und Geschwindigkeit `V`, Z-Offset `zO` in µm und Bettnetz `M`, Sense Offset `sO` in µm mit Schwelle (`@` an, `^` aus mit Restwert, sonst `Aus`), Z |
| 3 | X, Y, Z und aktuelle Geschwindigkeit |
| 4 | E0, E1 und Bett mit Ist/Soll und Heizleistung |
| 5 | Datei, Druckzeit, Filament, Layer des aktuellen Drucks |

## Menü

- **Schnelleinstellung:** Druck abbrechen (mit Rückfrage), Home alle, Motoren ausschalten, Objekt ausgeben, Geschwindigkeit und Fluss in %, Heizbett parken, Licht, Neustart (mit Rückfrage)
- **Position** (nicht beim Drucken): Home alle/X/Y/Z, X/Y/Z fahren, Extruder bewegen
- **Pause Position** (nur in der Pause): X/Y/Z fahren
- **Extruder:** Solltemperatur Bett/E0/E1, einzeln ausschalten, aktiver Extruder, Vorheizen PLA (180/60) und ABS (210/100), Abkühlen, Filament laden/entladen, Fluss, E-Ursprung
- **Lüfter:** Drehzahl, aus, 25/50/75/100 %
- **SD Karte:** Datei drucken, pausieren, fortsetzen, abbrechen
- **Konfiguration:** Z Kalibrierung (Matrix Scan, mit PLA- oder ABS-Betttemperatur, Z-Offset-Scan, Z Abstand), DMS Features (SenseOffset: Level, Max, AutoStart; Notfall Pause: Min, Max; Digit Flow CMP: Min, Max, dFlow, dFeed), Temperatures (PID-Autotune), Beschleunigung, Feedrate, Werkseinstellungen

Änderungen unter DMS Features, Beschleunigung und Feedrate werden wie im EEPROM der RF-Firmware in `rf_variables.cfg` gespeichert und beim Start übernommen. **Werkseinstellungen** setzt sie auf die Werte aus der `printer.cfg` zurück. AutoStart schaltet den Aufruf von `Z_SENSE_OFFSET` in `PRINT_START` ab, wenn das Makro die Variable `rf_sense_autostart` abfragt.

## Unterschiede zur RF-Firmware

- **Filament laden/entladen:** Es gibt nur die Varianten mit fester Länge (laden 90 mm bei 210 °C, entladen 90 mm bei 180 °C). Die kraftgesteuerten Varianten „Sanftes Limit“ und „Max. 210°C/Soft“ fehlen.
- **Matrix Scan:** Ruft `BED_CALIBRATE` auf (Z messen, Bettnetz, `SAVE_CONFIG` mit Neustart).
- **Seite 5:** Zeigt den aktuellen Druck, keine Gesamtzeiten. Klipper speichert keine Betriebsstunden.
- **Nicht vorhanden:** Allgemein (Baudrate, Piepser), Stepper-Ströme, Wobble-Fix, Fräsmodus.

## Technische Änderungen

- `display/hd44780.py`: Option `hd44780_charset` (`none` Standard, `western`, `a00`, `ascii`). `encode_text()` bildet Umlaute auf die Codes im Zeichen-ROM ab wie `uilang.h`: western ä 0x84, ö 0x94, ü 0x81, Ä 0x8E, Ü 0x9A; a00 ä 0xE1, ö 0xEF, ü 0xF5, ß 0xE2. Nicht vorhandene Zeichen werden ersetzt (Oe, ss, u, o).
- `display/display.py`: Verwendet `encode_text()`, wenn der Display-Treiber sie hat.
- `display/menu.py`: Option `menu_show_back` (Eintrag „..“ ein/aus) und `menu_pages`. Außerhalb des Menüs wechseln hoch und runter die `display_data`-Gruppe, zurück springt auf die erste Seite.
- `z_sense_offset.py`: `SET_Z_SENSE_OFFSET FORCE_THRESHOLD= MAX_Z_OFFSET=` setzt die Werte, ohne die Funktion einzuschalten.

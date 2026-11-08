# Änderungen für RF1000 / RF2000

## 2026-11-08 (3): Display für den RF1000

- **`config/rf_display_rf1000.cfg`:** Startseiten und Menü wie in der RF-Firmware für das 16x4-Display des RF1000 (Repetier `UI_COLS 16`, Kurztexte aus `uilang.h`, Zeichensatz `a00`).
- **`config/rf_display.cfg`:** Kraftanzeige auf Seite 2 auch bei fünfstelligen Minuswerten in 20 Spalten.

## 2026-11-07 (5): Startbild 3D-Artmaker

- **`rf_display.cfg`:** Startbild `rf_splash` mit 3D-Würfel aus eigenen Zeichen, Name, Version, Fortschrittsbalken und Stand, danach Seite 1. Version und Stand im Makro `_RF_INFO`.

## 2026-11-07 (4): RF2000-Display mit 20 Spalten und westlichem Zeichensatz

- **`rf_display.cfg`:** Seiten und Menütexte für 20x4 nach den Repetier-Vorlagen für das RF2000 (`UI_COLS 20`). Gradzeichen als eigenes Zeichen, Mikrometer als „um“.
- **Display:** Neue Option `hd44780_charset` (`western` für RF2000, `a00` für RF1000). Vorher wurden die Umlaut-Codes des RF1000 verwendet, auf dem RF2000 kamen falsche Zeichen.
- **Menü:** Neue Option `menu_show_back: False` entfernt den Eintrag „..“ (das RF2000 hat eine Zurück-Taste).

## 2026-11-07 (3): Display und Menü wie in der RF-Firmware

- **`config/rf_display.cfg`:** Startseiten und Menü wie in der RF-Repetier-Firmware (deutsche Texte aus `uilang.h`), Einstellungen werden wie im EEPROM in `rf_variables.cfg` gespeichert. Siehe [DISPLAY_MENU.md](DISPLAY_MENU.md).
- **Display:** Umlaute, °, µ und ß über das Zeichen-ROM des HD44780. Neue Option `menu_pages`: hoch/runter blättern außerhalb des Menüs durch die Seiten.
- **Sense Offset:** `SET_Z_SENSE_OFFSET` setzt Schwelle und Obergrenze, ohne einzuschalten.

## 2026-11-07 (2): Sense Offset im Terminal, Display-Anzeige korrigiert

- **Sense Offset:** Meldungen im Terminal, wenn der Offset um `report_step` (Standard 0,02 mm) steigt und wenn `max_z_offset` erreicht ist. Nach dem ersten Layer folgt das Ergebnis mit höchster und mittlerer Kraft und der Zahl der Überschreitungen. `Z_SENSE_OFFSET QUERY=1` zeigt den Stand.
- **Display:** Die Statuszeile zählte beim Kürzen Leerzeichen aus der Vorlage mit (z. B. „RF2000 vS0.171“). Jetzt steht dort „RF2000 v2 S0.171“.

## 2026-11-07: Sense Offset korrigiert, Anzeige in Mainsail und Display, Menütasten

- **Sense Offset:** Homing setzt den Offset jetzt auf 0. Vorher blieb er nach dem Druck stehen und verfälschte beim nächsten Druck die Heißmessung um bis zu `max_z_offset`.
- **Sense Offset:** `max_z_height` wird an der Z-Höhe aus dem G-Code geprüft (ohne Bed Mesh und Z-Offset). Vorher zählte die Z-Höhe samt Mesh; bei einem Mesh um −0,5 mm war die Regelung bis etwa zum 4. Layer aktiv.
- **Sense Offset:** Der letzte Kraftwert für die Trend-Erkennung wird auch über der Schwelle aktualisiert. `Z_SENSE_OFFSET ENABLE=0` schaltet aus (Offset bleibt), An und Aus werden in der Konsole gemeldet.
- **Mainsail:** Unter „Sonstige“ stehen `Load Cell` (Kraft in Digits) und `Sense Offset` (in µm). Mainsail schreibt dort fest „g“ dahinter. Die Kurve „Digits“ im Temperatur-Diagramm ist im Config Creator nur noch optional.
- **Display:** Zeile 4 zeigt rechts `S0.000` (Sense Offset in mm), solange er an ist oder einen Wert hat. `menu_reverse_input: True`: Taste hoch erhöht beim Ändern von Werten, Taste runter verringert.
- **Makros:** Die Zwischenschritte der Heißmessung heißen jetzt `_HOT_Z_PROBE_STEP2` bis `_HOT_Z_PROBE_STEP5` und erscheinen nicht mehr als Knöpfe in Mainsail.

## 2026-11-06: Config Creator erweitert, Sense Offset korrigiert

- **Sense Offset:** `PRINT_START` ruft jetzt `Z_SENSE_OFFSET` auf. Vorher blieb das Modul ausgeschaltet, weil Homing es abschaltet und kein Befehl es wieder einschaltet. `max_z_height` steht jetzt in der `printer.cfg`; die Anleitung beschreibt die Regelung genau.
- **Config Creator:** getrennte Auswahl für Notfall-Pause und Flow-Kompensation, Info-Popups, DMS statt Last-Zelle, Modellbilder, bed_mesh je Modell (RF2000 v2 bicubic 6,9), Düse 0,2 bis 0,8 mm, Dual mit Düsenversatz, Filament-Schritt (PLA/PETG/manuell), Testdruck `OFFSET_TEST` und `NOZZLE_OFFSET_ADJUST` in `offset_test.cfg`, Orca-Slicer-Einstellungen mit Start- und End-G-Code.
- **Y-Achse:** Y=0 ist die Vorderkante des Betts, der Home-Schalter liegt davor (RF2000 v2: 10 mm, RF1000/RF2000: 20 mm). RF2000 v2: Bett 300 mm, vorne 15 mm frei für die Prime Line (285 mm bedruckbar), RF1000/RF2000: Y max 245 mm. Neue Felder "Y-Home vor dem Bett" und "Y frei vorne"; die Orca-Anleitung nennt den Sperrbereich.
- **Heißmessung (optional):** `HOT_Z_PROBE` misst nach dem Aufheizen an einem Zufallspunkt (Vorgabe X/Y 30 bis 50 mm) zweimal mit `PROBE` (die zweite Messung 2 mm weiter in X zählt) und setzt den Z-Offset für den Druck. Standardmäßig aus.

## 2026-11-05: Notfall-Pause, Flow-Kompensation und Digits-Kurve

Zwei Funktionen der alten RF-Firmware (Repetier) gibt es jetzt auch in Klipper, dazu eine Live-Kurve
der Last-Zelle. Alles ist standardmäßig **aus** und ändert bestehende Systeme nicht, bis der Abschnitt
in der `printer.cfg` eingetragen wird.

### Neu
- **Notfall-Pause** (`FEATURE_EMERGENCY_PAUSE`, `M3075`): Pausiert den Druck, wenn die Kraft an der Düse
  (Mittelwert über mehrere Messwerte) die eingestellten Grenzen verlässt. Aktiv nur beim Drucken und
  bei referenzierten Achsen. Danach läuft dein `PAUSE`-Makro (parken). Befehl: `RF_EMERGENCY_PAUSE`.
- **Flow-Kompensation** (`FEATURE_DIGIT_FLOW_COMPENSATION`, `M3911`): Skaliert Extrusion (`M221`) und
  Vorschub (`M220`) kraftabhängig zwischen `flow_min` und `flow_max`. Ein `M220`/`M221` des Slicers
  bleibt erhalten, die Korrektur wird daraufmultipliziert. Befehl: `RF_FLOW_COMP`.
- **Kurve "Digits"** in Mainsail: Neuer Sensortyp `rf1000_force` für `[temperature_sensor Digits]`.
  Mainsail zeigt die Einheit dort fest als "°C", gemeint ist die Kraft.
- **Config Creator** (`RenkforceConfigCreator/index.html`): Seite im Browser, die `printer.cfg` und `macros.cfg` erzeugt, jetzt mit
  Abschnitt für Notfall-Pause, Flow-Kompensation und Digits-Kurve sowie einer Anleitung zum Einstellen. Siehe
  [RenkforceConfigCreator/README.md](RenkforceConfigCreator/README.md).
- Beispiel-Konfigurationen `config/printer-rf1000.cfg` und `config/printer-rf2000v2-single.cfg`
  enthalten die neuen Abschnitte als auskommentierten Block.

Dateien: `klippy/extras/rf1000_pressure_guard.py`, Anleitung in [PRESSURE_GUARD.md](PRESSURE_GUARD.md).

### Schon vorhanden (unverändert)
Sense Offset (`[z_sense_offset]`) entspricht `FEATURE_SENSIBLE_PRESSURE` (`M3909`) der Firmware.

### Aktualisieren
1. Im Mainsail unter **Maschine** "Nach Updates suchen" und Klipper aktualisieren. Der Update-Manager
   meldet neue Commits des Forks, es gibt keine neue Versionsnummer, nur der Zähler (`v0.13.0-…`) steigt.
2. **Dienst neu starten:** `sudo systemctl restart klipper`. Ein `RESTART` im Mainsail lädt bereits
   geladene Python-Module nicht neu.
3. Abschnitt `[rf1000_pressure_guard]` (und optional `[temperature_sensor Digits]`) in die `printer.cfg`
   einfügen, in dieser Reihenfolge. Grenzwerte mit `LCP_READ` neu messen.

### Wichtig
- Die Werte gelten in der Einheit von `last_force` (siehe `LCP_READ`), **nicht** in den rohen Digits der
  alten Firmware. Bitte neu messen.
- Die Korrektur über `M220`/`M221` wirkt auf neu geplante Bewegungen, also um die Klipper-Pufferzeit
  verzögert (geschätzt 1 bis 2 Sekunden), nicht in Millisekunden wie im Interrupt der Firmware.
  Die Notfall-Pause ist ein Schutz bei Verstopfung oder Verklemmen, kein Ersatz für den Not-Halt.

### Geprüft
Mock-Tests (Pause-Auslösung, Absicherungen, Flow-Skalierung, Sensortyp) laufen mit dem Klipper-Python
auf dem Raspberry Pi. Auf einem Drucker mit echtem Klipper geladen (Raspberry Pi), Sensorwerte und Befehle laufen
fehlerfrei. **Noch nicht unter echter Last im Druck getestet.**

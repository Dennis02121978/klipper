# Änderungen für RF1000 / RF2000

## 2026-11-06: Config Creator erweitert, Sense Offset korrigiert

- **Sense Offset:** `PRINT_START` ruft jetzt `Z_SENSE_OFFSET` auf. Vorher blieb das Modul ausgeschaltet, weil Homing es abschaltet und kein Befehl es wieder einschaltet. `max_z_height` steht jetzt in der `printer.cfg`; die Anleitung beschreibt die Regelung genau.
- **Config Creator:** getrennte Auswahl für Notfall-Pause und Flow-Kompensation, Info-Popups, DMS statt Last-Zelle, Modellbilder, bed_mesh je Modell (RF2000 v2 bicubic 6,9), Düse 0,2 bis 0,8 mm, Dual mit Düsenversatz, Filament-Schritt (PLA/PETG/manuell), Testdruck `OFFSET_TEST` und `NOZZLE_OFFSET_ADJUST` in `offset_test.cfg`, Orca-Slicer-Einstellungen mit Start- und End-G-Code.

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

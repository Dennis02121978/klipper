# Renkforce Klipper Config Creator

Eine einzelne HTML-Seite, die `printer.cfg` und `macros.cfg` für RF1000, RF2000 und RF2000 v2
(Single oder Dual Extruder) erzeugt. Sie läuft komplett im Browser, es werden keine Daten gesendet.

## Benutzen
1. [index.html](index.html) herunterladen (auf GitHub oben rechts "Download raw file") und im Browser öffnen.
2. Extruder, Modell, Maße, Filament, Düse, Z-Endstop und optional die Last-Zelle (Abschnitt 7) einstellen.
3. Mit "Beide laden" `printer.cfg` und `macros.cfg` speichern und auf den Pi in `~/printer_data/config/` legen.
4. Die Datei `z_tasten.cfg` wird eingebunden und gehört nicht zum Generator (siehe [Z_TASTEN.md](../Z_TASTEN.md)).

Abschnitt 7 (Notfall-Pause, Flow-Kompensation, Digits-Kurve) braucht das Modul
`klippy/extras/rf1000_pressure_guard.py` aus diesem Repo. Unten auf der Seite steht eine Anleitung
zum Einstellen und Bedienen. Mehr dazu in [PRESSURE_GUARD.md](../PRESSURE_GUARD.md).

## Hinweise
- Die erzeugten Dateien werden ohne Gewähr bereitgestellt. Alle Werte (Pins, Maße, Endstops,
  Temperaturen) vor dem ersten Start kontrollieren.
- Das Feld "MCU serial" ist mit einem Beispielwert vorbelegt. Eigenen Wert aus
  `ls /dev/serial/by-id/` eintragen.

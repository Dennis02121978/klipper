# Z-Achse mit den Tasten am RF2000 fahren

Mit dem Modul `z_jog` fährst du die Z-Achse mit den Tasten **Z-UP** und **Z-DN** am Drucker.

| Bedienung | Was passiert |
|---|---|
| Kurz drücken | Z fährt 0,03 mm |
| 2 Sekunden halten | Z fährt konstant mit 8 mm/s, bis du loslässt |
| Drücken beim Drucken | Der Z-Offset ändert sich um 0,005 mm (Babystep), Halten fährt nicht |

**Z-DN** erhöht Z und **Z-UP** verringert Z.

Am RF2000 getestet: kurze Schritte, Babystep sowie Fahren und Stoppen beim Halten.

> [!NOTE]
> Nahe am Bett nimmst du besser kurze Schritte.

## Sicherungen

- Ohne Z-Referenzfahrt bewegen die Tasten nichts.
- Beim Halten stoppt die Fahrt bei `hold_min_z` und um `max_margin` vor dem oberen Ende.
- Kurze Schritte kommen bis zur Grenze `position_min` deiner `printer.cfg`, also unter Z=0, wenn dieser Wert negativ ist.

## Einrichten

Voraussetzung ist Klipper aus diesem Repo, siehe [Klipper auf dieses Repo umstellen](KLIPPER_WECHSELN.md).

**1. Alte Belegung entfernen.** Lösche aus deiner Config alle Abschnitte, die die Pins `PJ2` oder `PJ4` nutzen, zum Beispiel `[gcode_button Z_UP]` und `[gcode_button Z_DOWN]`. Sonst meldet Klipper, dass der Pin doppelt belegt ist.

**2. Datei kopieren.** Verbinde dich per SSH mit dem Drucker und gib ein:

```bash
cp ~/klipper/config/sample-rf2000-z-tasten.cfg ~/printer_data/config/z_tasten.cfg
```

**3. Datei einbinden.** Öffne in Mainsail unter **Maschine → Konfigurationsdateien** die `printer.cfg` und ergänze bei den anderen `[include …]`-Zeilen:

```ini
[include z_tasten.cfg]
```

Klicke danach auf **Speichern & Neustart**.

**4. Vorsichtig testen.**

1. Fahre mit `G28` und `G1 Z50 F600` auf eine sichere Höhe.
2. Drücke jede Taste kurz. Z muss sich in Mainsail um 0,03 mm ändern.
3. Halte eine Taste gedrückt. Nach 2 Sekunden muss die Achse fahren und beim Loslassen stoppen.
4. Vergleiche die Z-Anzeige grob mit der gefahrenen Strecke.

## Einstellungen

Die Werte stehen in deiner `z_tasten.cfg`:

| Abschnitt | Wert | Bedeutung |
|---|---|---|
| `[z_jog]` | `hold_delay` | Wartezeit bis zur konstanten Fahrt in Sekunden |
| `[z_jog]` | `hold_speed` | Geschwindigkeit beim Halten in mm/s |
| `[z_jog]` | `hold_min_z` | Untere Grenze beim Halten |
| `[z_jog]` | `max_margin` | Abstand zum oberen Ende beim Halten in mm |
| `[gcode_macro _Z_JOG]` | `variable_step` | Weg bei kurzem Druck in mm |
| `[gcode_macro _Z_JOG]` | `variable_babystep` | Änderung des Z-Offsets beim Drucken in mm |

Die Pins in dieser Datei passen zum RF2000. Bei anderen Druckern musst du `increase_pin` und `decrease_pin` anpassen.

## Während der Fahrt

Beim Halten nimmt Klipper keine anderen G-Code-Befehle an. Sie laufen erst nach dem Loslassen weiter.

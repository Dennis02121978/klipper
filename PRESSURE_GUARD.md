# Notfall-Pause und Flow-Kompensation (rf1000_pressure_guard)

Port von `FEATURE_EMERGENCY_PAUSE` und `FEATURE_DIGIT_FLOW_COMPENSATION` der RF-Firmware.
Das Modul `klippy/extras/rf1000_pressure_guard.py` nutzt den Kraftwert von
`[rf1000_load_cell_probe]`. Standardmäßig ist alles aus.

```
[rf1000_pressure_guard]
#emergency_min: 0       # <= 0, Pause wenn Mittelwert darunter (0 und 0 = aus)
#emergency_max: 0       # >= 0, Pause wenn Mittelwert darüber
#emergency_samples: 5   # Mittelwert über so viele Messwerte
#pause_gcode: PAUSE     # wird nach der Pause-Anforderung ausgeführt
#flow_min: 0            # darunter: kein Eingriff
#flow_max: 0            # darüber: volle Korrektur
#flow_percent: 0        # Extrusion bei flow_max in % (-99..99)
#feed_percent: 0        # Vorschub bei flow_max in % (-90..99)
#flow_min_z: 0.5        # Korrektur erst über dieser Z-Höhe (mm)
```

Befehle (nur bis zum Neustart gültig): `RF_EMERGENCY_PAUSE [MIN=] [MAX=]` (wie `M3075`),
`RF_FLOW_COMP [MIN=] [MAX=] [FLOW=] [FEED=]` (wie `M3911`).

- Werte gelten in der Einheit von `last_force` (siehe `LCP_READ`), nicht in rohen Firmware-Digits.
- Die Korrektur läuft über `M220`/`M221` und wirkt auf neu geplante Bewegungen, also um die
  Klipper-Pufferzeit verzögert. Ein `M220`/`M221` des Slicers bleibt erhalten.
- Mit Mock-Tests geprüft; die Notfall-Pause und die Kompensation selbst sind noch nicht
  unter echter Last am Drucker getestet.

# Klipper auf dieses Repo umstellen

Diese Anleitung stellt dein vorhandenes Klipper auf diesen Stand um. Er verbindet das aktuelle offizielle Klipper mit den Modulen für den Renkforce RF1000 und RF2000, zum Beispiel für die DRV8711-Treiber und die Wägezelle.

In Mainsail selbst gibt es dafür keine Einstellung. Du änderst die Quelle einmal im Terminal. Danach zeigt Mainsail im Update Manager automatisch dieses Repo an, an der `moonraker.conf` musst du nichts ändern.

> [!WARNING]
> Der Stand ist noch nicht im Druckbetrieb erprobt. Bisher geprüft wurde auf einem Drucker mit ATmega2560: Klipper startet, und die Wägezelle liefert Werte. Fahrten, Z-Referenzfahrt und Druck sind noch nicht bestätigt. Bleib bei den ersten Tests am Drucker und halte den Not-Halt bereit.

## Bekanntes Problem

`BED_MESH_CALIBRATE` bricht mit dem Probe `rf1000_load_cell_probe` im Testlauf mit einem Fehler ab: `get_offsets() takes 1 positional argument`. Der Fehler steckt schon im älteren RF1000-Stand. Führe den Befehl vorerst nicht aus.

## Das brauchst du vorher

- [ ] Es läuft **kein Druck**.
- [ ] Du hast Klipper, Moonraker und Mainsail installiert, und Klipper liegt im Ordner `~/klipper`.
- [ ] Der Drucker ist mit dem **Internet** verbunden.
- [ ] Du hast in Mainsail unter **Maschine** deine Config-Dateien heruntergeladen.

## Schritt 1: Mit dem Drucker verbinden

Öffne ein Terminal: Unter Windows die **PowerShell**, auf dem Mac das Programm **Terminal**.

Gib diesen Befehl ein und ersetze Benutzer und IP-Adresse durch deine eigenen. Die IP-Adresse steht oben im Browser, wenn du Mainsail öffnest. Der Benutzer ist oft `pi` oder bei MKS-Boards `mks`.

```bash
ssh pi@192.168.1.50
```

Beim Tippen des Passworts siehst du nichts, das ist normal.

## Schritt 2: Prüfen und sichern

```bash
cd ~/klipper
git status --short
```

Erscheint **keine** Zeile, ist alles in Ordnung. Erscheinen Dateien, hast du eigene Änderungen im Klipper-Ordner. Kläre das zuerst, denn der Wechsel bricht sonst ab oder deine Änderungen stören später.

Lege jetzt die Sicherung an:

```bash
cp -a ~/klipper ~/klipper-backup
```

Gibt es `~/klipper-backup` schon, wähle einen anderen Namen und benutze ihn auch später beim Zurückwechseln.

## Schritt 3: Quelle umstellen

```bash
cd ~/klipper
git remote set-url origin https://github.com/Dennis02121978/klipper.git
git fetch origin --tags
git checkout -B master origin/master
```

Kontrolle:

```bash
git remote -v
git describe --tags --always
```

In der ersten Zeile muss `Dennis02121978/klipper` stehen, die Version beginnt mit `v0.13.0`.

## Schritt 4: Firmware aufs Board schreiben

Code auf dem Pi und Firmware auf dem Board müssen zusammenpassen. Bis zu diesem Schritt kann Klipper deshalb einen Fehler melden, das ist normal.

Installiere dafür den passenden Firmware Updater und starte das Update: [Anleitung für den Firmware Updater](FIRMWARE_UPDATER.md).

## Schritt 5: Config prüfen

Deine `printer.cfg` bleibt beim Wechsel unverändert. Für neue Einstellungen kannst du dir diese Beispiele ansehen:

| Datei | Für |
|---|---|
| [`config/printer-rf1000.cfg`](config/printer-rf1000.cfg) | RF1000 |
| [`config/printer-rf1000-mill.cfg`](config/printer-rf1000-mill.cfg) | RF1000 mit Fräse |
| [`config/printer-rf2000v2-single.cfg`](config/printer-rf2000v2-single.cfg) | RF2000 v2 mit einem Extruder |

## Schritt 6: Vorsichtig testen

1. Lade Mainsail mit **F5** neu und schau, ob Klipper bereit ist.
2. Öffne **Maschine → Update Manager** und klicke auf **auf Aktualisierungen prüfen**. Bei `klipper` steht jetzt eine Version ab `v0.13.0`.
3. Fahre mit `G28 X` und `G28 Y` X und Y an.
4. Fahre mit `G28 Z` die Z-Achse an, die Hand am Not-Halt.
5. Heize auf und mach einen kurzen Testdruck.

## Spätere Updates

Der Update Manager zeigt neue Stände dieses Repos bei `klipper` an. Neue Versionen des offiziellen Klipper kommen erst an, wenn sie hier eingepflegt wurden.

Nimm für Updates am besten den [Firmware Updater](FIRMWARE_UPDATER.md), denn er aktualisiert Code und Firmware zusammen. Der Knopf im Update Manager aktualisiert nur den Code. Hast du ihn benutzt, starte danach zusätzlich den Firmware Updater.

## Wenn etwas nicht klappt

| Meldung | Was du tun kannst |
|---|---|
| `Your local changes … would be overwritten` | Im Klipper-Ordner gibt es eigene Änderungen. Siehe Schritt 2. |
| `MCU Protocol error` oder eine Meldung, dass die Firmware nicht passt | Die Firmware wurde noch nicht geschrieben. Siehe Schritt 4. |
| `Unknown config object` | Deine `printer.cfg` nutzt einen Abschnitt, den es so nicht mehr gibt. Vergleiche sie mit den Beispielen aus Schritt 5. |
| `ModuleNotFoundError` im Klipper-Log | Es fehlt ein Python-Paket. Gib `~/klippy-env/bin/pip install -r ~/klipper/scripts/klippy-requirements.txt` ein und starte Klipper mit `sudo systemctl restart klipper` neu. |

## Zurück zum alten Stand

```bash
sudo systemctl stop klipper
rm -rf ~/klipper
mv ~/klipper-backup ~/klipper
sudo systemctl start klipper
```

Starte danach den Firmware Updater noch einmal. Er schreibt die Firmware passend zum alten Stand aufs Board.

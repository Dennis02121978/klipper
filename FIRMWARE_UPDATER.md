# Firmware Updater für Mainsail

Mit dem Firmware Updater bekommt Mainsail den Menüpunkt **Firmware-Update**. Damit holst du per Knopfdruck den neuesten Klipper-Stand und schreibst die passende Firmware aufs Board, ganz ohne Terminal. Nur für die Installation brauchst du einmalig ein paar Befehle.

## Welches Paket brauche ich?

Es gibt zwei Pakete, je nach Board. Pro Drucker installierst du **nur eines**.

| Dein Board | Paket | So wird geschrieben |
|---|---|---|
| **ATmega2560** mit 16 MHz und 250000 Baud, zum Beispiel beim RF1000 oder RF2000 | `rf-update` | Direkt über die serielle Verbindung |
| **MKS SKIPR** mit Micro-SD im MCU-Slot | `skipr-update` | Über die SD-Karte, der Drucker startet dabei neu |

Welchen Prozessor dein Board hat, siehst du in Mainsail unter **Maschine** bei den System-Informationen. Die Update-Seite sperrt das Update, wenn Prozessor oder Einstellungen nicht passen.

## Das brauchst du vorher

- [ ] Es läuft **kein Druck**.
- [ ] Du nutzt Klipper und Mainsail mit nginx.
- [ ] Der Drucker ist mit dem **Internet** verbunden.
- [ ] Im Ordner `~/klipper` gibt es keine eigenen Änderungen.

## Schritt 1: Mit dem Drucker verbinden

Öffne ein Terminal: Unter Windows die **PowerShell**, auf dem Mac das Programm **Terminal**.

Gib diesen Befehl ein und ersetze Benutzer und IP-Adresse durch deine eigenen. Die IP-Adresse steht oben im Browser, wenn du Mainsail öffnest. Der Benutzer ist oft `pi` oder bei MKS-Boards `mks`.

```bash
ssh pi@192.168.1.50
```

Beim Tippen des Passworts siehst du nichts, das ist normal.

## Schritt 2: Paket installieren

Führe nur den Abschnitt für dein Board aus.

### ATmega2560 (`rf-update`)

```bash
cd ~
wget https://github.com/Dennis02121978/3D-Artmaker/releases/download/v1.3.0/rf-update_1.3.0_all.deb
echo "f11f067108f872a8bc62e656afb3a80b8bf6dc39e4c388ff26fc799817ecb52c  rf-update_1.3.0_all.deb" | sha256sum -c
```

Am Ende muss `OK` stehen. Steht dort etwas anderes, installiere nicht weiter.

```bash
sudo apt update
sudo apt install ./rf-update_1.3.0_all.deb
```

### MKS SKIPR (`skipr-update`)

```bash
cd ~
wget https://github.com/Dennis02121978/3D-Artmaker/releases/download/v1.3.0/skipr-update_1.3.0_all.deb
echo "9b5c22a8765beb7dcd5bbf251f30cf93e2c544883e8f06aa32286eb62e6b50ef  skipr-update_1.3.0_all.deb" | sha256sum -c
```

Am Ende muss `OK` stehen. Steht dort etwas anderes, installiere nicht weiter.

```bash
sudo apt update
sudo apt install ./skipr-update_1.3.0_all.deb
```

**Bei beiden Paketen gilt:** Kommt eine Frage mit `J/n` oder `Y/n`, drücke `J` oder `Y` und dann Enter. Am Ende steht `Firmware-Update ist installiert`. Mainsail verliert dabei kurz die Verbindung, das ist normal.

## Schritt 3: Firmware aktualisieren

1. Lade Mainsail mit **F5** neu.
2. Klicke links auf **Firmware-Update**.
3. Klicke auf **Update starten** und dann auf **Ja, jetzt starten**.
4. Warte, bis **Update erfolgreich** erscheint.

Die Seite zeigt dir, ob es etwas Neues gibt. Auch ohne Update kannst du die Firmware neu aufspielen, zum Beispiel nach einem Wechsel des Klipper-Stands.

> [!CAUTION]
> **Schalte den Drucker während des Updates nicht aus!** Das Browserfenster darfst du schließen, das Update läuft trotzdem weiter.

## So läuft das Update ab

1. Es prüft den Drucker, das Board und ob gerade ein Druck läuft.
2. Es holt den neuesten Stand des Repos, aus dem dein `~/klipper` stammt.
3. Es baut die Firmware. Scheitert das, wurde nichts aufs Board geschrieben.
4. Es hält Klipper an und schreibt die Firmware aufs Board.
5. **ATmega2560:** Es startet Klipper und prüft, ob es bereit ist. Der Pi startet nicht neu.
6. **MKS SKIPR:** Der Drucker startet am Ende neu.

## Updates für den Firmware Updater selbst

In Mainsail steht unter **Maschine → Update Manager** ein eigener Eintrag: **3D-Artmaker Firmware Updater ATmega** oder **3D-Artmaker Firmware Updater**. Ein Klick auf **update** erneuert dort nur die Webseite.

Das eigentliche Update-Programm läuft mit Administratorrechten und wird deshalb nicht per Klick ersetzt. Gibt es ein neues Paket, zeigt die Seite einen Hinweis mit einem Link zum Download. Wiederhole dann Schritt 2 mit dem neuen Dateinamen und der Prüfsumme aus der Datei `SHA256SUMS`.

## Wenn etwas nicht klappt

| Meldung | Was du tun kannst |
|---|---|
| `Gerade läuft ein Druck` | Warte, bis der Druck fertig ist. |
| `Dieses Update ist nur für …` oder `Die Firmware passt nicht zu deinem Board` | Das Paket passt nicht zu deinem Board. Bitte nicht weiter versuchen. |
| `Im Klipper-Ordner gibt es eigene Änderungen` | Im Ordner `~/klipper` wurden Dateien geändert. Kläre das zuerst. Das meldet nur `rf-update`. |
| `Das Board wurde nicht gefunden` | Prüfe Kabel und Stromversorgung. Bei `rf-update` kommt der Anschluss aus der Zeile `serial:` unter `[mcu]` in deiner `printer.cfg`. |
| Die Firmware konnte nicht erstellt werden | Es wurde nichts aufs Board geschrieben. Starte das Update noch einmal. |
| Die Firmware konnte nicht geschrieben werden | Schalte den Drucker aus und wieder ein und starte das Update noch einmal. |
| Klipper wurde nicht bereit | Die Firmware ist geschrieben. Lies die Meldung in Mainsail, oft passt etwas in der `printer.cfg` nicht. |

Hilft das nicht, öffne auf der Update-Seite **Technische Details anzeigen** und öffne ein [Issue im Repo 3D-Artmaker](https://github.com/Dennis02121978/3D-Artmaker/issues) mit dem Text daraus. Poste dabei niemals dein Passwort.

## Wieder entfernen

```bash
sudo apt purge rf-update
```

Bei einem MKS SKIPR heißt das Paket `skipr-update`. Der Menüpunkt und der Eintrag im Update Manager verschwinden damit, und deine Klipper-Config bleibt unverändert.

## Sicherheit

Die Update-Seite hat kein eigenes Passwort. Jeder in deinem Netzwerk kann sie öffnen, genau wie Mainsail meist auch. Gib deinen Drucker deshalb **nicht** im Router für das Internet frei.

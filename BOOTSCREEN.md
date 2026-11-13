# BootScreen für den Raspberry Pi

Der BootScreen zeigt beim Einschalten das 3D-Artmaker-Logo auf dem Display, bis KlipperScreen erscheint. Das Logo wird dabei kurz animiert: Die Linie läuft einmal durch die 3D, danach wird der Schwung unter „Artmaker“ gezeichnet, und das Logo bleibt stehen. Der Konsolentext ist dann nicht mehr zu sehen. Für die Installation brauchst du einmalig ein paar Befehle.

## Passt das zu meinem Drucker?

- [ ] Du hast einen **Raspberry Pi** mit Klipper und **KlipperScreen**.
- [ ] Du hast ein **480x320-SPI-Display im Querformat**, zum Beispiel ein 3,5-Zoll-RPi-LCD, und es **funktioniert schon**. Das Paket richtet das Display nicht ein.
- [ ] Der Drucker ist mit dem **Internet** verbunden.
- [ ] Es läuft **kein Druck**.

Passt etwas davon nicht, bricht die Installation mit einer Meldung ab und ändert nichts.

Getestet ist das Paket auf einem Raspberry Pi 3 mit Debian 13 und dem Overlay `piscreen`.

## Schritt 1: Mit dem Drucker verbinden

Öffne ein Terminal: Unter Windows die **PowerShell**, auf dem Mac das Programm **Terminal**.

Gib diesen Befehl ein und ersetze Benutzer und IP-Adresse durch deine eigenen. Die IP-Adresse steht oben im Browser, wenn du Mainsail öffnest. Der Benutzer ist oft `pi`.

```bash
ssh pi@192.168.1.50
```

Beim Tippen des Passworts siehst du nichts, das ist normal.

## Schritt 2: Paket installieren

```bash
cd ~
wget https://github.com/Dennis02121978/3D-Artmaker/releases/download/v1.7.0/rf-bootlogo_1.7.0_all.deb
echo "e33f0345c20f3923f71cf5b0b9f1a89ac4caee8eac2e4fdb12382b902f2a1890  rf-bootlogo_1.7.0_all.deb" | sha256sum -c
```

Am Ende muss `OK` stehen. Steht dort etwas anderes, installiere nicht weiter.

```bash
sudo apt update
sudo apt install ./rf-bootlogo_1.7.0_all.deb
```

Kommt eine Frage mit `J/n` oder `Y/n`, drücke `J` oder `Y` und dann Enter. Dein Drucker lädt dabei ImageMagick nach, das dauert einen Moment. Am Ende steht `Logo ist installiert`. Mainsail verliert dabei kurz die Verbindung, das ist normal.

## Schritt 3: Neu starten

```bash
sudo reboot
```

## So sieht der Start danach aus

Die Zeiten sind auf einem Raspberry Pi 3 gemessen:

| Zeit nach dem Einschalten | Auf dem Display |
|---|---|
| bis etwa 13 Sekunden | Weiß, weil der Treiber noch nicht geladen ist |
| ab etwa 13 Sekunden | Das Logo, etwa zwei Sekunden animiert (Linie läuft durch die 3D, dann wird der Schwung gezeichnet), danach bleibt es stehen |
| nach etwa 34 Sekunden | Für einen Moment schwarz, dann wieder das Logo |
| ab etwa 41 Sekunden | KlipperScreen |

Das weiße Bild am Anfang lässt sich mit diesem Paket nicht vermeiden, weil das Display bis dahin nicht angesteuert wird.

Hängt ein HDMI-Monitor am Pi, siehst du dort beim Start voraussichtlich auch keinen Text mehr.

## Updates

In Mainsail steht unter **Maschine → Update Manager** ein eigener Eintrag: **3D-Artmaker BootScreen Pi**. Ein Klick auf **update** erneuert dort nur das Logo, das neue Bild erscheint beim nächsten Start.

Alle 3D-Artmaker-Pakete haben dieselbe Versionsnummer. Mainsail bietet deshalb auch dann ein Update an, wenn sich das Logo gar nicht geändert hat. Das schadet nicht.

## Wenn etwas nicht klappt

| Meldung | Was du tun kannst |
|---|---|
| `Dieses Paket ist nur fuer den Raspberry Pi` | Dein System wird nicht unterstützt. Unter Armbian nimmst du das Paket `skipr-bootlogo` aus dem [Repo 3D-Artmaker](https://github.com/Dennis02121978/3D-Artmaker). |
| `Kein SPI-Display gefunden` | Das Display läuft noch nicht oder wird nicht unterstützt. Richte es zuerst ein. |
| `Das Logo passt nur auf ein 480x320-Display im Querformat` | Dein Display hat eine andere Auflösung oder steht im Hochformat. |
| `KlipperScreen wurde nicht gefunden` | Installiere zuerst KlipperScreen. |
| `KlipperScreen laeuft mit Wayland` | Das Paket funktioniert nur, wenn KlipperScreen mit X11 läuft. |

Hilft das nicht, öffne ein [Issue im Repo 3D-Artmaker](https://github.com/Dennis02121978/3D-Artmaker/issues) mit der genauen Meldung. Poste dabei niemals dein Passwort.

## Wieder entfernen

```bash
sudo apt remove rf-bootlogo
sudo reboot
```

Die Einstellungen für den Start werden dabei zurückgenommen, und der Eintrag im Update Manager verschwindet. Deine Klipper-Config bleibt unverändert. ImageMagick bleibt installiert. Mit `sudo apt autoremove` kannst du es ebenfalls entfernen, falls nichts anderes es braucht.

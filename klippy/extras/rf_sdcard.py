# SD-Karte im Kartenleser des Druckerboards lesen (RF1000/RF2000/RF2000 v2)
#
# Die Karte haengt am Hardware-SPI des ATmega2560 (CS PB0, Erkennung PD2).
# Klipper liest sie ueber die vorhandenen SPI-Befehle der MCU-Firmware, es
# ist keine neue Firmware noetig. Gelesen wird nur, nie geschrieben.
#
# Drucken: Die Datei wird zuerst in den G-Code-Ordner des Raspberry Pi
# kopiert (Unterordner "SD-Karte") und dann wie jede andere Datei gedruckt.
# Direkt von der Karte zu drucken wuerde die serielle Verbindung zur MCU
# waehrend des Drucks zu stark belasten.
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, os, struct, threading, binascii, time
from . import bus

SECTOR = 512
CHUNK = 48                  # Bytes je spi_transfer (Nachricht max. 64 Bytes)
BURST = 24                  # spi_transfer-Befehle je Durchgang (ohne Warten)
GCODE_EXT = ('.gcode', '.gco', '.g', '.nc')
MAX_FILES = 200
MAX_DEPTH = 3

CMD_GO_IDLE = 0
CMD_SEND_IF_COND = 8
CMD_STOP = 12
CMD_SET_BLOCKLEN = 16
CMD_READ_SINGLE = 17
CMD_READ_MULTI = 18
CMD_APP = 55
CMD_READ_OCR = 58
ACMD_SEND_OP_COND = 41


class SDError(Exception):
    pass


def crc7(data):
    poly = 0b10001001 << 1
    crc = 0
    for b in data:
        crc ^= b & 0xFF
        for i in range(8):
            crc = ((crc << 1) ^ poly if crc & 0x80 else crc << 1) & 0xFF
    return crc | 1


######################################################################
# SPI ueber die MCU, mehrere Transfers ohne auf jede Antwort zu warten
######################################################################

class MCUSPIPipe:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        ppins = self.printer.lookup_object('pins')
        cs = ppins.lookup_pin(config.get('cs_pin'))
        self.mcu = cs['chip']
        self.oid = self.mcu.create_oid()
        self.bus_name = config.get('spi_bus', None)
        self.speed = config.getint('spi_speed', 4000000, minval=100000)
        self.mcu.add_config_cmd("config_spi oid=%d pin=%s cs_active_high=0"
                                % (self.oid, cs['pin']))
        self.cmd_queue = self.mcu.alloc_command_queue()
        self.mcu.register_config_callback(self._build_config)
        self.lock = threading.Lock()
        self.responses = []
        self.expect = 0
        self.completion = None
        self.xfer_cmd = self.send_cmd = None
        self.pace = 0.
        self.pace_factor = config.getfloat('pace_factor', 1.3, minval=0.)
        self.burst = config.getint('burst', BURST, minval=1, maxval=64)
    def _build_config(self):
        busname = bus.resolve_bus_name(self.mcu, "spi_bus", self.bus_name)
        self.mcu.add_config_cmd("spi_set_bus oid=%d spi_bus=%s mode=0 rate=%d"
                                % (self.oid, busname, self.speed))
        self.xfer_cmd = self.mcu.lookup_command(
            "spi_transfer oid=%c data=%*s", cq=self.cmd_queue)
        self.send_cmd = self.mcu.lookup_command(
            "spi_send oid=%c data=%*s", cq=self.cmd_queue)
        self.mcu.register_serial_response(
            self._handle_response,
            "spi_transfer_response oid=%c response=%*s", self.oid)
    def _get_pace(self):
        # Der Sendepuffer der MCU (serial_irq: 96 Bytes) fasst nur eine
        # Antwort. Kommen die Befehle schneller, als die Antworten ueber
        # die serielle Leitung passen, verwirft die MCU Antworten. Deshalb
        # jeden Transfer erst schicken, wenn die vorige Antwort raus ist.
        if not self.pace:
            baud = self.mcu.get_constants().get('SERIAL_BAUD')
            try:
                baud = float(baud)
            except (TypeError, ValueError):
                baud = 0.
            # Antwort: Daten + ca. 10 Bytes Rahmen, 10 Bit je Byte, Reserve
            # fuer andere Meldungen der MCU (Temperaturen, Waegezelle)
            self.pace = ((CHUNK + 10) * 10. / baud * self.pace_factor
                         if baud else 1e-6)
        return self.pace
    def _handle_response(self, params):
        # Laeuft im Hintergrund-Thread der seriellen Verbindung
        with self.lock:
            self.responses.append(bytes(params['response']))
            if len(self.responses) >= self.expect and self.completion:
                c, self.completion = self.completion, None
                self.reactor.async_complete(c, True)
    def send(self, data):
        self.send_cmd.send([self.oid, list(data)])
    def transfer(self, chunks, timeout=1.):
        # chunks: Liste von Byte-Listen; Antwort: alle Bytes hintereinander
        completion = self.reactor.completion()
        with self.lock:
            self.responses = []
            self.expect = len(chunks)
            self.completion = completion
        pace = self._get_pace()
        now = self.reactor.monotonic()
        start = self.mcu.estimated_print_time(now) + .002
        for i, c in enumerate(chunks):
            minclock = self.mcu.print_time_to_clock(start + i * pace)
            self.xfer_cmd.send([self.oid, list(c)], minclock=minclock)
        res = completion.wait(now + timeout + len(chunks) * pace)
        with self.lock:
            data = b''.join(self.responses)
            got = len(self.responses)
            self.responses = []
            self.expect = 0
            self.completion = None
        if res is None:
            # Spaete Antworten abwarten und verwerfen, damit der naechste
            # Transfer sauber beginnt
            self.reactor.pause(self.reactor.monotonic() + .2)
            with self.lock:
                self.responses = []
            raise SDError("SD-Karte antwortet nicht (%d/%d)"
                          % (got, len(chunks)))
        return data
    def clock_bytes(self, count):
        chunks = []
        while count > 0:
            n = min(CHUNK, count)
            chunks.append([0xFF] * n)
            count -= n
        return self.transfer(chunks)


######################################################################
# SD-Karte im SPI-Modus (nur lesen)
######################################################################

class SDCard:
    def __init__(self, spi):
        self.spi = spi
        self.ready = False
        self.high_capacity = False
    def _command(self, cmd, arg):
        req = [0x40 | cmd, (arg >> 24) & 0xFF, (arg >> 16) & 0xFF,
               (arg >> 8) & 0xFF, arg & 0xFF]
        req.append(crc7(req))
        # Ein 0xFF davor gibt der Karte Takte, um den letzten Befehl
        # abzuschliessen
        self.spi.send([0xFF] + req)
    def _command_resp(self, cmd, arg, count=8):
        self._command(cmd, arg)
        resp = self.spi.clock_bytes(count).lstrip(b'\xff')
        return resp
    def _app_command_resp(self, cmd, arg):
        self._command_resp(CMD_APP, 0)
        return self._command_resp(cmd, arg)
    def init(self, reactor):
        self.ready = False
        self.spi.clock_bytes(10)
        for i in range(10):
            r = self._command_resp(CMD_GO_IDLE, 0)
            if r and r[0] == 0x01:
                break
            reactor.pause(reactor.monotonic() + .05)
        else:
            raise SDError("Keine SD-Karte gefunden")
        r = self._command_resp(CMD_SEND_IF_COND, 0x1AA)
        version = 2 if (r and r[0] == 0x01 and len(r) >= 5
                        and r[4] == 0xAA) else 1
        arg = (1 << 30) if version == 2 else 0
        for i in range(100):
            r = self._app_command_resp(ACMD_SEND_OP_COND, arg)
            if r and r[0] == 0x00:
                break
            reactor.pause(reactor.monotonic() + .02)
        else:
            raise SDError("SD-Karte startet nicht (ACMD41)")
        self.high_capacity = False
        if version == 2:
            r = self._command_resp(CMD_READ_OCR, 0)
            if r and r[0] == 0x00 and len(r) >= 2:
                self.high_capacity = bool(r[1] & 0x40)
        r = self._command_resp(CMD_SET_BLOCKLEN, SECTOR)
        if not r or r[0] != 0x00:
            raise SDError("SD-Karte: Blockgroesse nicht setzbar")
        self.ready = True
    def _wait_idle(self, tries=50):
        # Nach einem Block weiter takten, bis die Karte 0xFF liefert
        for i in range(tries):
            if self.spi.clock_bytes(2).endswith(b'\xff'):
                return
        raise SDError("SD-Karte bleibt beschaeftigt")
    def recover(self):
        # Nach einem Fehler: Lesen beenden, notfalls neu starten
        try:
            self._command(CMD_STOP, 0)
            for i in range(50):
                if self.spi.clock_bytes(16).endswith(b'\xff' * 4):
                    return
        except SDError:
            pass
        reactor = self.spi.reactor
        self.init(reactor)
    def _addr(self, sector):
        return sector if self.high_capacity else sector * SECTOR
    def _wait_token(self, tries=200):
        for i in range(tries):
            b = self.spi.clock_bytes(1)
            if b[0] == 0xFE:
                return
            if b[0] != 0xFF:
                raise SDError("SD-Karte: Lesefehler 0x%02X" % (b[0],))
        raise SDError("SD-Karte: keine Daten")
    def read_sector(self, sector):
        for tries in range(4):
            try:
                return self._read_sector_once(sector)
            except SDError as e:
                if tries == 3 or not self.ready:
                    raise
                logging.info("rf_sdcard: %s, neuer Versuch", e)
                self.recover()
    def _read_sector_once(self, sector):
        if not self.ready:
            raise SDError("SD-Karte nicht bereit")
        self._command(CMD_READ_SINGLE, self._addr(sector))
        r = self.spi.clock_bytes(8).lstrip(b'\xff')
        if not r or r[0] != 0x00:
            raise SDError("SD-Karte: Lesebefehl abgelehnt")
        # Das Startzeichen kann schon in den 8 Bytes stecken
        rest = r[1:]
        if b'\xfe' in rest:
            data = rest[rest.index(b'\xfe') + 1:]
        else:
            self._wait_token()
            data = b''
        data += self.spi.clock_bytes(SECTOR + 2 - len(data))
        block, crc = data[:SECTOR], data[SECTOR:SECTOR + 2]
        self._wait_idle()
        if binascii.crc_hqx(block, 0) != struct.unpack('>H', crc)[0]:
            raise SDError("SD-Karte: Pruefsumme falsch (Sektor %d)"
                          % (sector,))
        return block
    def read_sectors(self, sector, count, callback):
        # Mehrere Sektoren am Stueck (CMD18), callback(bytes) je Sektor
        if not self.ready:
            raise SDError("SD-Karte nicht bereit")
        self._command(CMD_READ_MULTI, self._addr(sector))
        r = self.spi.clock_bytes(8).lstrip(b'\xff')
        if not r or r[0] != 0x00:
            raise SDError("SD-Karte: Lesebefehl abgelehnt")
        buf = bytearray(r[1:])
        done = 0
        try:
            while done < count:
                # Bytes vor dem Startzeichen ueberspringen
                while True:
                    i = 0
                    while i < len(buf) and buf[i] == 0xFF:
                        i += 1
                    del buf[:i]
                    if buf:
                        break
                    buf += self.spi.transfer(
                        [[0xFF] * CHUNK for k in range(4)])
                if buf[0] != 0xFE:
                    raise SDError("SD-Karte: Lesefehler 0x%02X" % (buf[0],))
                need = SECTOR + 3 - len(buf)
                if need > 0:
                    left = (count - done - 1) * (SECTOR + 3)
                    want = min(need + left, self.spi.burst * CHUNK)
                    want = max(want, need)
                    chunks = []
                    while want > 0:
                        n = min(CHUNK, want)
                        chunks.append([0xFF] * n)
                        want -= n
                    buf += self.spi.transfer(chunks)
                block = bytes(buf[1:SECTOR + 1])
                crc = struct.unpack('>H', bytes(buf[SECTOR + 1:SECTOR + 3]))[0]
                del buf[:SECTOR + 3]
                if binascii.crc_hqx(block, 0) != crc:
                    raise SDError("SD-Karte: Pruefsumme falsch (Sektor %d)"
                                  % (sector + done,))
                callback(block)
                done += 1
        finally:
            # Lesen beenden (CMD12) und warten, bis die Karte frei ist
            # Danach Antwort (R1) und Busy (0x00) abwarten, bis 0xFF kommt
            self._command(CMD_STOP, 0)
            for i in range(200):
                if self.spi.clock_bytes(16).endswith(b'\xff' * 4):
                    break


######################################################################
# FAT12/16/32, nur lesen
######################################################################

class FATEntry:
    def __init__(self, name, path, is_dir, cluster, size, mtime=0):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.cluster = cluster
        self.size = size
        self.mtime = mtime


class FATVolume:
    def __init__(self, card):
        self.card = card
        self.fat_cache = {}
        s0 = card.read_sector(0)
        if s0[510:512] != b'\x55\xaa':
            raise SDError("SD-Karte nicht formatiert")
        lba = 0
        if not self._is_boot_sector(s0):
            for i in range(4):
                e = s0[446 + 16 * i:462 + 16 * i]
                ptype = e[4]
                start = struct.unpack('<I', e[8:12])[0]
                if ptype == 0x07:
                    raise SDError("SD-Karte: exFAT/NTFS wird nicht "
                                  "unterstuetzt, bitte FAT32 formatieren")
                if ptype in (0x01, 0x04, 0x06, 0x0B, 0x0C, 0x0E) and start:
                    lba = start
                    break
            else:
                raise SDError("SD-Karte: keine FAT-Partition")
            s0 = card.read_sector(lba)
        if s0[3:11] == b'EXFAT   ':
            raise SDError("SD-Karte: exFAT wird nicht unterstuetzt, "
                          "bitte FAT32 formatieren")
        if not self._is_boot_sector(s0):
            raise SDError("SD-Karte: kein FAT-Dateisystem")
        bps, spc, rsv, nfats, rootent, tot16 = struct.unpack(
            '<HBHBHH', s0[11:21])
        fatsz16 = struct.unpack('<H', s0[22:24])[0]
        tot32 = struct.unpack('<I', s0[32:36])[0]
        fatsz32 = struct.unpack('<I', s0[36:40])[0]
        rootclus = struct.unpack('<I', s0[44:48])[0]
        if bps != SECTOR:
            raise SDError("SD-Karte: Sektorgroesse %d nicht unterstuetzt"
                          % (bps,))
        fatsz = fatsz16 or fatsz32
        total = tot16 or tot32
        root_secs = (rootent * 32 + SECTOR - 1) // SECTOR
        self.spc = spc
        self.fat_start = lba + rsv
        self.root_start = lba + rsv + nfats * fatsz
        self.root_secs = root_secs
        self.data_start = self.root_start + root_secs
        clusters = (total - (rsv + nfats * fatsz + root_secs)) // spc
        if clusters < 4085:
            self.fat_type = 12
        elif clusters < 65525:
            self.fat_type = 16
        else:
            self.fat_type = 32
        self.root_cluster = rootclus if self.fat_type == 32 else 0
    def _is_boot_sector(self, s):
        if s[0] not in (0xEB, 0xE9):
            return False
        bps = struct.unpack('<H', s[11:13])[0]
        return bps in (512, 1024, 2048, 4096) and s[13] in (
            1, 2, 4, 8, 16, 32, 64, 128) and s[16] in (1, 2)
    def _fat_sector(self, sec):
        data = self.fat_cache.get(sec)
        if data is None:
            if len(self.fat_cache) > 64:
                self.fat_cache.clear()
            data = self.fat_cache[sec] = self.card.read_sector(sec)
        return data
    def next_cluster(self, c):
        if self.fat_type == 32:
            off = c * 4
            s = self._fat_sector(self.fat_start + off // SECTOR)
            n = struct.unpack('<I', s[off % SECTOR:off % SECTOR + 4])[0]
            n &= 0x0FFFFFFF
            return None if n >= 0x0FFFFFF8 or n < 2 else n
        if self.fat_type == 16:
            off = c * 2
            s = self._fat_sector(self.fat_start + off // SECTOR)
            n = struct.unpack('<H', s[off % SECTOR:off % SECTOR + 2])[0]
            return None if n >= 0xFFF8 or n < 2 else n
        off = c + c // 2
        lo = self._fat_sector(self.fat_start + off // SECTOR)[off % SECTOR]
        off2 = off + 1
        hi = self._fat_sector(self.fat_start + off2 // SECTOR)[off2 % SECTOR]
        n = lo | (hi << 8)
        n = n >> 4 if c & 1 else n & 0xFFF
        return None if n >= 0xFF8 or n < 2 else n
    def cluster_sector(self, c):
        return self.data_start + (c - 2) * self.spc
    def _chain(self, c, limit=1 << 20):
        out = []
        while c is not None and len(out) < limit:
            out.append(c)
            c = self.next_cluster(c)
        return out
    def _dir_sectors(self, cluster):
        if cluster == 0 and self.fat_type != 32:
            for i in range(self.root_secs):
                yield self.root_start + i
            return
        if cluster == 0:
            cluster = self.root_cluster
        for c in self._chain(cluster, 4096):
            base = self.cluster_sector(c)
            for i in range(self.spc):
                yield base + i
    def list_dir(self, cluster, prefix=''):
        out = []
        lfn = {}
        for sec in self._dir_sectors(cluster):
            data = self.card.read_sector(sec)
            for o in range(0, SECTOR, 32):
                e = data[o:o + 32]
                first = e[0]
                if first == 0x00:
                    return out
                if first == 0xE5:
                    lfn = {}
                    continue
                attr = e[11]
                if attr == 0x0F:
                    seq = first & 0x1F
                    part = e[1:11] + e[14:26] + e[28:32]
                    lfn[seq] = part.decode('utf-16-le', 'ignore')
                    continue
                if attr & 0x08:            # Datentraegername
                    lfn = {}
                    continue
                if lfn:
                    name = ''.join(lfn[k] for k in sorted(lfn))
                    name = name.split('\x00')[0].rstrip('￿')
                else:
                    base = e[0:8].decode('latin-1').rstrip()
                    ext = e[8:11].decode('latin-1').rstrip()
                    if e[12] & 0x08:
                        base = base.lower()
                    if e[12] & 0x10:
                        ext = ext.lower()
                    name = base + ('.' + ext if ext else '')
                lfn = {}
                if name in ('.', '..') or attr & 0x06:   # versteckt/System
                    continue
                hi, lo = struct.unpack('<H', e[20:22])[0], \
                    struct.unpack('<H', e[26:28])[0]
                cl = (hi << 16 | lo) if self.fat_type == 32 else lo
                size = struct.unpack('<I', e[28:32])[0]
                ftime, fdate = struct.unpack('<HH', e[22:26])
                try:
                    mtime = time.mktime((
                        1980 + (fdate >> 9), (fdate >> 5) & 0xF, fdate & 0x1F,
                        ftime >> 11, (ftime >> 5) & 0x3F, (ftime & 0x1F) * 2,
                        0, 0, -1))
                except (ValueError, OverflowError):
                    mtime = 0
                out.append(FATEntry(name, prefix + name, bool(attr & 0x10),
                                    cl, size, mtime))
        return out
    def list_gcode(self):
        files = []
        def walk(cluster, prefix, depth):
            for e in self.list_dir(cluster, prefix):
                if len(files) >= MAX_FILES:
                    return
                if e.is_dir:
                    if depth < MAX_DEPTH and not e.name.startswith('.'):
                        walk(e.cluster, e.path + '/', depth + 1)
                elif (e.name.lower().endswith(GCODE_EXT)
                      and not e.name.startswith('._')):
                    files.append(e)
        walk(0, '', 0)
        files.sort(key=lambda e: e.path.lower())
        return files
    def read_file(self, entry, write, progress=None):
        left = entry.size
        chain = self._chain(entry.cluster) if entry.size else []
        # Aufeinanderfolgende Cluster am Stueck lesen
        runs = []
        for c in chain:
            if runs and runs[-1][0] + runs[-1][1] == c:
                runs[-1][1] += 1
            else:
                runs.append([c, 1])
        state = {'left': left}
        def got(block):
            n = min(SECTOR, state['left'])
            if n > 0:
                write(block[:n])
                state['left'] -= n
                if progress is not None:
                    progress(entry.size - state['left'], entry.size)
        for c, n in runs:
            if state['left'] <= 0:
                break
            secs = min(n * self.spc,
                       (state['left'] + SECTOR - 1) // SECTOR)
            first = self.cluster_sector(c)
            tries = 0
            while secs > 0:
                state['run'] = 0
                def got_run(block):
                    state['run'] += 1
                    got(block)
                try:
                    self.card.read_sectors(first, secs, got_run)
                    break
                except SDError as e:
                    # Ab dem ersten fehlenden Sektor neu lesen
                    first += state['run']
                    secs -= state['run']
                    tries += 1
                    logging.info("rf_sdcard: %s, neuer Versuch %d", e, tries)
                    self.retries = getattr(self, 'retries', 0) + 1
                    if tries > 8:
                        raise
                    self.card.recover()
        if state['left'] > 0:
            raise SDError("SD-Karte: Datei unvollstaendig")


######################################################################
# Klipper-Modul
######################################################################

class RFSDCard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name()
        self.spi = MCUSPIPipe(config)
        self.card = SDCard(self.spi)
        self.volume = None
        self.files = []
        self.present = None             # None = keine Kartenerkennung
        self.error = ''
        self.busy = False
        self.progress = 0.
        self.folder = config.get('folder', 'SD-Karte')
        self.mutex = self.reactor.mutex()
        self.msg_timer = self.reactor.register_timer(self._clear_msg)
        self.last_msg = None
        detect = config.get('detect_pin', None)
        if detect is not None:
            self.present = False
            buttons = self.printer.load_object(config, 'buttons')
            buttons.register_buttons([detect], self._detect_callback)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('RF_SD_LIST', self.cmd_RF_SD_LIST,
                                    desc=self.cmd_RF_SD_LIST_help)
        self.gcode.register_command('RF_SD_PRINT', self.cmd_RF_SD_PRINT,
                                    desc=self.cmd_RF_SD_PRINT_help)
        self.gcode.register_command('RF_SD_COPY', self.cmd_RF_SD_COPY,
                                    desc=self.cmd_RF_SD_COPY_help)
        self.gcode.register_command('RF_SD_TEST', self.cmd_RF_SD_TEST,
                                    desc=self.cmd_RF_SD_TEST_help)
        self.retries = 0
        self.printer.register_event_handler('klippy:ready', self._ready)
    # Status fuer Mainsail und Makros
    def get_status(self, eventtime):
        return {'present': bool(self.present) or (
                    self.present is None and self.volume is not None),
                'ready': self.volume is not None,
                'files': [e.path for e in self.files],
                'busy': self.busy, 'progress': round(self.progress, 3),
                'error': self.error}
    # Anzeige
    def _message(self, msg, timeout=5.):
        ds = self.printer.lookup_object('display_status', None)
        if ds is not None:
            ds.message = msg
            self.last_msg = msg
            self.reactor.update_timer(self.msg_timer,
                                      self.reactor.monotonic() + timeout)
    def _clear_msg(self, eventtime):
        ds = self.printer.lookup_object('display_status', None)
        if ds is not None and ds.message == self.last_msg:
            ds.message = None
        return self.reactor.NEVER
    def _is_printing(self):
        sd = self.printer.lookup_object('virtual_sdcard', None)
        return sd is not None and sd.is_active()
    # Karte einlesen
    def _ready(self):
        if self.present:
            self.reactor.register_callback(self._mount_cb)
    def _detect_callback(self, eventtime, state):
        self.present = bool(state)
        if state:
            self.reactor.register_callback(self._mount_cb,
                                           eventtime + .5)
        else:
            self.volume = None
            self.files = []
            self.card.ready = False
            self.error = ''
            self._message("SD-Karte entfernt")
            self.gcode.respond_info("SD-Karte entfernt")
    def _mount_cb(self, eventtime):
        if self._is_printing():
            # Waehrend des Drucks nicht lesen, das passiert beim Oeffnen
            # des Menues oder mit RF_SD_LIST
            return
        try:
            self.mount()
            self._message("SD-Karte: %d Dateien" % (len(self.files),))
            self.gcode.respond_info("SD-Karte eingelegt, %d Dateien"
                                    % (len(self.files),))
        except Exception as e:
            self._message("SD-Karte: Fehler")
            self.gcode.respond_info("SD-Karte: %s" % (e,))
    def mount(self, force=False):
        with self.mutex:
            if self.volume is not None and not force:
                return self.files
            if self.present is False:
                raise SDError("Keine SD-Karte eingelegt")
            self.volume = None
            self.files = []
            try:
                self.card.init(self.reactor)
                vol = FATVolume(self.card)
                self.files = vol.list_gcode()
                self.volume = vol
                self.error = ''
            except Exception as e:
                self.error = str(e)
                logging.info("rf_sdcard: %s", e)
                raise
            return self.files
    def try_files(self):
        # Fuer das Menue: Dateien der Karte, leer ohne Karte (ohne Fehler)
        if self.present is False:
            return []
        if self.volume is None or self.present is None:
            # Ohne Kartenerkennung bei jedem Oeffnen neu einlesen
            self.volume = None
            try:
                self.mount()
            except Exception:
                return []
        return list(self.files)
    def _find(self, name):
        name = name.strip().lstrip('/')
        for e in self.files:
            if e.path == name or e.path.lower() == name.lower():
                return e
        return None
    def _target_path(self, entry):
        sd = self.printer.lookup_object('virtual_sdcard', None)
        if sd is None:
            raise SDError("[virtual_sdcard] fehlt in der printer.cfg")
        base = sd.sdcard_dirname
        rel = os.path.join(self.folder, entry.path)
        return os.path.join(base, rel), rel
    def copy(self, entry, gcmd=None):
        path, rel = self._target_path(entry)
        # Schon kopiert und unveraendert (Groesse und Aenderungszeit)?
        if (os.path.exists(path) and os.path.getsize(path) == entry.size
                and abs(os.path.getmtime(path) - entry.mtime) < 2.):
            return rel
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.makedirs(d)
        tmp = path + '.part'
        self.busy = True
        self.progress = 0.
        state = {'last': 0., 'pct': -1}
        def progress(done, total):
            self.progress = float(done) / total if total else 1.
            pct = int(self.progress * 100)
            now = self.reactor.monotonic()
            if pct != state['pct'] and now - state['last'] > 1.:
                state['last'] = now
                state['pct'] = pct
                self._message("SD kopieren %d%%" % (pct,), 30.)
        start = self.reactor.monotonic()
        try:
            with self.mutex:
                with open(tmp, 'wb') as f:
                    self.volume.read_file(entry, f.write, progress)
            if entry.mtime:
                os.utime(tmp, (entry.mtime, entry.mtime))
            os.rename(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        finally:
            self.busy = False
        secs = self.reactor.monotonic() - start
        if gcmd is not None:
            gcmd.respond_info("SD-Karte: %s kopiert (%d kB in %.0f s)"
                              % (entry.path, entry.size // 1024, secs))
        self._message("SD kopiert", 3.)
        return rel
    # G-Code-Befehle
    cmd_RF_SD_LIST_help = "Dateien auf der SD-Karte im Drucker anzeigen"
    def cmd_RF_SD_LIST(self, gcmd):
        try:
            files = self.mount(force=gcmd.get_int('RELOAD', 1) != 0)
        except Exception as e:
            raise gcmd.error("SD-Karte: %s" % (e,))
        if not files:
            gcmd.respond_info("SD-Karte: keine G-Code-Dateien")
            return
        lines = ["SD-Karte, %d Dateien:" % (len(files),)]
        for e in files:
            lines.append("  %s (%d kB)" % (e.path, (e.size + 1023) // 1024))
        gcmd.respond_info("\n".join(lines))
    def _get_entry(self, gcmd):
        if self._is_printing():
            raise gcmd.error("SD-Karte: Es laeuft schon ein Druck")
        name = gcmd.get('FILE')
        try:
            self.mount()
        except Exception as e:
            raise gcmd.error("SD-Karte: %s" % (e,))
        entry = self._find(name)
        if entry is None:
            raise gcmd.error("SD-Karte: Datei '%s' nicht gefunden" % (name,))
        return entry
    cmd_RF_SD_COPY_help = "Datei von der SD-Karte auf den Raspberry Pi kopieren"
    def cmd_RF_SD_COPY(self, gcmd):
        # FILE=* kopiert alle Dateien (danach in Mainsail unter G-Code-Dateien)
        if gcmd.get('FILE').strip() == '*':
            if self._is_printing():
                raise gcmd.error("SD-Karte: Es laeuft ein Druck")
            try:
                files = self.mount()
                for entry in files:
                    self.copy(entry, gcmd)
            except Exception as e:
                raise gcmd.error("SD-Karte: %s" % (e,))
            gcmd.respond_info("SD-Karte: %d Dateien liegen unter %s"
                              % (len(files), self.folder))
            return
        entry = self._get_entry(gcmd)
        try:
            rel = self.copy(entry, gcmd)
        except Exception as e:
            raise gcmd.error("SD-Karte: %s" % (e,))
        gcmd.respond_info("SD-Karte: liegt jetzt unter %s" % (rel,))
    cmd_RF_SD_TEST_help = "Lesegeschwindigkeit der SD-Karte messen"
    def cmd_RF_SD_TEST(self, gcmd):
        if self._is_printing():
            raise gcmd.error("SD-Karte: Es laeuft ein Druck")
        kb = gcmd.get_int('KB', 256, minval=16)
        factor = gcmd.get_float('PACE', None, minval=0.)
        burst = gcmd.get_int('BURST', None, minval=1, maxval=64)
        if factor is not None:
            self.spi.pace_factor = factor
            self.spi.pace = 0.
        if burst is not None:
            self.spi.burst = burst
        try:
            self.mount()
        except Exception as e:
            raise gcmd.error("SD-Karte: %s" % (e,))
        if not self.files:
            raise gcmd.error("SD-Karte: keine Datei zum Testen")
        entry = max(self.files, key=lambda e: e.size)
        vol = self.volume
        vol.retries = 0
        count = {'n': 0}
        class Stop(Exception):
            pass
        def write(data):
            count['n'] += len(data)
            if count['n'] >= kb * 1024:
                raise Stop()
        start = self.reactor.monotonic()
        with self.mutex:
            try:
                vol.read_file(entry, write)
            except Stop:
                self.card.recover()
        secs = self.reactor.monotonic() - start
        gcmd.respond_info(
            "SD-Karte: %d kB in %.1f s = %.1f kB/s, Wiederholungen %d "
            "(pace_factor %.2f, burst %d)"
            % (count['n'] // 1024, secs, count['n'] / 1024. / secs,
               vol.retries, self.spi.pace_factor, self.spi.burst))
    cmd_RF_SD_PRINT_help = "Datei von der SD-Karte drucken"
    def cmd_RF_SD_PRINT(self, gcmd):
        entry = self._get_entry(gcmd)
        try:
            rel = self.copy(entry, gcmd)
        except Exception as e:
            raise gcmd.error("SD-Karte: %s" % (e,))
        self.gcode.run_script_from_command(
            'SDCARD_PRINT_FILE FILENAME="%s"' % (rel,))


def load_config(config):
    return RFSDCard(config)

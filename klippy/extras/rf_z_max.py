# Z-Max-Endstop am RF2000 und RF2000 v2
#
# Der Schalter sitzt am unteren Ende der Z-Achse (grosses Z). Ist er
# ausgeloest, faehrt das Bett nicht weiter nach unten. Eine normale Fahrt kann
# die MCU nicht an einem Schalter anhalten. Fahrten nach unten laufen deshalb
# wie die Referenzfahrt im Drip-Modus mit ueberwachtem Endstop.
#
# This file may be distributed under the terms of the GNU GPLv3 license.
from . import homing

# Bis zu dieser Strecke bleiben Fahrten mit X/Y-Anteil (Bettnetz) und Fahrten
# waehrend eines Drucks (Schichtwechsel, Z-Hop) normale Fahrten, damit der
# Druck nicht bei jeder Schicht anhaelt
SMALL_MOVE = 1.

class RFZMax:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        # Ab dieser Z-Position werden Fahrten nach unten ueberwacht
        self.guard_height = config.getfloat('guard_height', 150.)
        # RF_Z_MAX_SEEK faehrt hoechstens bis hier (Repetier: G1 Z210)
        self.seek_limit = config.getfloat('seek_limit', 210., above=0.)
        self.seek_speed = config.getfloat('seek_speed', 9., above=0.)
        self.toolhead = self.normal_move = None
        self.is_triggered = False
        ppins = self.printer.lookup_object('pins')
        self.mcu_endstop = ppins.setup_pin('endstop', config.get('pin'))
        query_endstops = self.printer.load_object(config, 'query_endstops')
        query_endstops.register_endstop(self.mcu_endstop, 'z_max')
        self.printer.register_event_handler('klippy:mcu_identify',
                                            self._handle_mcu_identify)
        self.printer.register_event_handler('klippy:connect',
                                            self._handle_connect)
        self.gcode.register_command('RF_Z_MAX_SEEK', self.cmd_RF_Z_MAX_SEEK,
                                    desc=self.cmd_RF_Z_MAX_SEEK_help)
    def _handle_mcu_identify(self):
        kin = self.printer.lookup_object('toolhead').get_kinematics()
        for stepper in kin.get_steppers():
            if stepper.is_active_axis('z'):
                self.mcu_endstop.add_stepper(stepper)
    def _handle_connect(self):
        # Alle Fahrten (G-Code, Makros, Bettnetz) laufen ueber toolhead.move
        self.toolhead = self.printer.lookup_object('toolhead')
        self.normal_move = self.toolhead.move
        self.toolhead.move = self._move
    def _is_z_homed(self):
        kin = self.toolhead.get_kinematics()
        status = kin.get_status(self.reactor.monotonic())
        return 'z' in status['homed_axes']
    def _is_printing(self):
        print_stats = self.printer.lookup_object('print_stats', None)
        if print_stats is None:
            return False
        status = print_stats.get_status(self.reactor.monotonic())
        return status['state'] == 'printing'
    def _needs_guard(self, curpos, newpos):
        dist = newpos[2] - curpos[2]
        if dist <= .000001 or newpos[2] <= self.guard_height:
            return False
        if dist <= SMALL_MOVE:
            has_xy = (abs(newpos[0] - curpos[0]) > .000001
                      or abs(newpos[1] - curpos[1]) > .000001)
            if has_xy or self._is_printing():
                return False
        return self._is_z_homed()
    def _move(self, newpos, speed):
        curpos = self.toolhead.get_position()
        if not self._needs_guard(curpos, newpos):
            self.normal_move(newpos, speed)
            return
        # Erst Z ueberwacht fahren, dann X, Y und Extruder auf der Hoehe, die
        # erreicht wurde. Nach unten ist diese Reihenfolge immer sicher.
        newpos = list(newpos)
        self.move_down(newpos[2], speed)
        z = self.toolhead.get_position()[2]
        self.normal_move([newpos[0], newpos[1], z] + list(newpos[3:]), speed)
        # Die Z-Position kann vom Ziel abweichen
        self.printer.lookup_object('gcode_move').reset_last_position()
    def _query(self):
        print_time = self.toolhead.get_last_move_time()
        self.is_triggered = not not self.mcu_endstop.query_endstop(print_time)
        return self.is_triggered
    def _report_stop(self, z):
        self.gcode.respond_info(
            "Z-Max-Endstop ausgeloest bei Z %.2f, es geht nicht weiter nach"
            " unten" % (z,))
    # Fahrt nach unten bis zum Ziel oder bis zum Schalter. cancel ist eine
    # Completion, mit der z_jog beim Loslassen der Taste vorher anhaelt.
    def move_down(self, target_z, speed, cancel=None):
        toolhead = self.toolhead
        toolhead.flush_step_generation()
        startpos = toolhead.get_position()
        if target_z <= startpos[2]:
            return
        if self._query():
            self._report_stop(startpos[2])
            return
        movepos = startpos[:2] + [target_z] + startpos[3:]
        # Ziel pruefen (Fahrbereich), bevor der Endstop scharf geschaltet wird
        kin = toolhead.get_kinematics()
        if target_z > kin.limits[2][1]:
            raise self.gcode.error("Z Fahrt ausserhalb des Fahrbereichs: %.3f"
                                   % (target_z,))
        steppers = self.mcu_endstop.get_steppers()
        start_steps = [s.get_mcu_position() for s in steppers]
        start_z = steppers[0].get_commanded_position()
        step_dist = steppers[0].get_step_dist()
        rest_time = step_dist / min(speed, toolhead.get_kinematics()
                                    .max_z_velocity)
        print_time = toolhead.get_last_move_time()
        trigger = self.mcu_endstop.home_start(
            print_time, homing.ENDSTOP_SAMPLE_TIME,
            homing.ENDSTOP_SAMPLE_COUNT, rest_time)
        trigger_time = 0.
        cancelled = False
        try:
            stop = trigger
            if cancel is not None:
                stop = self.reactor.completion()
                def on_trigger(eventtime):
                    # Jedes Ergebnis zaehlt, beim Ausloesen ist es False
                    # (False = kein Kommunikationsfehler)
                    trigger.wait()
                    if not stop.test():
                        stop.complete(True)
                def on_cancel(eventtime):
                    # False kommt nur aus dem finally unten
                    if cancel.wait() and not stop.test():
                        stop.complete(True)
                self.reactor.register_callback(on_trigger)
                self.reactor.register_callback(on_cancel)
            toolhead.dwell(homing.HOMING_START_DELAY)
            toolhead.drip_move(movepos, speed, stop)
        except self.printer.command_error:
            toolhead.get_kinematics().clear_homing_state("z")
            raise
        finally:
            if cancel is not None:
                cancelled = cancel.test()
                if not cancelled:
                    # Wartenden Callback beenden
                    cancel.complete(False)
            # Endstop immer wieder abmelden, auch nach einem Fehler
            try:
                trigger_time = self.mcu_endstop.home_wait(
                    toolhead.get_last_move_time())
            except self.printer.command_error:
                # Position unbekannt, Z neu referenzieren
                toolhead.get_kinematics().clear_homing_state("z")
                raise
        toolhead.flush_step_generation()
        triggered = trigger_time > 0.
        z = target_z
        if triggered or cancelled:
            # Fahrt endete vor dem Ziel: Weg aus den Schrittmotoren lesen
            moved = steppers[0].get_mcu_position() - start_steps[0]
            z = start_z + moved * step_dist
        toolhead.set_position(startpos[:2] + [z] + startpos[3:])
        if triggered:
            self.is_triggered = True
            self._report_stop(z)
    cmd_RF_Z_MAX_SEEK_help = "Bett bis zum Z-Max-Endstop nach unten fahren"
    def cmd_RF_Z_MAX_SEEK(self, gcmd):
        speed = gcmd.get_float('SPEED', self.seek_speed, above=0.)
        if not self._is_z_homed():
            raise gcmd.error("RF_Z_MAX_SEEK: Zuerst die Z-Achse referenzieren")
        kin = self.toolhead.get_kinematics()
        z_min = kin.get_status(self.reactor.monotonic())['axis_minimum'][2]
        z_max = kin.get_status(self.reactor.monotonic())['axis_maximum'][2]
        limit = max(self.seek_limit, z_max)
        # Der Schalter darf hinter position_max liegen
        kin.update_limits(2, (z_min, limit))
        try:
            self.move_down(limit, speed)
        finally:
            if self._is_z_homed():
                kin.update_limits(2, (z_min, z_max))
        self.printer.lookup_object('gcode_move').reset_last_position()
        if not self.is_triggered:
            gcmd.respond_info(
                "RF_Z_MAX_SEEK: Z-Max-Endstop bis Z %.1f nicht ausgeloest."
                " Schalter mit QUERY_ENDSTOPS pruefen." % (limit,))
    def get_status(self, eventtime):
        return {'triggered': self.is_triggered}

def load_config(config):
    return RFZMax(config)

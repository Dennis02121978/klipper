# Fahren der Z-Achse mit zwei Tasten
#
# Kurzer Druck: fuehrt press_gcode aus. Nach hold_delay Sekunden Halten faehrt
# die Achse konstant, bis die Taste losgelassen wird. Das nutzt wie die
# Referenzfahrt den Drip-Modus, damit sie beim Loslassen sofort stoppt.
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class ZJog:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.press_template = self.gcode_macro.load_template(
            config, 'press_gcode')
        self.hold_delay = config.getfloat('hold_delay', 2., above=0.)
        self.hold_speed = config.getfloat('hold_speed', 3., above=0.)
        self.hold_min_z = config.getfloat('hold_min_z', 0.)
        self.max_margin = config.getfloat('max_margin', .5, minval=0.)
        self.toolhead = None
        self.pressed = 0
        self.hold_timer = None
        self.completion = None
        buttons = self.printer.load_object(config, 'buttons')
        buttons.register_buttons([config.get('increase_pin')],
                                 self._make_callback(1))
        buttons.register_buttons([config.get('decrease_pin')],
                                 self._make_callback(-1))
        self.printer.register_event_handler('klippy:connect',
                                            self._handle_connect)
        self.printer.register_event_handler('klippy:shutdown', self._release)
    def _handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
    def _make_callback(self, direction):
        def callback(eventtime, state):
            if state:
                self._press(eventtime, direction)
            elif self.pressed == direction:
                self._release()
        return callback
    def _press(self, eventtime, direction):
        if self.pressed:
            return
        self.pressed = direction
        self.hold_timer = self.reactor.register_timer(
            self._hold_event, eventtime + self.hold_delay)
        context = self.press_template.create_template_context()
        context['params'] = {'DIR': direction}
        try:
            self.gcode.run_script(self.press_template.render(context))
        except self.gcode.error as e:
            self.gcode.respond_raw("!! %s" % (str(e),))
        except:
            logging.exception("z_jog: Fehler bei press_gcode")
    def _release(self):
        self.pressed = 0
        if self.hold_timer is not None:
            self.reactor.unregister_timer(self.hold_timer)
            self.hold_timer = None
        if self.completion is not None:
            self.completion.complete(True)
    def _hold_event(self, eventtime):
        self.reactor.unregister_timer(self.hold_timer)
        self.hold_timer = None
        try:
            with self.gcode.get_mutex():
                self._hold()
        except self.gcode.error as e:
            self.gcode.respond_raw("!! %s" % (str(e),))
        except:
            logging.exception("z_jog: Fehler beim Fahren")
        return self.reactor.NEVER
    def _hold(self):
        direction = self.pressed
        if not direction or self.printer.is_shutdown():
            return
        toolhead = self.toolhead
        curtime = self.reactor.monotonic()
        print_stats = self.printer.lookup_object('print_stats')
        if print_stats.get_status(curtime)['state'] == 'printing':
            return
        status = toolhead.get_status(curtime)
        if 'z' not in status['homed_axes']:
            return
        pos = toolhead.get_position()
        if direction > 0:
            target = status['axis_maximum'][2] - self.max_margin
            if target <= pos[2]:
                return
        else:
            target = max(self.hold_min_z, status['axis_minimum'][2])
            if target >= pos[2]:
                return
        pos[2] = target
        self.completion = self.reactor.completion()
        try:
            toolhead.drip_move(pos, self.hold_speed, self.completion)
        finally:
            self.completion = None
        if not self.printer.is_shutdown():
            self._sync_position()
    def _sync_position(self):
        # Die Fahrt endet vor dem Ziel: Position aus den Schrittmotoren lesen
        toolhead = self.toolhead
        toolhead.flush_step_generation()
        kin = toolhead.get_kinematics()
        spos = {s.get_name(): s.get_commanded_position()
                for s in kin.get_steppers()}
        cur = toolhead.get_position()
        calc = kin.calc_position(spos)
        newpos = [c if c is not None else t for c, t in zip(calc, cur[:3])]
        toolhead.set_position(newpos + cur[3:])

def load_config(config):
    return ZJog(config)

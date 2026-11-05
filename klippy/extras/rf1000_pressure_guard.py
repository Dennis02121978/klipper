# Pressure guard for RF1000 / RF2000 load cell: emergency pause and
# digit flow compensation (port of the Repetier based RF firmware features
# FEATURE_EMERGENCY_PAUSE and FEATURE_DIGIT_FLOW_COMPENSATION).
#
# The module listens to the tared force of [rf1000_load_cell_probe]
# (subscribe_force) and
#   * pauses the print when the averaged force leaves [emergency_min,
#     emergency_max] (firmware: M3075 S<min> P<max>)
#   * scales extrusion (M221) and feed rate (M220) with the averaged force
#     between flow_min and flow_max (firmware: M3911 S P E F)
#
# All force values use the unit of the "last_force" value of the load cell
# probe (see LCP_READ), NOT the raw "digits" of the original firmware.
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import collections
import logging

FEED_RAMP_STEP = 0.01  # firmware changes the feed factor by 1% per update


class ForceSensor:
    """Sensor type "rf1000_force" for [temperature_sensor <name>]: shows the
    load cell force as a curve in Mainsail/Fluidd (unit shown there: °C)."""

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.probe_name = config.get("probe", "rf1000_load_cell_probe")
        self.callback = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def setup_minmax(self, min_temp, max_temp):
        pass  # forces are not limited here, see rf1000_load_cell_probe

    def setup_callback(self, cb):
        self.callback = cb

    def get_report_time_delta(self):
        return 1.0

    def _handle_ready(self):
        probe = self.printer.lookup_object(self.probe_name)
        probe.subscribe_force(self._on_force)

    def _on_force(self, force):
        if self.callback is not None:
            self.callback(self.reactor.monotonic(), force)


class PressureGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.printer.load_object(config, "gcode_move")
        pheaters = self.printer.load_object(config, "heaters")
        pheaters.add_sensor_factory("rf1000_force", ForceSensor)
        self.probe_name = config.get("probe", "rf1000_load_cell_probe")

        # Emergency pause (both 0 = disabled)
        self.pause_min = config.getfloat("emergency_min", 0.0, maxval=0.0)
        self.pause_max = config.getfloat("emergency_max", 0.0, minval=0.0)
        self.pause_samples = config.getint("emergency_samples", 5, minval=1)
        self.pause_gcode = config.get("pause_gcode", "PAUSE")

        # Flow compensation (flow_percent = feed_percent = 0 -> disabled)
        self.flow_min = config.getfloat("flow_min", 0.0, minval=0.0)
        self.flow_max = config.getfloat("flow_max", 0.0, minval=0.0)
        self.flow_percent = config.getfloat(
            "flow_percent", 0.0, minval=-99.0, maxval=99.0
        )
        self.feed_percent = config.getfloat(
            "feed_percent", 0.0, minval=-90.0, maxval=99.0
        )
        self.flow_samples = config.getint("flow_samples", 4, minval=1)
        self.flow_min_z = config.getfloat("flow_min_z", 0.5, minval=0.0)
        self.update_interval = config.getfloat("update_interval", 0.25, above=0.0)
        self._check_ranges(config.error)

        # Runtime state
        self.pause_buf = collections.deque(maxlen=self.pause_samples)
        self.flow_buf = collections.deque(maxlen=self.flow_samples)
        self.pause_pending = False
        self.user_flow = 1.0  # value set by the user via M221
        self.user_feed = 1.0  # value set by the user via M220
        self.dyn_flow = 1.0  # factor of the compensation
        self.dyn_feed = 1.0
        self.last_avg = 0.0
        self.toolhead = self.print_stats = self.pause_resume = None
        self.timer = None

        # Take over M220 / M221 to keep the user value and our factor apart
        self.old_m220 = self.gcode.register_command("M220", None)
        self.old_m221 = self.gcode.register_command("M221", None)
        self.gcode.register_command("M220", self.cmd_M220, desc="Set speed factor")
        self.gcode.register_command("M221", self.cmd_M221, desc="Set extrude factor")
        self.gcode.register_command(
            "RF_EMERGENCY_PAUSE",
            self.cmd_RF_EMERGENCY_PAUSE,
            desc=self.cmd_RF_EMERGENCY_PAUSE_help,
        )
        self.gcode.register_command(
            "RF_FLOW_COMP", self.cmd_RF_FLOW_COMP, desc=self.cmd_RF_FLOW_COMP_help
        )
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    # ------------------------------------------------------------------
    def _check_ranges(self, error):
        if self.pause_min > 0.0 or self.pause_max < 0.0:
            raise error("emergency_min must be <= 0 and emergency_max >= 0")
        if self.flow_max and self.flow_max < self.flow_min:
            raise error("flow_max must not be smaller than flow_min")

    def _handle_ready(self):
        self.toolhead = self.printer.lookup_object("toolhead")
        self.print_stats = self.printer.lookup_object("print_stats", None)
        self.pause_resume = self.printer.lookup_object("pause_resume", None)
        probe = self.printer.lookup_object(self.probe_name)
        probe.subscribe_force(self._on_force)
        self.timer = self.reactor.register_timer(
            self._update_flow, self.reactor.NOW
        )

    def get_status(self, eventtime):
        return {
            "emergency_min": self.pause_min,
            "emergency_max": self.pause_max,
            "flow_min": self.flow_min,
            "flow_max": self.flow_max,
            "flow_percent": self.flow_percent,
            "feed_percent": self.feed_percent,
            "flow_factor": self.dyn_flow,
            "feed_factor": self.dyn_feed,
            "average_force": self.last_avg,
        }

    # ------------------------------------------------------------------
    def _is_printing(self, eventtime):
        if self.print_stats is None or self.toolhead is None:
            return False
        if self.print_stats.get_status(eventtime)["state"] != "printing":
            return False
        if self.pause_resume is not None and self.pause_resume.is_paused:
            return False
        return True

    def _is_homed(self, eventtime):
        homed = self.toolhead.get_status(eventtime)["homed_axes"]
        return all(a in homed for a in "xyz")

    def _on_force(self, force):
        # Called from the ADC callback for every sample
        self.flow_buf.append(force)
        if self.flow_buf:
            self.last_avg = sum(self.flow_buf) / len(self.flow_buf)
        if not (self.pause_min or self.pause_max):
            return
        eventtime = self.reactor.monotonic()
        if self.pause_pending or not (
            self._is_printing(eventtime) and self._is_homed(eventtime)
        ):
            self.pause_buf.clear()
            return
        self.pause_buf.append(force)
        if len(self.pause_buf) < self.pause_samples:
            return
        avg = sum(self.pause_buf) / len(self.pause_buf)
        if avg < self.pause_min or avg > self.pause_max:
            self.pause_buf.clear()
            self.pause_pending = True
            self.reactor.register_callback(
                lambda et, a=avg: self._emergency_pause(a)
            )

    def _emergency_pause(self, avg):
        try:
            self.gcode.respond_info(
                "emergency pause: force %.0f outside [%.0f, %.0f]"
                % (avg, self.pause_min, self.pause_max)
            )
            if self.pause_resume is not None:
                self.pause_resume.send_pause_command()
            self.gcode.run_script(self.pause_gcode)
        except Exception:
            logging.exception("rf1000_pressure_guard: emergency pause failed")
        finally:
            self.pause_pending = False

    # ------------------------------------------------------------------
    def _share(self, digits):
        """0.0 below flow_min, 1.0 above flow_max, linear in between."""
        if digits <= self.flow_min:
            return 0.0
        if digits >= self.flow_max:
            return 1.0
        return (digits - self.flow_min) / (self.flow_max - self.flow_min)

    def _update_flow(self, eventtime):
        goal_flow, goal_feed = 1.0, 1.0
        enabled = self.flow_percent or self.feed_percent
        if (
            enabled
            and self.flow_buf
            and self._is_printing(eventtime)
            and self.toolhead.get_position()[2] > self.flow_min_z
        ):
            share = self._share(abs(sum(self.flow_buf) / len(self.flow_buf)))
            goal_flow = 1.0 + 0.01 * self.flow_percent * share
            goal_feed = 1.0 + 0.01 * self.feed_percent * share
        # flow follows immediately, feed is ramped like in the firmware
        self._set_flow(goal_flow)
        if abs(goal_feed - self.dyn_feed) <= FEED_RAMP_STEP:
            new_feed = goal_feed
        else:
            new_feed = self.dyn_feed + (
                FEED_RAMP_STEP if goal_feed > self.dyn_feed else -FEED_RAMP_STEP
            )
        self._set_feed(new_feed)
        return eventtime + self.update_interval

    def _call_old(self, old, name, percent):
        value = "%.4f" % percent
        gcmd = self.gcode.create_gcode_command(name, "%s S%s" % (name, value), {"S": value})
        old(gcmd)

    def _set_flow(self, factor):
        if abs(factor - self.dyn_flow) < 1e-4:
            return
        self.dyn_flow = factor
        self._call_old(self.old_m221, "M221", self.user_flow * factor * 100.0)

    def _set_feed(self, factor):
        if abs(factor - self.dyn_feed) < 1e-4:
            return
        self.dyn_feed = factor
        self._call_old(self.old_m220, "M220", self.user_feed * factor * 100.0)

    def cmd_M221(self, gcmd):
        percent = gcmd.get_float("S", 100.0, above=0.0)
        self.user_flow = percent / 100.0
        self._call_old(self.old_m221, "M221", percent * self.dyn_flow)

    def cmd_M220(self, gcmd):
        percent = gcmd.get_float("S", 100.0, above=0.0)
        self.user_feed = percent / 100.0
        self._call_old(self.old_m220, "M220", percent * self.dyn_feed)

    # ------------------------------------------------------------------
    cmd_RF_EMERGENCY_PAUSE_help = (
        "Set/show emergency pause limits: RF_EMERGENCY_PAUSE [MIN=<=0] "
        "[MAX=>=0], MIN=0 MAX=0 disables"
    )

    def cmd_RF_EMERGENCY_PAUSE(self, gcmd):
        new_min = gcmd.get_float("MIN", self.pause_min, maxval=0.0)
        new_max = gcmd.get_float("MAX", self.pause_max, minval=0.0)
        self.pause_min, self.pause_max = new_min, new_max
        self.pause_buf.clear()
        if not (new_min or new_max):
            gcmd.respond_info("Emergency pause disabled")
        else:
            gcmd.respond_info(
                "Emergency pause: min %.0f, max %.0f (average of %d samples)"
                % (new_min, new_max, self.pause_samples)
            )

    cmd_RF_FLOW_COMP_help = (
        "Set/show force dependent flow compensation: RF_FLOW_COMP "
        "[MIN=<force>] [MAX=<force>] [FLOW=<%>] [FEED=<%>]"
    )

    def cmd_RF_FLOW_COMP(self, gcmd):
        new_min = abs(gcmd.get_float("MIN", self.flow_min))
        new_max = abs(gcmd.get_float("MAX", self.flow_max))
        if new_min > new_max:
            new_min, new_max = new_max, new_min
        self.flow_min, self.flow_max = new_min, new_max
        self.flow_percent = gcmd.get_float(
            "FLOW", self.flow_percent, minval=-99.0, maxval=99.0
        )
        self.feed_percent = gcmd.get_float(
            "FEED", self.feed_percent, minval=-90.0, maxval=99.0
        )
        gcmd.respond_info(
            "Flow compensation: min %.0f, max %.0f, flow %+.0f%%, feed %+.0f%%"
            % (self.flow_min, self.flow_max, self.flow_percent, self.feed_percent)
        )


def load_config(config):
    return PressureGuard(config)

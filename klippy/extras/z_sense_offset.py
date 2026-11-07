# Correct Z offset for first layer for thermal elongation of the hotend, based
# on the required extrusion force measured by the load cell probe. Requires
# to enable the load_cell_probe module.
#
# Copyright (C) 2020 Martin Hierholzer <martin@hierholzer.info>
#
# Based on the implementation by Nibbles/Wessix on:
# https://github.com/RF1000community/Repetier-Firmware
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging

class SenseOffsetSensor:
    """Sensor type "z_sense_offset" for [temperature_sensor <name>]: shows the
    current sense offset in micrometers as a curve in Mainsail/Fluidd
    (unit shown there: degrees C). Must be defined after [z_sense_offset]."""

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.callback = None
        self.sense = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def setup_minmax(self, min_temp, max_temp):
        pass

    def setup_callback(self, cb):
        self.callback = cb

    def get_report_time_delta(self):
        return 1.0

    def _handle_ready(self):
        self.sense = self.printer.lookup_object('z_sense_offset')
        self.reactor.register_timer(self._report, self.reactor.NOW)

    def _report(self, eventtime):
        if self.callback is not None and self.sense is not None:
            self.callback(eventtime, self.sense.z_offset * 1000.)
        return eventtime + 1.0


class SenseOffsetDisplay:
    def __init__(self, sense):
        self.sense = sense

    def get_status(self, eventtime):
        return {'force_g': round(self.sense.z_offset * 1000.)}


class SensingZOffset:
    def __init__(self, config):
        self.name = config.get_name()
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

        self.force_threshold = config.getint('force_threshold', minval=1)
        self.force_threshold_default = self.force_threshold
        self.max_z_offset = config.getfloat('max_z_offset', above=0.)
        self.max_z_offset_default = self.max_z_offset
        self.max_z_height = config.getfloat('max_z_height', 0.33, above=0.)
        self.n_average_force = config.getint('n_average_force', 10, minval=1)
        self.smoothing = config.getfloat('smoothing', 0.5, minval=0.,
            maxval=0.99)
        self.step_size = config.getfloat('step_size', 0.001, above=0.)
        self.relative_tolerance = config.getfloat('relative_tolerance', 0.1,
            above=0.)
        self.acuteness = config.getfloat('acuteness', 24., above=0.)
        self.max_steps_at_once = config.getfloat('max_steps_at_once', 48.,
            above=0.)
        # Meldung im Terminal, sobald der Offset um diesen Betrag gestiegen
        # ist (0 = keine Zwischenmeldungen, nur Obergrenze und Ergebnis)
        self.report_step = config.getfloat('report_step', 0.02, minval=0.)

        self.load_cell = self.printer.lookup_object('load_cell')
        self.load_cell.subscribe_force(self.force_callback)

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('Z_SENSE_OFFSET',
            self.Z_SENSE_OFFSET,
            desc=self.cmd_Z_SENSE_OFFSET_help)

        # Sensor type for a [temperature_sensor] curve in Mainsail
        pheaters = self.printer.load_object(config, 'heaters')
        pheaters.add_sensor_factory('z_sense_offset', SenseOffsetSensor)

        self.z_offset = 0.
        self.last_force = 0.
        self.smoothed_force = 0.
        self.averaged_force = 0.
        self.i_average = 0
        self.enable = False
        self._reset_stats()

        # Anzeige in Mainsail unter Sonstige (Objekttyp load_cell, Wert in
        # force_g, Einheit dort fest "g"): Offset in Mikrometer
        self.printer.add_object('load_cell Sense_Offset',
                                SenseOffsetDisplay(self))

        # Register transform
        self.gcode_move = self.printer.load_object(config, 'gcode_move')
        self.normal_transform = self.gcode_move.set_move_transform(self,
                                                                   force=True)

        # Reset z offset when homing (the offset must not survive into
        # the next print, e.g. into the hot Z probe)
        self.printer.register_event_handler("homing:home_rails_end",
                                            self._handle_home_rails_end)


    cmd_Z_SENSE_OFFSET_help = "Increase Z offset depending on measured " \
            "extrusion pressure (ENABLE=0 off, offset stays; QUERY=1 status)"

    def _reset_stats(self):
        self.reported_offset = 0.
        self.max_reported = False
        self.summary_done = False
        self.n_samples = 0
        self.n_over = 0
        self.force_sum = 0.
        self.force_max = 0.

    def _respond(self, msg):
        self.gcode.respond_info(msg, log=True)

    def _status_text(self):
        txt = "%.3f mm (max %.3f), Schwelle %d" % (self.z_offset,
            self.max_z_offset, self.force_threshold)
        if self.n_samples:
            txt += ", Kraft max %d / Mittel %d, ueber Schwelle %d von %d" % (
                self.force_max, self.force_sum / self.n_samples,
                self.n_over, self.n_samples)
        return txt

    def Z_SENSE_OFFSET(self, gcmd):
        if gcmd.get_int("QUERY", 0, minval=0, maxval=1):
            gcmd.respond_info("Sense Offset %s: %s" % (
                "an" if self.enable else "aus", self._status_text()))
            return
        if not gcmd.get_int("ENABLE", 1, minval=0, maxval=1):
            self.enable = False
            gcmd.respond_info("Sense Offset aus, Offset bleibt %.3f mm"
                              % (self.z_offset,))
            return
        self.max_z_offset = gcmd.get_float("MAX_Z_OFFSET",
            self.max_z_offset_default, minval=0.)
        self.force_threshold = gcmd.get_int("FORCE_THRESHOLD",
            self.force_threshold_default, minval=1)
        self.z_offset = 0.
        self.last_force = 0.
        self.smoothed_force = 0.
        self.averaged_force = 0.
        self.i_average = 0
        self._reset_stats()
        self.enable = True
        gcmd.respond_info("Sense Offset an: Schwelle %d, max %.3f mm bis "
                          "Z %.2f" % (self.force_threshold, self.max_z_offset,
                                      self.max_z_height))

    def _handle_ready(self):
        self.tool = self.printer.lookup_object('toolhead')
        self.enable = False

    def _handle_home_rails_end(self, homing_state, rails):
        self.enable = False
        self.z_offset = 0.

    def get_status(self, eventtime):
        return {
            'enabled': self.enable,
            'z_offset': self.z_offset,
            'force': self.smoothed_force,
            'force_threshold': self.force_threshold,
            'max_z_offset': self.max_z_offset,
            'max_z_height': self.max_z_height,
        }

    def get_position(self):
        x, y, z, e = self.normal_transform.get_position()
        return [x, y, z-self.z_offset, e]

    def move(self, newpos, speed):
        x, y, z, e = newpos
        self.normal_transform.move([x, y, z+self.z_offset, e], speed)

    def force_callback(self, force) :
        # check if enabled
        if not self.enable or self.max_z_offset <= 0. :
          return

        # check if still in first layer: G-Code Z (as in the slicer), without
        # bed mesh, gcode offset and this offset
        gm = self.gcode_move
        if gm.last_position[2] - gm.base_position[2] > self.max_z_height:
          if self.n_samples and not self.summary_done:
            self.summary_done = True
            self._respond("Sense Offset Ergebnis erster Layer: "
                          + self._status_text())
          return

        # perform averaging with some smoothing
        self.averaged_force += force
        self.i_average += 1
        if self.i_average < self.n_average_force :
          return
        smoothed_force = abs(self.averaged_force)/self.n_average_force
        self.averaged_force *= self.smoothing
        self.i_average *= self.smoothing
        self.smoothed_force = smoothed_force
        self.n_samples += 1
        self.force_sum += smoothed_force
        self.force_max = max(self.force_max, smoothed_force)
        if smoothed_force >= self.force_threshold:
          self.n_over += 1

        # no action required if below threshold
        if smoothed_force < self.force_threshold:
          self.last_force = smoothed_force
          return

        # check of extra tolerance is also exceeded
        exceed_tolerance = False
        if smoothed_force > self.force_threshold*(1+self.relative_tolerance) :
          exceed_tolerance = True

        # determine number of steps (of size self.step_size) to be done
        # start with default of 1
        n_steps = 1

        if exceed_tolerance and smoothed_force >= self.last_force:
          # larger and increasing deviations require faster action
          ratio = smoothed_force / self.force_threshold - 1
          n_steps += min(ratio * self.acuteness, self.max_steps_at_once)

          # the more offset we have already applied, the slower the additional
          # offset needs to be applied (to prevent overshooting)
          ratio = self.z_offset / self.max_z_offset
          n_steps -= (n_steps-1)*ratio

        if not exceed_tolerance and smoothed_force < self.last_force:
          # small and decreasing devation does not require any action
          n_steps = 0

        # remember force for the trend check of the next sample
        self.last_force = smoothed_force

        # apply offset
        self.z_offset = min(self.z_offset + n_steps*self.step_size,
            self.max_z_offset)

        logging.info("z_sense_offset: force=%d n_steps=%.1f z_offset=%.3f"
                     % (smoothed_force, n_steps, self.z_offset))

        if self.z_offset >= self.max_z_offset and not self.max_reported:
          self.max_reported = True
          self.reported_offset = self.z_offset
          self._respond("Sense Offset: Obergrenze %.3f mm erreicht "
                        "(Kraft %d, Schwelle %d)" % (self.z_offset,
                        smoothed_force, self.force_threshold))
        elif (self.report_step > 0. and self.z_offset
              >= self.reported_offset + self.report_step):
          self.reported_offset = self.z_offset
          self._respond("Sense Offset: %.3f mm (Kraft %d, Schwelle %d)"
                        % (self.z_offset, smoothed_force,
                           self.force_threshold))


def load_config(config):
    return SensingZOffset(config)

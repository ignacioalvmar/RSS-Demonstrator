#!/usr/bin/env python

# wheel handling
#

import evdev
import os
import sys
from threading import Lock
from enum import Enum
import math
import time
try:
    import pygame
    from pygame.locals import KMOD_CTRL
    from pygame.locals import KMOD_SHIFT
    from pygame.locals import K_0
    from pygame.locals import K_9
    from pygame.locals import K_BACKQUOTE
    from pygame.locals import K_BACKSPACE
    from pygame.locals import K_COMMA
    from pygame.locals import K_DOWN
    from pygame.locals import K_ESCAPE
    from pygame.locals import K_F1
    from pygame.locals import K_F2
    from pygame.locals import K_F3
    from pygame.locals import K_F4
    from pygame.locals import K_F5
    from pygame.locals import K_F6
    from pygame.locals import K_F7
    from pygame.locals import K_F8
    from pygame.locals import K_F9
    from pygame.locals import K_LEFT
    from pygame.locals import K_PERIOD
    from pygame.locals import K_RIGHT
    from pygame.locals import K_SLASH
    from pygame.locals import K_SPACE
    from pygame.locals import K_TAB
    from pygame.locals import K_UP
    from pygame.locals import K_a
    from pygame.locals import K_c
    from pygame.locals import K_d
    from pygame.locals import K_h
    from pygame.locals import K_l
    from pygame.locals import K_m
    from pygame.locals import K_p
    from pygame.locals import K_q
    from pygame.locals import K_r
    from pygame.locals import K_s
    from pygame.locals import K_w
    from pygame.locals import K_u
    from pygame.locals import K_i
    from pygame.locals import K_f
    from pygame.locals import K_RETURN
    from pygame.locals import MOUSEMOTION
    from pygame.locals import MOUSEBUTTONDOWN
    from pygame.locals import MOUSEBUTTONUP

except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')

import carla
try:
  from carla import ad
except:
  pass


class SteeringWheelInitState(Enum):
    START = 1
    TOGGLE = 2
    LEFT = 3
    RIGHT = 4

class SteeringWheelMode(Enum):
    CONSTANT_FORCE = 1
    VIBRATING = 3
    NO_FORCE = 4


class WheelControl(object):

    MOUSE_STEERING_RANGE=200
    HIDRAW_DEVICE="logitech_raw"

    def __init__(self, world, start_in_autopilot, scenario_runner, use_rss, use_wheel, notification_fct):

        self._max_lat_accel_left = None
        self._max_lat_accel_right = None
        self._use_rss = use_rss
        self._world = world
        self._autopilot_enabled = start_in_autopilot
        self._scenario_runner = scenario_runner
        self._notification_fct = notification_fct
        self._mouse_steering_center = None

        self._light_state = None
        # device = "/dev/input/by-id/usb-Logitech_G29_Driving_Force_Racing_Wheel-event-joystick"
        # #print(device)
        # self.evdev = None
        # try:
        #     self.evdev = evdev.InputDevice(device)
        #     print("Successfully initialized event device.")
        # except OSError as e:
        #     print("Failed to initialize event device {}.".format(e))
        #     self.evdev = None

        self._surface = pygame.Surface((self.MOUSE_STEERING_RANGE * 2, self.MOUSE_STEERING_RANGE * 2))
        self._surface.set_colorkey(pygame.Color('black'))
        self._surface.set_alpha(60)

        line_width = 2
        pygame.draw.polygon(self._surface,
            (0, 0, 255),
            [
                (0,0),
                (0,self.MOUSE_STEERING_RANGE * 2 - line_width),
                (self.MOUSE_STEERING_RANGE * 2 - line_width,self.MOUSE_STEERING_RANGE * 2 - line_width),
                (self.MOUSE_STEERING_RANGE * 2 - line_width, 0),
                (0,0)
            ], line_width)
        pygame.draw.polygon(self._surface,
            (0, 0, 255),
            [
                (0,self.MOUSE_STEERING_RANGE),
                (self.MOUSE_STEERING_RANGE * 2,self.MOUSE_STEERING_RANGE)
            ], line_width)
        pygame.draw.polygon(self._surface,
            (0, 0, 255),
            [
                (self.MOUSE_STEERING_RANGE, 0),
                (self.MOUSE_STEERING_RANGE, self.MOUSE_STEERING_RANGE * 2)
            ], line_width)

        self.raw_dev = None
        if use_wheel:
            try:
                self.raw_dev = os.open("/dev/{}".format(WheelControl.HIDRAW_DEVICE), os.O_RDWR)
                print("Successfully initialized raw device.")
            except OSError as e:
                print("Failed to initialize raw device {}. Steering wheel support disabled.".format(e))
                self.raw_dev = None
        self._steering_wheel_write_lock = Lock()
        self._steering_wheel_auto_center_active = True
        self._steering_wheel_leds_active = True

        self._control = carla.VehicleControl()
        if self._use_rss:
            self._restrictor = carla.RssRestrictor()
        else:
            self._restrictor = None
        world.player.set_autopilot(self._autopilot_enabled)
        self._last_lat_restriction_ms = 0
        self._fade_in_time = 500.0
        self._steer_cache = 0.0
        self._speed_limit = 30
        self._current_speed = 0
        #self._current_frame = 0
        self.vehicle_physics = world.player.get_physics_control()
        self._steering_wheel_first_steer_value_received = False
        self._steering_wheel_first_brake_value_received = False
        self._steering_wheel_first_throttle_value_received = False
        self._steering_wheel_init_state = SteeringWheelInitState.START
        self._steering_wheel_init_lock = Lock()
        self._steering_wheel_state = SteeringWheelMode.NO_FORCE
        self._steering_wheel_constant_force = 0 # used to not send similar values to the hid-device on every tick

        # initialize steering wheel
        self._joystick = None
        if use_wheel:
            pygame.joystick.init()

            joystick_count = pygame.joystick.get_count()
            if joystick_count > 1:
                raise ValueError("Please Connect Just One Joystick")

            try:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
            except pygame.error:
                self._joystick = None

        self._steer_idx = 0
        self._throttle_idx = 2
        self._brake_idx = 3
        self._reverse_idx = 5
        self._handbrake_idx = 4
        self._evasive_active = False

        self.restart()




    def set_max_lateral_accel(self, left, right):
        self._max_lat_accel_left = left
        self._max_lat_accel_right = right


    def set_range(self, range):
        '''
        Set wheel range
        '''
        if not self.raw_dev:
            return
        self._steering_wheel_write_lock.acquire(True)
        print("Set steering wheel range to {}".format(range))
        range1 = range & 0x00ff
        range2 = (range & 0xff00) >> 8
        os.write(self.raw_dev,bytearray([0xf8, 0x81, range1, range2, 0x00, 0x00, 0x00]))
        self._steering_wheel_write_lock.release()

    def set_leds(self, enable):
        '''
        Set steering wheel leds
        '''
        if not self.raw_dev:
            return
        if self._steering_wheel_leds_active != enable:
            self._steering_wheel_write_lock.acquire(True)
            if enable:
                os.write(self.raw_dev,bytearray([0xf8, 0x12, 0x1f, 0x00, 0x00, 0x00, 0x00]))
            else:
                os.write(self.raw_dev,bytearray([0xf8, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]))
            self._steering_wheel_leds_active = enable
            self._steering_wheel_write_lock.release()

    def restart(self):
        if not self._joystick:
            return
        self.reset_wheel()
        self.disable_force()
        self._steering_wheel_init_state = SteeringWheelInitState.START
        self._initialize_steering_wheel = True
        self.set_range(360)
        self.steering_wheel_auto_center(False)
        self.set_leds(False)

    def update_wheel_position(self):
        steering_wheel_position = self._joystick.get_axis(self._steer_idx)
        #print("New Wheel Position {}".format(steering_wheel_position))
        if self._initialize_steering_wheel:
            print("Initializing steering wheel... {}".format(self._steering_wheel_init_state))
            if self._steering_wheel_init_lock.acquire(False):
                if self._steering_wheel_init_state == SteeringWheelInitState.START:
                    print("INIT START")
                    self.steer_left(0.2)
                    time.sleep(0.3)
                    self.steer_right(0.2)
                    time.sleep(0.3)
                    self._steering_wheel_init_state = SteeringWheelInitState.LEFT
                elif self._steering_wheel_init_state == SteeringWheelInitState.LEFT:
                    print("INIT LEFT")
                    if steering_wheel_position > -0.8:
                        print("STEER LEFT")
                        self.steer_left(1)
                    else:
                        print("STEER RIGHT FAST")
                        self.steer_right(0.5)
                        self._steering_wheel_init_state = SteeringWheelInitState.RIGHT
                elif self._steering_wheel_init_state == SteeringWheelInitState.RIGHT:
                    print("INIT RIGHT")
                    if steering_wheel_position > -0.5 and abs(steering_wheel_position) > 0.02:
                        print("STEER RIGHT SLOW")
                        self.steer_right(0.2)
                    elif abs(steering_wheel_position) < 0.02:
                        print("Initializing steering wheel finished.")
                        self.disable_force()
                        self.steering_wheel_auto_center(True)
                        self._initialize_steering_wheel = False
                        self.steering_wheel_friction(2)

                self._steering_wheel_init_lock.release()
                return

        target_value = 0
        force = 0

        if self._autopilot_enabled:
            target_value = self._world.player.get_control().steer
            initial_force_level = 0.2 # for autopilot as low as possible
            #print("New Wheel Position {} (expected {})".format(steering_wheel_position, target_value))
            #max distance is 2, therefore divide by 2
            #to move the steering wheel at all, add some initial value
            force = (abs(steering_wheel_position - target_value)/2) + initial_force_level
        else:
            if not self._world.restrict_lateral_active:
                self.disable_force()
                return
            target_value = self._world.restricted_vehicle_control.steer
            initial_force_level = 0.2
            force_multiplier = 1.5

            #print("New Wheel Position {} (expected {})".format(steering_wheel_position, target_value))
            #max distance is 2, therefore divide by 2
            #to move the steering wheel at all, add some initial value
            force = ((abs(steering_wheel_position - target_value)/2) + initial_force_level) * force_multiplier

        lateral_force = True
        if abs(target_value - steering_wheel_position) < 0.02: # 0.01 to have a small region where no force is added
            self.disable_force()
            lateral_force = False
        elif target_value > steering_wheel_position:
            # print("Force right: {}".format(force))
            self.steer_right(force)
        elif steering_wheel_position > target_value:
            # print("Force left: {}".format(force))
            self.steer_left(force)


    def parse_events(self, world, clock):
        for event in pygame.event.get():
            #print("Unknown key: {}".format(event))
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.JOYHATMOTION:
                if event.hat == 0:
                    #if event.value[1] == 1:
                    #    self._world.toggle_traffic_participants()
                    #if event.value[0] == -1:
                    #    world.restart()
                    #if event.value[0] == 1:
                    #    world.restart(True)
                    if event.value[1] == -1:
                        if world.rss_sensor:
                            if world.rss_sensor.sensor.road_boundaries_mode == carla.RoadBoundariesMode.Off:
                                world.rss_sensor.sensor.road_boundaries_mode = carla.RoadBoundariesMode.On
                                self._notification_fct('RSS Road Boundaries Mode set to On')
                            else:
                                world.rss_sensor.sensor.road_boundaries_mode = carla.RoadBoundariesMode.Off
                                self._notification_fct('RSS Road Boundaries Mode set to Off')
            elif event.type == pygame.JOYAXISMOTION:
                if event.axis == 0:
                    self._steering_wheel_first_steer_value_received = True
                if event.axis == self._brake_idx:
                    self._steering_wheel_first_brake_value_received = True
                elif event.axis == self._throttle_idx:
                    self._steering_wheel_first_throttle_value_received = True
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    #maps to multiple buttons on steering wheel
                    world.red_button_pressed()
                    pass
                elif event.button == 1:
                    world.toggle_hud_info()
                elif event.button == 2:
                    pass
                elif event.button == 3:
                    world.next_weather()
                elif event.button == 6:
                    pass
                elif event.button == 7:
                    world.toggle_help()
                elif event.button == 8:
                    self._autopilot_enabled = not self._autopilot_enabled
                    world.player.set_autopilot(self._autopilot_enabled)
                    self._notification_fct('Autopilot %s' % ('On' if self._autopilot_enabled else 'Off'))
#                elif event.button == 9:
#                    if self._speed_limit == 30:
#                        self._notification_fct('Speed limit disabled')
#                        self._speed_limit = 100
#                    else:
#                        self._notification_fct('Speed limit set to 30 km/h')
#                        self._speed_limit = 30
                elif event.button == 10:
                    pass
                elif event.button == 11:
                    self._world.toggle_rss_restrict()
                elif event.button == 4 or event.button == 5:
                    self._control.gear = 1 if self._control.reverse else -1
                elif event.button == 23:
                    world.camera_manager.next_sensor()

            elif event.type == pygame.KEYUP:
                if self._is_quit_shortcut(event.key):
                    return True
                elif event.key == K_RETURN:
                    world.red_button_pressed()
                elif event.key == K_BACKSPACE:
                    world.restart()
                elif event.key == K_F1:
                    world.toggle_hud_info()
                elif event.key == K_F2:
                    if world and world.rss_sensor:
                        world.rss_sensor.toggle_debug_visualization_mode()
                elif event.key == K_F3:
                    if world and world.rss_sensor:
                        world.rss_sensor.decrease_log_level()
                        world.rss_sensor.decrease_map_log_level()
                        self._restrictor.set_log_level(self._world.rss_sensor.log_level)
                elif event.key == K_F4:
                    if world and world.rss_sensor:
                        world.rss_sensor.increase_log_level()
                        world.rss_sensor.increase_map_log_level()
                        self._restrictor.set_log_level(self._world.rss_sensor.log_level)
                elif event.key == K_F5:
                    world.restart("CARLADemo.xosc")
                elif event.key == K_F6:
                    world.restart("scenarios/F6.xosc")
                elif event.key == K_F7:
                    world.restart("scenarios/F7.xosc")
                elif event.key == K_F8:
                    world.restart("scenarios/F8.xosc")
                elif event.key == K_F9:
                    world.restart("scenarios/F9.xosc")
                elif event.key == K_u:
                    world.position_ego_on_next_waypoint()
                elif event.key == K_i:
                    world.toggle_pause()
                elif event.key == K_h or (event.key == K_SLASH and pygame.key.get_mods() & KMOD_SHIFT):
                    world.toggle_help()
                elif event.key == K_TAB:
                    world.camera_manager.toggle_camera()
                elif event.key == K_c and pygame.key.get_mods() & KMOD_SHIFT:
                    world.next_weather(reverse=True)
                elif event.key == K_c:
                    world.next_weather()
                elif event.key == K_BACKQUOTE:
                    world.camera_manager.next_sensor()
                elif event.key > K_0 and event.key <= K_9:
                    world.camera_manager.set_sensor(event.key - 1 - K_0)
                elif event.key == K_r:
                    world.toggle_rss_restrict()
                elif event.key == K_q:
                    self._control.gear = 1 if self._control.reverse else -1
                elif event.key == K_m:
                    self._control.manual_gear_shift = not self._control.manual_gear_shift
                    self._control.gear = world.player.get_control().gear
                    self._notification_fct('%s Transmission' %
                                           ('Manual' if self._control.manual_gear_shift else 'Automatic'))
                elif self._control.manual_gear_shift and event.key == K_COMMA:
                    self._control.gear = max(-1, self._control.gear - 1)
                elif self._control.manual_gear_shift and event.key == K_PERIOD:
                    self._control.gear = self._control.gear + 1
                elif event.key == K_p:
                    self._autopilot_enabled = not self._autopilot_enabled
                    world.player.set_autopilot(self._autopilot_enabled)
                    self._notification_fct('Autopilot %s' % ('On' if self._autopilot_enabled else 'Off'))
                elif event.key == K_f:
                    pygame.display.toggle_fullscreen()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                #store current mouse position for mouse-steering
                if event.button == 1:
                    self._mouse_steering_center = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self._mouse_steering_center = None

        if not self._autopilot_enabled:
            if self._joystick:
                self._parse_vehicle_wheel()
            self._parse_vehicle_keys(pygame.key.get_pressed(), clock.get_time())
            if pygame.mouse.get_pressed()[0]:
                self._parse_mouse(pygame.mouse.get_pos())
            self._control.reverse = self._control.gear < 0

            #limit speed to 30kmh
            v = world.player.get_velocity()
            self._world.throttle_input = self._control.throttle # used for display
            self._world.speed_limit = self._speed_limit

            self._current_speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
            if self._current_speed >= self._speed_limit:
                self._control.throttle = 0

            if self._restrictor:
                proper_response = self._world.rss_sensor.proper_response if self._world.rss_sensor and self._world.rss_sensor.response_valid else None
                if proper_response:
                    rss_ego_dynamics_on_route = self._world.rss_sensor.ego_dynamics_on_route

                    if not (pygame.key.get_mods() & KMOD_CTRL) and self._world.rss_restrict:
                        proper_response = self.add_evasive_maneuver_to_response(proper_response)

                        self._world.restricted_vehicle_control = self._restrictor.restrict_vehicle_control(self._control, proper_response, rss_ego_dynamics_on_route, self.vehicle_physics)

                        current_time = pygame.time.get_ticks()

                        #set leds if restrict is active
                        restrict_active = not self._world.restricted_vehicle_control == self._control
                        restrict_longitudinal_active = False
                        restrict_lateral_active = False
                        if not restrict_active:
                            self._world.restricted_vehicle_control = None
                            self._world.restrict_longitudinal_active = False
                            self._world.restrict_lateral_active = False
                            #fade in steering
                            self._control.steer = min(1.0, (current_time - self._last_lat_restriction_ms) / self._fade_in_time) * self._control.steer
                        else:
                            prev_lon_active = self._world.restrict_longitudinal_active
                            restrict_longitudinal_active = (self._control.brake != self._world.restricted_vehicle_control.brake or self._control.throttle != self._world.restricted_vehicle_control.throttle)
                            if not prev_lon_active and restrict_longitudinal_active:
                                self.steering_wheel_vibrate()
                                #self.steering_wheel_vibrate_on()

                            restrict_lateral_active = self._control.steer != self._world.restricted_vehicle_control.steer
                            if restrict_lateral_active:
                                self._last_lat_restriction_ms = current_time
                                self._control.steer = self._world.restricted_vehicle_control.steer
                            else:
                                #fade in steering
                                self._control.steer = min(1.0, (current_time - self._last_lat_restriction_ms) / self._fade_in_time) *  self._world.restricted_vehicle_control.steer
                            self._control.brake = self._world.restricted_vehicle_control.brake
                            self._control.throttle = self._world.restricted_vehicle_control.throttle
                            self._steer_cache = self._world.restricted_vehicle_control.steer

                        #if not restrict_longitudinal_active:
                        #    self.steering_wheel_vibrate_off()

                        self._world.update_rss_restricts(restrict_lateral_active, restrict_longitudinal_active)
                        self.set_leds(restrict_active)
                    else:
                        self._world.restricted_vehicle_control = None
                        self._notification_fct("RSS temporary Inactive!")

                    #world.hud.restricted_vehicle_control = self._control
        if not world.move_player_target_transform:
            # control only active if not moving vehicle
            if self._light_state == None:
                self._light_state = world.player.get_light_state()

            if not self._light_state:
                brake_light_active = False
            else:
                brake_light_active = (self._light_state | carla.VehicleLightState.Brake) == carla.VehicleLightState.Brake

            if self._control.brake > 0 and not brake_light_active:
                self._light_state = carla.VehicleLightState(self._light_state | carla.VehicleLightState.Brake)
                world.player.set_light_state(carla.VehicleLightState(self._light_state))
            elif self._control.brake <= 0 and brake_light_active:
                self._light_state = carla.VehicleLightState(self._light_state & ~carla.VehicleLightState.Brake)
                world.player.set_light_state(carla.VehicleLightState(self._light_state))
            world.player.apply_control(self._control)
        if self._joystick:
            self.update_wheel_position()

    def set_evasive(self, active):
        self._evasive_active = active

    def add_evasive_maneuver_to_response(self, proper_response):
        if self._evasive_active and ( proper_response.accelerationRestrictions.longitudinalRange.maximum > 0. ):
            is_dangerous = False
            for state in self._world.rss_sensor.individual_rss_states:
                if state.is_dangerous:
                    is_dangerous = True
                    brake_dist_brake_min = ad.physics.Distance()
                    response_time = ad.physics.Duration(0.3)
                    ad.rss.situation.calculateLongitudinalDistanceOffsetAfterStatedBrakingPattern(
                        self._current_speed/3.6,
                        self._speed_limit/3.6,
                        response_time,
                        self._world.rss_sensor.current_vehicle_parameters.alphaLon.accelMax,
                        self._world.rss_sensor.current_vehicle_parameters.alphaLon.brakeMin,
                        brake_dist_brake_min)
                    # rss state provides distance of center points, so we have to subtract a complete vehicle length
                    distance_to_other = state.distance - 0.5 * float(state.ego_state.dimension.length + state.object_state.dimension.length)
                    # print("Dangerous {}, but no response, d={}, d_b_max={}".format(state.rss_state.objectId, distance_to_other, brake_dist_brake_min))
                    if brake_dist_brake_min >= distance_to_other:
                        print("EVASIVE brake")
                        proper_response.accelerationRestrictions.longitudinalRange.maximum = self._world.rss_sensor.current_vehicle_parameters.alphaLon.brakeMin
        return proper_response


    def steering_wheel_vibrate(self):
        if not self.raw_dev:
            return

        #vibrate uses slot F1
        force_altitude = 32
        with self._steering_wheel_write_lock:
            os.write(self.raw_dev,bytearray([0x21, 0x06, 128 + force_altitude, 128 - force_altitude, 8, 8, 0x0f]))
            time.sleep(0.05)
            os.write(self.raw_dev,bytearray([0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))

    def steering_wheel_vibrate_on(self):
        if not self.raw_dev:
            return

        #vibrate uses slot F1
        force_altitude = 32
        with self._steering_wheel_write_lock:
            os.write(self.raw_dev,bytearray([0x21, 0x06, 128 + force_altitude, 128 - force_altitude, 8, 8, 0x0f]))

    def steering_wheel_vibrate_off(self):
        if not self.raw_dev:
            return

        #vibrate uses slot F1
        with self._steering_wheel_write_lock:
            os.write(self.raw_dev,bytearray([0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))

    def _parse_vehicle_keys(self, keys, milliseconds):
        steer_increment = 5e-4 * milliseconds
        if keys[K_LEFT] or keys[K_a]:
            self._steer_cache -= steer_increment
        elif keys[K_RIGHT] or keys[K_d]:
            self._steer_cache += steer_increment
        else:
            self._steer_cache = 0.0
        self._steer_cache = min(0.7, max(-0.7, self._steer_cache))
        if not self._joystick:
            self._control.throttle = 1.0 if keys[K_UP] or keys[K_w] else 0.0
            self._control.steer = round(self._steer_cache, 1)
            self._control.brake = 1.0 if keys[K_DOWN] or keys[K_s] else 0.0
            self._control.hand_brake = keys[K_SPACE]
        else:
            if keys[K_UP] or keys[K_w]:
                self._control.throttle = 1.0 if keys[K_UP] or keys[K_w] else 0.0
            if keys[K_LEFT] or keys[K_a] or keys[K_RIGHT] or keys[K_d]:
                self._control.steer = round(self._steer_cache, 1)
            if keys[K_DOWN] or keys[K_s]:
                self._control.brake = 1.0 if keys[K_DOWN] or keys[K_s] else 0.0
            if keys[K_SPACE]:
                self._control.hand_brake = keys[K_SPACE]

    def _parse_vehicle_wheel(self):
        numAxes = self._joystick.get_numaxes()
        jsInputs = [float(self._joystick.get_axis(i)) for i in range(numAxes)]
        # print (jsInputs)
        jsButtons = [float(self._joystick.get_button(i)) for i in
                     range(self._joystick.get_numbuttons())]
        # Custom function to map range of inputs [1, -1] to outputs [0, 1] i.e 1 from inputs means nothing is pressed
        # For the steering, it seems fine as it is
        K1 = 0.4#0.5#1.0  # 0.55
        steerCmd = K1 * math.tan(1.1 * jsInputs[self._steer_idx]) #jsInputs[self._steer_idx]
        #steerCmd = jsInputs[self._steer_idx]

        throttleCmd = 0
        if self._steering_wheel_first_throttle_value_received:
            K2 = 1.6  # 1.6
            throttleCmd = K2 + (2.05 * math.log10(
                -0.7 * jsInputs[self._throttle_idx] + 1.4) - 1.2) / 0.92
            if throttleCmd <= 0:
                throttleCmd = 0
            elif throttleCmd > 1:
                throttleCmd = 1

        brakeCmd = 0
        if self._steering_wheel_first_brake_value_received:
            brakeCmd = 1.6 + (2.05 * math.log10(
                -0.7 * jsInputs[self._brake_idx] + 1.4) - 1.2) / 0.92
            if brakeCmd <= 0:
                brakeCmd = 0
            elif brakeCmd > 1:
                brakeCmd = 1

        self._control.steer = steerCmd
        self._control.brake = brakeCmd
        self._control.throttle = throttleCmd

        #toggle = jsButtons[self._reverse_idx]

        self._control.hand_brake = bool(jsButtons[self._handbrake_idx])

    def _parse_mouse(self, pos):
        if not self._mouse_steering_center:
            return

        lateral = float(pos[0] - self._mouse_steering_center[0])
        longitudinal = float(pos[1] - self._mouse_steering_center[1])
        max_val = self.MOUSE_STEERING_RANGE
        lateral = -max_val if lateral < -max_val else max_val if lateral > max_val else lateral
        longitudinal = -max_val if longitudinal < -max_val else max_val if longitudinal > max_val else longitudinal
        self._control.steer = lateral/max_val
        if longitudinal < 0.0:
            self._control.throttle = -longitudinal / max_val
            self._control.brake = 0.0
        elif longitudinal > 0.0:
            self._control.throttle = 0.0
            self._control.brake = longitudinal / max_val

    @staticmethod
    def _is_quit_shortcut(key):
        return (key == K_q and pygame.key.get_mods() & KMOD_CTRL)

    def disable_force(self):
        if not self.raw_dev:
            return

        #force uses slot F0
        with self._steering_wheel_write_lock:
            if not self._steering_wheel_constant_force == 0 or not self._steering_wheel_state == SteeringWheelMode.NO_FORCE:
                #print("  disable force")
                os.write(self.raw_dev,bytearray([0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
                self._steering_wheel_constant_force = 0
                self._steering_wheel_state = SteeringWheelMode.NO_FORCE

    def set_force(self, val):
        if not self.raw_dev:
            return

        #force uses slot F0
        if val == 0.5:
            self.disable_force()
            return
        new_value = int(round(abs(val - 1) * 255))
        with self._steering_wheel_write_lock:
            if not self._steering_wheel_state == SteeringWheelMode.CONSTANT_FORCE or not self._steering_wheel_constant_force == new_value:
                self._steering_wheel_constant_force = new_value
                os.write(self.raw_dev,bytearray([0x11, 0x00, self._steering_wheel_constant_force, 0x00, 0x00, 0x00, 0x00]))
                self._steering_wheel_state = SteeringWheelMode.CONSTANT_FORCE

    def steer_left(self, force):
        # force 0..1
        value = 0.5 - (0.5 * force)
        if value < 0:
            value = 0
        #print("   <-- (force: {})".format(value))
        self.set_force(value)

    def steer_right(self, force):
        # force 0..1
        value = 0.5 + (0.5 * force)
        if value > 1:
            value = 1
        #print("   --> (force: {})".format(value))
        self.set_force(value)

    def steering_wheel_auto_center(self, enable):
        '''
        Set wheel autocenter
        '''
        if not self.raw_dev:
            return
        if not self._steering_wheel_auto_center_active == enable:
            print("Set steering wheel autocenter to {}".format(enable))
            self._steering_wheel_write_lock.acquire(True)
            if enable:
                os.write(self.raw_dev,bytearray([0x3e, 0x00, 0x04, 0x04, 0x80, 0x00, 0x00]))
                os.write(self.raw_dev,bytearray([0x34, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
            else:
                os.write(self.raw_dev,bytearray([0x35, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
            self._steering_wheel_auto_center_active = enable
            self._steering_wheel_write_lock.release()

    def steering_wheel_friction(self, level):
        if not self.raw_dev:
            return

        #friction uses slot F2
        self._steering_wheel_write_lock.acquire(True)
        os.write(self.raw_dev,bytearray([0x41, 0x02, level, 0x00, level, 0x00, 0x00]))
        self._steering_wheel_write_lock.release()

    def reset_wheel(self):
        if not self.raw_dev:
            return

        self._steering_wheel_write_lock.acquire(True)
        os.write(self.raw_dev,bytearray([0xf1, 0x06, 0x80, 0x80, 0x08, 0x08, 0x0f]))
        os.write(self.raw_dev,bytearray([0xf3, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
        os.write(self.raw_dev,bytearray([0xf0, 0x00, 0x80, 0x80, 0x80, 0x80, 0x00]))
        self._steering_wheel_write_lock.release()

    def render(self, display):
        if self._mouse_steering_center:
            display.blit(self._surface, (self._mouse_steering_center[0] - self.MOUSE_STEERING_RANGE, self._mouse_steering_center[1] - self.MOUSE_STEERING_RANGE))

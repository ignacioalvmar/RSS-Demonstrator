#!/usr/bin/env python

# Copyright (c) 2019-2020 Intel Labs
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

# Allows controlling a vehicle with a keyboard. For a simpler and more
# documented example, please take a look at tutorial.py.

"""
Welcome to CARLA manual control with steering wheel Logitech G29.

To drive start by pushing the brake pedal.
Change your wheel_config.ini according to your steering wheel.

To find out the values of your steering wheel use jstest-gtk in Ubuntu.

"""

from __future__ import print_function


# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================

import glob
import os
import sys

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass


# ==============================================================================
# -- imports -------------------------------------------------------------------
# ==============================================================================


import carla

from carla import ColorConverter as cc
import argparse
import datetime
import inspect
import logging
import random
import re
import math
import weakref
from threading import Lock, Thread
try:
    import queue
except ImportError:
    import Queue as queue
import time
from enum import Enum
import copy

from lib.wheel_ctrl import WheelControl
import pygame
try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')

from lib.scenario_runner_runner import ScenarioRunnerRunner
from lib.location_event_handler import LocationEventHandler

from lib.rss_sensor import RssSensor
from lib.rss_visualization import RssUnstructuredSceneVisualizer, RssBoundingBoxVisualizer

from dialogs.navigation_dialog import NavigationDialog
from dialogs.overlay_dialog import OverlayDialog
from dialogs.finish_dialog import FinishDialog
from dialogs.rss_info_dialog import RssInfoDialog
from dialogs.welcome_dialog import WelcomeDialog
from dialogs.left_the_road_dialog import LeftTheRoadDialog
from dialogs.dashboard import Dashboard
from dialogs.notification import Notification
from dialogs.hud import HUD
from dialogs.rss_parameter_display import RssParameterDisplay
from dialogs.help import HelpText


global_client_timeout=10.

# ==============================================================================
# -- Global functions ----------------------------------------------------------
# ==============================================================================


def find_weather_presets():
    rgx = re.compile('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)')
    name = lambda x: ' '.join(m.group(0) for m in rgx.finditer(x))
    presets = [x for x in dir(carla.WeatherParameters) if re.match('[A-Z].+', x)]
    return [(getattr(carla.WeatherParameters, x), name(x)) for x in presets]


def get_actor_display_name(actor, truncate=250):
    name = ' '.join(actor.type_id.replace('_', '.').title().split('.')[1:])
    return (name[:truncate - 1] + u'\u2026') if len(name) > truncate else name

# ==============================================================================
# -- CollisionSensor -----------------------------------------------------------
# ==============================================================================

class CollisionSensor(object):
    def __init__(self, parent_actor, notification):
        self.sensor = None
        self.history = []
        self._parent = parent_actor
        self.notification = notification
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.collision')
        self.sensor = world.spawn_actor(bp, carla.Transform(), attach_to=self._parent)
        # We need to pass the lambda a weak reference to self to avoid circular
        # reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(lambda event: CollisionSensor._on_collision(weak_self, event))

    def get_collision_history(self):
        history = collections.defaultdict(int)
        for frame, intensity in self.history:
            history[frame] += intensity
        return history

    @staticmethod
    def _on_collision(weak_self, event):
        self = weak_self()
        if not self:
            return
        actor_type = get_actor_display_name(event.other_actor)
        text = "Collision with {}".format(actor_type)
        self.notification.set_notification(text)
        print(text)
        impulse = event.normal_impulse
        intensity = math.sqrt(impulse.x**2 + impulse.y**2 + impulse.z**2)
        self.history.append((event.frame, intensity))
        if len(self.history) > 4000:
            self.history.pop(0)

# ==============================================================================
# -- World ---------------------------------------------------------------------
# ==============================================================================

class World(object):

    def __init__(self, client, scenario_runner, overlay_dialog, display, scenario_file, enable_autopilot, use_rss, use_walkers, demo_mode, use_wheel):
        self.client = client
        self._wheel_ctrl = None
        self.world = client.get_world()
        self._map = self.world.get_map()
        self.location_event_handler = LocationEventHandler()
        self._paused = False
        self.vehicles = []
        self.rss_restrict_count = 0
        self.player = None
        self.move_player_target_transform = None
        self.restricted_vehicle_control = None
        self.restrict_longitudinal_active = False
        self.restrict_lateral_active = False
        self.speed_limit = 0
        self.throttle_input = 0
        self.rss_restrict = True
        self._use_rss = use_rss
        self._use_walkers = use_walkers
        self._demo_mode = demo_mode
        self.rss_sensor = None
        self.rss_sensor_log_level = carla.RssLogLevel.warn
        self.unstructured_scene_drawer = None
        self.camera_manager = None
        self._weather_presets = find_weather_presets()
        self._weather_index = 0
        self._traffic_participants_active = False
        self._traffic_participants = []
        self._walkers = []
        self._walker_ids = []
        self._scenario_runner = scenario_runner
        self._overlay_dialog = overlay_dialog
        self._display = display
        self._routing_targets_dict = dict()
        self.unstructured_scene_drawer = None

        self._logo = pygame.image.load("images/intellabs_logo_70.png")
        self._logo_pos = (20, self._display.get_height() - self._logo.get_height() - 20)

        self._help = HelpText(self._display.get_width(), self._display.get_height())
        self._hud = HUD(self._display.get_width(), self._display.get_height())
        self._notifications = Notification(self._display.get_width(), self._display.get_height())
        self._dashboard = Dashboard(self._display.get_width(), self._display.get_height())
        self._bounding_box_drawer = None

        # Scene: Change RSS Parameters
        self._rss_parameter_display = RssParameterDisplay(self._display.get_width(), self._display.get_height())

        if self._demo_mode:
            self._navigation_dialog = NavigationDialog()
            self._left_navigation_id = self._navigation_dialog.load_image("images/arrow_left2.png", (self._display.get_width()/2 - 162/2 - 57, 140))
            self._right_navigation_id = self._navigation_dialog.load_image("images/arrow_right2.png", (self._display.get_width()/2 - 162/2 + 57, 140))
            self._straight_navigation_id = self._navigation_dialog.load_image("images/arrow_straight2.png", (self._display.get_width()/2 - 82/2, 140))
            self.location_event_handler.register_event((349.5,117.4 + 2), 17.8 + 5, self._right_navigation_id, self.show_navigation)
            self.location_event_handler.register_event((108,131), 15, self._left_navigation_id, self.show_navigation)
            self.location_event_handler.register_event((91,178), 15, self._straight_navigation_id, self.show_navigation)
            self.location_event_handler.register_event((91,309), 17, self._left_navigation_id, self.show_navigation)
            self.location_event_handler.register_event((321.9,328.6), 15, self._left_navigation_id, self.show_navigation)
            #self.location_event_handler.register_event((214,130), 123 - 40, 0, self.change_speed_limit)
            #self.location_event_handler.register_event((214,328.6), 123 - 40, 0, self.change_speed_limit)
            #self.location_event_handler.register_event((91,229.8), 98.8 - 40, 0, self.change_speed_limit)

            self._left_the_road_dialog = LeftTheRoadDialog(self._display.get_width(), self._display.get_height())

            self._welcome_dialog = WelcomeDialog(self._display.get_width(), self._display.get_height())
            self.location_event_handler.register_event((336.9,70), 5, 1001, self.show_welcome_dialog)

            self._finish_dialog = FinishDialog(self._display.get_width(), self._display.get_height())
            self.location_event_handler.register_event((320,328), 20, 1002, self.show_finish_dialog)

            self._rss_info_dialog = RssInfoDialog(self._display.get_width(), self._display.get_height())
            self._rss_info_dialog_longitudinal = self._rss_info_dialog.load_content("images/longitudinal3.png", "RSS assures a longitudinal safe distance.", (20,140))
            self._rss_info_dialog_lateral = self._rss_info_dialog.load_content("images/lateral.png", "RSS assures a lateral safe distance.", (20,140))
            self._rss_info_dialog_right_of_way = self._rss_info_dialog.load_content("images/right_of_way2.png", "RSS assures that right of way is given, not taken.", (20,140))
            self._rss_info_dialog_pedestrians = self._rss_info_dialog.load_content("images/rss-unstructured.png", "RSS assures safety for Vulnerable Road Users.", (20,140))
            self._rss_info_dialog_parameters = self._rss_info_dialog.load_content("images/parameter_sets2.png", "RSS supports multiple driving profiles.", (20,140))
            #self._rss_info_dialog_assertive = self._rss_info_dialog.load_content("images/parameter_sets2.png", "RSS parameters set to 'assertive'.", (20,140))
            self.location_event_handler.register_event((311,129.7), 5, self._rss_info_dialog_longitudinal, self.show_rss_info_dialog)
            self.location_event_handler.register_event((245,129.7), 5, self._rss_info_dialog_lateral, self.show_rss_info_dialog)
            self.location_event_handler.register_event((85,154.5), 10, self._rss_info_dialog_right_of_way, self.show_rss_info_dialog)
            self.location_event_handler.register_event((124.9,331), 5, self._rss_info_dialog_pedestrians, self.show_rss_info_dialog)
            self.location_event_handler.register_event((170,331), 5, self._rss_info_dialog_parameters, self.show_rss_info_dialog)


            #self.location_event_handler.register_event((200,328.6), 5, self._rss_info_dialog_assertive, self.show_rss_info_dialog)


            # Scene: taking prio
            self.location_event_handler.register_event((70,195), 50, 1007, self.switch_to_taking_prio)

            # Scene: Change RSS Parameters
            self.location_event_handler.register_event((290,331), 50, 1003, self.switch_to_assertive_parameters)
            self.location_event_handler.register_event((290,331), 130.1, 1004, self.display_rss_parameter_set)

            # Scene: Pedestrian
            self.location_event_handler.register_event((250,331), 130.1, 1005, self.display_unstructured)

            #TODO: move route to openscenario
            self._routing_targets_dict = {
            "CARLADemo.xosc": [carla.Transform(carla.Location(x=88, y=175)), carla.Transform(carla.Location(x=108, y=331)), carla.Transform(carla.Location(x=339, y=245))],
            "scenarios/F6.xosc": [carla.Transform(carla.Location(x=88, y=175)), carla.Transform(carla.Location(x=108, y=331)), carla.Transform(carla.Location(x=339, y=245))],
            "scenarios/F7.xosc": [carla.Transform(carla.Location(x=108, y=331)), carla.Transform(carla.Location(x=339, y=245))],
            "scenarios/F8.xosc": [carla.Transform(carla.Location(x=339, y=245))],
            "scenarios/F9.xosc": [carla.Transform(carla.Location(x=339, y=245))]}

        # Scene: Change RSS Parameters
        self.switch_to_assertive_parameters(0, False)

        self.restart(scenario_file)
        self._wheel_ctrl = WheelControl(self, enable_autopilot, scenario_runner, use_rss, use_wheel, self._notifications.set_notification)
        #Spawn other participants?
        #self.toggle_traffic_participants()

    def red_button_pressed(self):
        if not self._demo_mode:
            return
        self.pause_simulation(False)

        if self._finish_dialog.is_enabled():
            self.restart("CARLADemo.xosc")

        if self._left_the_road_dialog.is_enabled():
            print("reenable physics, player at {}".format(self.player.get_location()))
            self.player.set_simulate_physics(True)
            self._left_the_road_dialog.disable()

        self._dashboard.enable()
        self._rss_info_dialog.disable()
        self._welcome_dialog.disable()

    # Scene: Pedestrian
    def display_unstructured(self, _, active):
        if not self.unstructured_scene_drawer:
            return
        if active:
            self.unstructured_scene_drawer.enable()
        else:
            self.unstructured_scene_drawer.disable()


    #Scene: Change RSS Parameters
    def display_rss_parameter_set(self, _, active):
        if active:
            self._rss_parameter_display.set_param_assertive(False, self.rss_sensor)
            self._rss_parameter_display.enable()
        else:
            self._rss_parameter_display.disable()

    def switch_to_assertive_parameters(self, event_id, active):
        if active:
            if self.rss_sensor:
                self.rss_sensor.set_assertive_parameters()
                self._rss_parameter_display.set_param_assertive(True, self.rss_sensor)
        else:
            if self.rss_sensor:
                self.rss_sensor.set_default_parameters()
                self._rss_parameter_display.set_param_assertive(False, self.rss_sensor)


    def switch_to_taking_prio(self, event_id, active):
        if self.rss_sensor:
            self.rss_sensor.set_mini_accel_lat(active)
        self._wheel_ctrl.set_evasive(active)


    def show_rss_info_dialog(self, event_id, active):
        if active:
            if self.rss_sensor:
                self.rss_sensor.set_default_parameters()
            self._dashboard.disable()
            self._rss_info_dialog.enable_id(event_id)
            # rerender to show dialog immediately
            self.render(self._display)
            pygame.display.flip()
            self.pause_simulation(True)
        else:
            self._dashboard.enable()
            self._rss_info_dialog.disable()

    def show_welcome_dialog(self, event_id, active):
        if active:
            self._dashboard.disable()
            self._welcome_dialog.enable()
            self.pause_simulation(True)
        else:
            self._dashboard.enable()
            self._welcome_dialog.disable()

    def show_finish_dialog(self, event_id, active):
        print("show finish dialog")
        if active:
            self._dashboard.disable()

            # Scene: Change RSS Parameters
            self._rss_parameter_display.disable()

            # Scene: Pedestrian
            self.unstructured_scene_drawer.disable()
            self._finish_dialog.set_rss_restrictions(str(self.rss_restrict_count))
            self._finish_dialog.enable()
            self.pause_simulation(True)
        else:
            self._dashboard.enable()
            self._finish_dialog.disable()

    def show_navigation(self, navigation_case, active):
        if active:
            self._navigation_dialog.enable(navigation_case)
        else:
            self._navigation_dialog.disable()

    def toggle_help(self):
        self._help.toggle()

    def toggle_hud_info(self):
        self._hud.toggle_info()

    # def change_speed_limit(self, event_id, active):
    #     if active:
    #         self._wheel_ctrl._speed_limit = 50
    #         self._notifications.set_notification("Max speed changed to 50 km/h")
    #     else:
    #         self._wheel_ctrl._speed_limit = 30
    #         self._notifications.set_notification("Max speed changed to 30 km/h")

    def toggle_rss_restrict(self):
        self.rss_restrict = not self.rss_restrict
        if self.rss_restrict is False:
            self._notifications.set_static_warning("RSS Inactive!")
        else:
            self._notifications.remove_static_warning()

    def start(self):
        self.world.on_tick(self.on_world_tick)

    def on_world_tick(self, world_snapshot):
        self._hud.on_world_tick(world_snapshot)

        if self._demo_mode:
            #check distance between vehicle and next waypoint.
            #if it gets too big, trigger repositioning
            #TODO: do not place into wrong direction!
            if self.player and self.world:
                try:
                    if self.move_player_target_transform:
                        if self.player.get_location().distance(self.move_player_target_transform.location) < 1.:
                            print("player {} actually moved back on to the road {}".format(self.player.get_location(), self.move_player_target_transform))
                            self.move_player_target_transform = None
                        if self.move_player_target_transform:
                            print("waiting for player {} actually be moved back on to the road {}".format(self.player.get_location(), self.move_player_target_transform))
                    else:
                        wp = self._map.get_waypoint(self.player.get_location())
                        if self.player.get_location().distance(wp.transform.location) > 2.5:
                            self._dashboard.disable()
                            self._left_the_road_dialog.enable()
                            print("move player from {} back on to the road {}".format(self.player.get_location(), wp.transform))
                            self.move_player_target_transform = wp.transform
                            self.player.set_simulate_physics(False)
                            self.player.set_transform(self.move_player_target_transform)
                            control = carla.VehicleControl()
                            control.brake = 1
                            control.throttle = 0
                            self.player.apply_control(control)
                            self.pause_simulation(True)
                except RuntimeError:
                    pass

    def toggle_pause(self):
        print("Toggle PAUSE")
        settings = self.world.get_settings()
        self.pause_simulation(not settings.synchronous_mode)

    def pause_simulation(self, pause):
        if self.camera_manager:
            self.camera_manager.pause(pause)
        try:
            settings = self.world.get_settings()
            if pause and not settings.synchronous_mode:
                print("PAUSE: enable sync mode")
                self._paused = True
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 0.05
                self.client.set_timeout(0.1)
                self.world.apply_settings(settings)
            elif not pause and settings.synchronous_mode:
                print("PAUSE: disable sync mode")
                self._paused = False
                settings.synchronous_mode = False
                settings.fixed_delta_seconds = None
                self.client.set_timeout(0.1)
                self.world.apply_settings(settings)
        except RuntimeError:
            pass
        self.client.set_timeout(global_client_timeout)

    def restart(self, scenario_file, reset_position=False):
        if scenario_file in self._routing_targets_dict:
            routing_targets = self._routing_targets_dict[scenario_file]
        else:
            print("Could not find routing for scenario {}. RSS might not work as expected!".format(scenario_file))
            routing_targets = []

        #disable reverse gear
        if self._wheel_ctrl:
            self._wheel_ctrl._control = carla.VehicleControl()

        self.remove_traffic_participants()

        if self.player is not None:
            self.destroy_player()

        self.pause_simulation(False)
        self._overlay_dialog.set_text("")
        self._overlay_dialog.enable()
        self._overlay_dialog.render(self._display)

        # First spawn walkers (to avoid conflicts with sensors)
        try:
            if self._use_walkers:
                self._spawn_walkers()
        except Exception as e:
            print(e)

        if self._demo_mode:
            if not scenario_file or scenario_file == "CARLADemo.xosc":
                self._welcome_dialog.show_loading(True)
                self._welcome_dialog.enable()
                self._welcome_dialog.render(self._display)
            elif scenario_file == "scenarios/F6.xosc":
                self._rss_info_dialog.show_loading(True)
                self._rss_info_dialog.enable_id(self._rss_info_dialog_longitudinal)
                self._rss_info_dialog.render(self._display)
            elif scenario_file == "scenarios/F7.xosc":
                self._rss_info_dialog.show_loading(True)
                self._rss_info_dialog.enable_id(self._rss_info_dialog_right_of_way)
                self._rss_info_dialog.render(self._display)
            elif scenario_file == "scenarios/F8.xosc":
                self._rss_info_dialog.show_loading(True)
                self._rss_info_dialog.enable_id(self._rss_info_dialog_pedestrians)
                self._rss_info_dialog.render(self._display)
            elif scenario_file == "scenarios/F9.xosc":
                self._rss_info_dialog.show_loading(True)
                self._rss_info_dialog.enable_id(self._rss_info_dialog_parameters)
                self._rss_info_dialog.render(self._display)

        pygame.display.flip()
        self._scenario_runner.shutdown()
        # Keep same camera config if the camera manager exists.
        cam_index = self.camera_manager.index if self.camera_manager is not None else 0
        cam_pos_index = self.camera_manager.transform_index if self.camera_manager is not None else 0
        #print(self.world.get_blueprint_library())
        blueprint = self.world.get_blueprint_library().find('vehicle.lincoln.mkz_2017')
        blueprint.set_attribute('role_name', 'hero')
        blueprint.set_attribute('color', "255,255,255")
        # Second, spawn the player.
        spawn_points = self._map.get_spawn_points()
        spawn_point = spawn_points[1]
        self.player = self.world.try_spawn_actor(blueprint, spawn_point)
        while self.player is None:
            spawn_points = self._map.get_spawn_points()
            spawn_point = spawn_points[0]
            print("Trying to spawn ego at {}".format(spawn_point))
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)

        # Third, attach the sensors
        print("setting up sensors")
        self.camera_manager = CameraManager(self.player, self._display.get_size(), self._notifications.set_notification)
        self.camera_manager.transform_index = cam_pos_index
        self.camera_manager.set_sensor(cam_index, notify=False)
        if self._use_rss:
            dim = (self._display.get_width(), self._display.get_height())
            self.unstructured_scene_drawer = RssUnstructuredSceneVisualizer(self.player, self.world, dim)
            self.location_event_handler.retrigger(self.player, 1005)
            self._bounding_box_drawer = RssBoundingBoxVisualizer(dim, self.world, self.camera_manager.sensor)
            # TODO: check for hud state visualizer to pass to rss sensor, currently None
            self.rss_sensor = RssSensor(self.player, self.world,
                                        self.unstructured_scene_drawer, self._bounding_box_drawer, None, routing_targets)
            self.rss_sensor.sensor.set_log_level(self.rss_sensor_log_level)
            self.rss_sensor.sensor.set_map_log_level(self.rss_sensor_log_level)

            # TODO: only enabled for initial testing now...
            # self.rss_sensor.sensor.road_boundaries_mode = carla.RssRoadBoundariesMode.On
        else:
            self.rss_sensor = None

        self._collision_sensor = CollisionSensor(self.player, self._notifications)

        # Fourth, start scenario
        scenario_started = True
        if self._demo_mode:
            print("Execute scenario")
            scenario_started = self._scenario_runner.execute_scenario(scenario_file)
            if not scenario_started:
                self._overlay_dialog.set_text("Error while starting scenario.")
            else:
                self._welcome_dialog.show_loading(False)
                self._rss_info_dialog.show_loading(False)
        else:
            self._dashboard.enable()

        if scenario_started:
            self._overlay_dialog.disable()
        print("done")

    def _valid_walker_loc(self, location):
        if location.x > 300 and location.x < 350 and location.y > 70 and location.y < 150:
            return True
        if location.x > 90 and location.x < 150 and location.y > 130 and location.y < 150:
            return True
        if location.x > 150 and location.x < 350 and location.y > 100 and location.y < 150:
            return True
        if location.x > 80 and location.x < 110 and location.y > 130 and location.y < 340:
            return True
        if location.x > 80 and location.x < 350 and location.y > 300 and location.y < 350:
            return True
        return False

    def _spawn_walkers(self):
        # disable walker creation
        return
        # spawn pedestrians
        spawn_points = []
        while len(spawn_points) < 150:
            spawn_point = carla.Transform()
            loc = self.world.get_random_location_from_navigation()
            if loc != None and self._valid_walker_loc(loc):
                spawn_point.location = loc
                spawn_points.append(spawn_point)
        # 2. we spawn the walker object
        batch = []
        walkers_list = []
        SpawnActor = carla.command.SpawnActor
        blueprintsWalkers = self.world.get_blueprint_library().filter("walker.*")
        for spawn_point in spawn_points:
            walker_bp = random.choice(blueprintsWalkers)
            # set as not invencible
            if walker_bp.has_attribute('is_invincible'):
                walker_bp.set_attribute('is_invincible', 'false')
            batch.append(SpawnActor(walker_bp, spawn_point))
        results = self.client.apply_batch_sync(batch)
        self.world.wait_for_tick()
        for i in range(len(results)):
            if not results[i].error:
                walkers_list.append({"id": results[i].actor_id})
        # 3. we spawn the walker controller
        batch = []
        walker_controller_bp = self.world.get_blueprint_library().find('controller.ai.walker')
        for i in range(len(walkers_list)):
            batch.append(SpawnActor(walker_controller_bp, carla.Transform(), walkers_list[i]["id"]))
        results = self.client.apply_batch_sync(batch)
        self.world.wait_for_tick()
        for i in range(len(results)):
            if not results[i].error:
                walkers_list[i]["con"] = results[i].actor_id
        # 4. we put altogether the walkers and controllers id to get the objects from their id
        for i in range(len(walkers_list)):
            self._walker_ids.append(walkers_list[i]["con"])
            self._walker_ids.append(walkers_list[i]["id"])
        self._walkers = self.world.get_actors(self._walker_ids)

        # wait for a tick to ensure client receives the last transform of the walkers we have just created
        self.world.wait_for_tick()

        # 5. initialize each controller and set target to walk to (list is [controler, actor, controller, actor ...])
        for i in range(0, len(self._walker_ids), 2):
            # start walker
            self._walkers[i].start()
            # set walk to random point
            self._walkers[i].go_to_location(self.world.get_random_location_from_navigation())
            # random max speed
            self._walkers[i].set_max_speed(1 + random.random())    # max speed between 1 and 2 (default is 1.4 m/s)
        self.world.wait_for_tick()

    def next_weather(self, reverse=False):
        self._weather_index += -1 if reverse else 1
        self._weather_index %= len(self._weather_presets)
        preset = self._weather_presets[self._weather_index]
        self._notifications.set_notification('Weather: %s' % preset[1])
        self.player.get_world().set_weather(preset[0])


    def update_rss_restricts(self, restrict_lateral_active, restrict_longitudinal_active):
        previously_restrict_active = (self.restrict_lateral_active or self.restrict_longitudinal_active)
        restrict_active = restrict_lateral_active or restrict_longitudinal_active
        if restrict_active and not previously_restrict_active:
            self.rss_restrict_count += 1

        self.restrict_lateral_active = restrict_lateral_active
        self.restrict_longitudinal_active = restrict_longitudinal_active

        if restrict_active:
            notification_string = "RSS restricts: "
            if self.restrict_lateral_active:
                notification_string += "Lateral"
                if self.restrict_longitudinal_active:
                    notification_string += ", "
            if self.restrict_longitudinal_active:
                notification_string += "Longitudinal"
            self._notifications.set_notification(notification_string)

        #write to rss history
        if self._hud.frame:
            self._hud.rss_intervention_history.append((self._hud.frame, restrict_active))
            if len(self._hud.rss_intervention_history) > 4000:
                self._hud.rss_intervention_history.pop(0)

    def tick(self, clock):
        if self._wheel_ctrl.parse_events(self, clock):
            return True
        self.location_event_handler.tick(self.player)

        self.vehicles = self.world.get_actors().filter('vehicle.*')

        self._notifications.tick(clock)
        self._hud.tick(self, self.player, self.rss_sensor, self.vehicles, clock)
        self._dashboard.tick(self.player,
            self.rss_sensor,
            self.restricted_vehicle_control,
            self.restrict_longitudinal_active,
            self.restrict_lateral_active,
            self.speed_limit,
            self.throttle_input)

        return False

    def render(self, display):
        self.camera_manager.render(display)
        if self._bounding_box_drawer:
            self._bounding_box_drawer.render(display, self.camera_manager._current_frame)

        #paint rss intervention red frame
        if self.rss_restrict and (self.restrict_lateral_active or self.restrict_longitudinal_active):
            rect = pygame.Rect((0, 0), (12, self._display.get_height()))
            pygame.draw.rect(display, (255, 0, 0), rect, 0)
            rect = pygame.Rect((0, 0), (self._display.get_width(), 12))
            pygame.draw.rect(display, (255, 0, 0), rect, 0)
            rect = pygame.Rect((self._display.get_width()-12, 0), (self._display.get_width(), self._display.get_height()))
            pygame.draw.rect(display, (255, 0, 0), rect, 0)
            rect = pygame.Rect((0,self._display.get_height()-12), (self._display.get_width(), self._display.get_height()))
            pygame.draw.rect(display, (255, 0, 0), rect, 0)

        self._dashboard.render(display)
        self._hud.render(display)

        # draw as late as possible
        self._notifications.render(display)
        self._wheel_ctrl.render(display)


        # Scene: Change RSS Parameters
        self._rss_parameter_display.render(display)

        # enables unstructured display when an unstructured situation becomes dangerous
        #if self.rss_sensor.is_unstructured_dangerous():
        #    self.display_unstructured(None, True)

        # Scene: Pedestrian
        if self.unstructured_scene_drawer:
            self.unstructured_scene_drawer.render(display)
        if self._demo_mode:
            self._navigation_dialog.render(display)
            self._rss_info_dialog.render(display)
            self._welcome_dialog.render(display)
            self._finish_dialog.render(display)
            self._left_the_road_dialog.render(display)

        self._overlay_dialog.render(display)
        self._help.render(display)

        display.blit(self._logo, self._logo_pos)

    def destroy_player(self):
        if self.rss_sensor:
            self.rss_sensor_log_level = self.rss_sensor.log_level
            self.rss_sensor.destroy()
            self.rss_sensor = None
        actors = []
        if self.camera_manager:
            self.camera_manager.sensor.stop()
            actors.append(self.camera_manager.sensor)
        actors.append(self.player)
        for actor in actors:
            if actor is not None:
                actor.destroy()
                actor = None
        actors = []
        self.camera_manager.sensor = None
        self.camera_manager = None

    def destroy(self):
        print("Shutting down manual control.")
        self.destroy_player()
        self.remove_traffic_participants()
        self._scenario_runner.shutdown()

    def remove_traffic_participants(self):
        print('\ndestroying %d vehicles and %d walkers' % (len(self._traffic_participants), len(self._walkers)))
        for i in range(0, len(self._walker_ids), 2):
            self._walkers[i].stop()

        self.client.apply_batch([carla.command.DestroyActor(x) for x in self._traffic_participants + self._walker_ids])

        self.world.tick()
        self._walker_ids = []
        self._walkers = []
        self._traffic_participants = []

    def toggle_traffic_participants(self):
        # disable traffic participants
        return
        if not self._traffic_participants_active:
            #spawn traffic participants
            spawn_points = self._map.get_spawn_points()
            blueprints = self.world.get_blueprint_library().filter('vehicle.*')
            batch = []
            for n, transform in enumerate(spawn_points):
                if n >= 50:
                    break
                blueprint = random.choice(blueprints)
                if blueprint.has_attribute('color'):
                    color = random.choice(blueprint.get_attribute('color').recommended_values)
                    blueprint.set_attribute('color', color)
                if blueprint.has_attribute('driver_id'):
                    driver_id = random.choice(blueprint.get_attribute('driver_id').recommended_values)
                    blueprint.set_attribute('driver_id', driver_id)
                blueprint.set_attribute('role_name', 'autopilot')
                batch.append(carla.command.SpawnActor(blueprint, transform).then(carla.command.SetAutopilot(carla.command.FutureActor, True)))

            for response in self.client.apply_batch_sync(batch):
                if response.error:
                    logging.error(response.error)
                else:
                    self._traffic_participants.append(response.actor_id)
        else:
            self.remove_traffic_participants()

            #destroy traffic participants
        self._traffic_participants_active = not self._traffic_participants_active

    def position_ego_on_next_waypoint(self):
        if self.player:
            wp = self._map.get_waypoint(self.player.get_location())
            if wp:
                self.player.set_transform(wp.transform)
                self._notifications.set_notification("Successfully placed hero back on route.")
            else:
                self._notifications.set_notification("Error while setting transform of hero")

# ==============================================================================
# -- CameraManager -------------------------------------------------------------
# ==============================================================================


class CameraManager(object):
    def __init__(self, parent_actor, display_size, notification_fct):
        self._current_frame = -1
        self.sensor = None
        self.surface = None
        self._parent = parent_actor
        self._dim = display_size
        self._notification_fct = notification_fct
        self.recording = False
        self._camera_transforms = [
            carla.Transform(carla.Location(x=-5.5, z=2.8), carla.Rotation(pitch=-15)),
            carla.Transform(carla.Location(x=0.0, y=-0.35, z=1.3)),
            carla.Transform(carla.Location(x=0.5, z=1.4))]
        self.transform_index = 1
        self.sensors = [
            ['sensor.camera.rgb', cc.Raw, 'Camera RGB'],
            ['sensor.camera.depth', cc.Raw, 'Camera Depth (Raw)'],
            ['sensor.camera.depth', cc.Depth, 'Camera Depth (Gray Scale)'],
            ['sensor.camera.depth', cc.LogarithmicDepth, 'Camera Depth (Logarithmic Gray Scale)'],
            ['sensor.camera.semantic_segmentation', cc.Raw, 'Camera Semantic Segmentation (Raw)'],
            ['sensor.camera.semantic_segmentation', cc.CityScapesPalette,
                'Camera Semantic Segmentation (CityScapes Palette)'],
            ['sensor.lidar.ray_cast', None, 'Lidar (Ray-Cast)']]
        world = self._parent.get_world()
        bp_library = world.get_blueprint_library()
        for item in self.sensors:
            bp = bp_library.find(item[0])
            if item[0].startswith('sensor.camera'):
                bp.set_attribute('image_size_x', str(self._dim[0]))
                bp.set_attribute('image_size_y', str(self._dim[1]))
            elif item[0].startswith('sensor.lidar'):
                bp.set_attribute('range', '5000')
            item.append(bp)
        self.index = None
        self._pause = False

    def pause(self, pause):
        self._pause = pause

    def toggle_camera(self):
        self.transform_index = (self.transform_index + 1) % len(self._camera_transforms)
        self.sensor.set_transform(self._camera_transforms[self.transform_index])

    def set_sensor(self, index, notify=True):
        index = index % len(self.sensors)
        needs_respawn = True if self.index is None \
            else self.sensors[index][0] != self.sensors[self.index][0]
        if needs_respawn:
            if self.sensor is not None:
                self.sensor.destroy()
                self.surface = None
            self.sensor = self._parent.get_world().spawn_actor(
                self.sensors[index][-1],
                self._camera_transforms[self.transform_index],
                attach_to=self._parent)
            # We need to pass the lambda a weak reference to self to avoid
            # circular reference.
            #weak_self = weakref.ref(self)
            self.sensor.listen(lambda image: self._parse_image(image))
        if notify:
            self._notification_fct(self.sensors[index][2])
        self.index = index

    def next_sensor(self):
        self.set_sensor(self.index + 1)

    def toggle_recording(self):
        self.recording = not self.recording
        self._notification_fct('Recording %s' % ('On' if self.recording else 'Off'))

    def render(self, display):
        if self.surface is not None:
            display.blit(self.surface, (0, 0))

    def _parse_image(self, image):
        if not self:
            return
        self._current_frame = image.frame
        if self.sensors[self.index][0].startswith('sensor.lidar'):
            points = np.frombuffer(image.raw_data, dtype=np.dtype('f4'))
            points = np.reshape(points, (int(points.shape[0] / 3), 3))
            lidar_data = np.array(points[:, :2])
            lidar_data *= min(self._dim) / 100.0
            lidar_data += (0.5 * self._dim[0], 0.5 * self._dim[1])
            lidar_data = np.fabs(lidar_data) # pylint: disable=E1111
            lidar_data = lidar_data.astype(np.int32)
            lidar_data = np.reshape(lidar_data, (-1, 2))
            lidar_img_size = (self._dim[0], self._dim[1], 3)
            lidar_img = np.zeros(lidar_img_size)
            lidar_img[tuple(lidar_data.T)] = (255, 255, 255)
            if not self._pause:
                self.surface = pygame.surfarray.make_surface(lidar_img)
        else:
            image.convert(self.sensors[self.index][1])
            array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
            array = np.reshape(array, (image.height, image.width, 4))
            array = array[:, :, :3]
            array = array[:, :, ::-1]
            if not self._pause:
                self.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame)


# ==============================================================================
# -- game_loop() ---------------------------------------------------------------
# ==============================================================================


def game_loop(args):
    pygame.init()
    pygame.font.init()
    pygame.display.set_caption("CARLA RSS Demo")
    world = None

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(global_client_timeout)
        carla_map = client.get_world().get_map()
        print("Connected to CARLA")
        if not carla_map.name == "Town01":
            print("Switching to Town01")
            client.load_world("Town01")

        display = pygame.display.set_mode(
            (args.width, args.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF)
        if args.fullscreen:
            pygame.display.toggle_fullscreen()

        overlay_dialog = OverlayDialog(args.width, args.height)
        scenario_runner = ScenarioRunnerRunner()


        clock = pygame.time.Clock()
        #overlay_dialog.set_text("Loading...")
        overlay_dialog.enable()
        overlay_dialog.render(display)
        pygame.display.flip()

        world = World(client, scenario_runner, overlay_dialog, display, args.scenario, args.autopilot, not args.norss, args.walkers, not args.nodemo, not args.nowheel)
        world.start()

        while True:
            clock.tick_busy_loop(60)
            #print(clock.get_fps())

            if world.tick(clock):
                return
            world.render(display)
            pygame.display.flip()

            #bla = client.get_world().get_actors().filter("*light*")
            #for light in  bla:
            #    light.set_state(carla.TrafficLightState.Yellow)
            #    print("{} {} {}".format(light.get_green_time(), light.get_yellow_time(), light.get_red_time()))
            #    light.set_red_time(4)
            #    light.set_green_time(4)
            #    light.set_yellow_time(1)
    except Exception as e:
        print(e)
    finally:

        if world is not None:
            world.destroy()

        pygame.quit()


# ==============================================================================
# -- main() --------------------------------------------------------------------
# ==============================================================================


def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-a', '--autopilot',
        action='store_true',
        help='enable autopilot')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')
    argparser.add_argument(
        '--scenario',
        metavar='FILENAME',
        default='CARLADemo.xosc',
        help='OpenScenario file to execute')
    argparser.add_argument(
        '-f', '--fullscreen',
        action='store_true',
        help='fullscreen display')
    argparser.add_argument(
        '--norss',
        action='store_true',
        help='do not use any rss functionality')
    argparser.add_argument(
        '--walkers',
        action='store_true',
        help='add background pedestrians')
    argparser.add_argument(
        '--nodemo',
        action='store_true',
        help='do not execute demo')
    argparser.add_argument(
        '--nowheel',
        action='store_true',
        help='do not use steering wheel')
    args = argparser.parse_args()

    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    print(__doc__)

    try:

        game_loop(args)

    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':

    main()

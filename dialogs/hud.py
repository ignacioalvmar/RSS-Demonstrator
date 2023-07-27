
import math
import collections
import pygame

try:
    from carla import ad
except ImportError:
    print("Module 'carla' not found.")
    pass

# ==============================================================================
# -- HUD -----------------------------------------------------------------------
# ==============================================================================


class HUD(object):
    def __init__(self, width, height):
        self.dim = (width, height)
        self._font_mono = pygame.font.Font('fonts/intelone-display-regular.ttf', 14)
        self._font_mono_big = pygame.font.Font('fonts/intelone-display-regular.ttf', 22)
        self.frame = 0
        self._show_info = False
        self._info_text = []
        self.velocity = 0
        self.rss_intervention_history = []

    def on_world_tick(self, world_snapshot):
        self.frame = world_snapshot.frame

    def tick(self, world, player, rss_sensor, vehicles, clock):
        if not self._show_info:
            return
        self.rss_states = None
        if not rss_sensor:
            return

        self.rss_states = rss_sensor.individual_rss_states
        self.vehicles = vehicles
        rsshist = self.get_rss_intervention_history()
        rss_interventions = [rsshist[x + self.frame - 220] for x in range(0, 220)]

        self._info_text = [
            'Response Valid:   {}'.format("true" if rss_sensor.response_valid else "false"),
            '',
            'RSS Proper Response:',
            'isSafe:           {}'.format("true" if rss_sensor.proper_response.isSafe else "false"),
            'dangerousObjects: {}'.format(', '.join(str(p) for p in rss_sensor.proper_response.dangerousObjects)),
            'lonResponse:      {}'.format(rss_sensor.proper_response.longitudinalResponse),
            'latResponseLeft:  {}'.format(rss_sensor.proper_response.lateralResponseLeft),
            'latResponseRight: {}'.format(rss_sensor.proper_response.lateralResponseRight),
            '',
            'AccelerationRestriction:',
            'lonRange:         {}..{}'.format(rss_sensor.proper_response.accelerationRestrictions.longitudinalRange.minimum, rss_sensor.proper_response.accelerationRestrictions.longitudinalRange.maximum),
            'latLeftRange:     {}..{}'.format(rss_sensor.proper_response.accelerationRestrictions.lateralLeftRange.minimum, rss_sensor.proper_response.accelerationRestrictions.lateralLeftRange.maximum),
            'latRightRange:    {}..{}'.format(rss_sensor.proper_response.accelerationRestrictions.lateralRightRange.minimum, rss_sensor.proper_response.accelerationRestrictions.lateralRightRange.maximum),
            '',
            'EgoDynamicsOnRoute:',
            'egoSpeed:        % 3.1f' % (rss_sensor.ego_dynamics_on_route.ego_speed),
            'egoHeading:      % 1.3f' % (rss_sensor.ego_dynamics_on_route.ego_heading),
            'routeHeading:    % 1.3f' % (rss_sensor.ego_dynamics_on_route.route_heading),
            'headingDiff:     % 1.3f' % (rss_sensor.ego_dynamics_on_route.heading_diff),
            'routeSpeedLat:   % 3.1f' % (rss_sensor.ego_dynamics_on_route.route_speed_lat),
            'routeSpeedLon:   % 3.1f' % (rss_sensor.ego_dynamics_on_route.route_speed_lon),
            'routeAccelLat:   % 1.3f' % (rss_sensor.ego_dynamics_on_route.route_accel_lat),
            'routeAccelLon:   % 1.3f' % (rss_sensor.ego_dynamics_on_route.route_accel_lon),
            'avgRouteAccelLat:% 1.3f' % (rss_sensor.ego_dynamics_on_route.avg_route_accel_lat),
            'avgRouteAccelLon:% 1.3f' % (rss_sensor.ego_dynamics_on_route.avg_route_accel_lon),
            '',
            'RssDynamics:',
            '  alphaLon:',
            '    accelMax:    % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLon.accelMax),
            '    brakeMax:    % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLon.brakeMax),
            '    brakeMin:    % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLon.brakeMin),
            '    brakeMinC:   % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLon.brakeMinCorrect),
            '  alphaLat:',
            '    accelMax:    % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLat.accelMax),
            '    brakeMin:    % 1.2f' % (rss_sensor.current_vehicle_parameters.alphaLat.brakeMin),
            'lateralFluctuationMargin:% 1.2f' % (rss_sensor.current_vehicle_parameters.lateralFluctuationMargin),
            'responseTime:    % 1.2f' % (rss_sensor.current_vehicle_parameters.responseTime),
            'maxSpeedOnAccel: % 3.2f' % (rss_sensor.current_vehicle_parameters.maxSpeedOnAcceleration)
            ]

        self._info_text += [
            '',
            'RSS Interventions:',
            rss_interventions,
            '']

    def get_rss_intervention_history(self):
        history = collections.defaultdict(bool)
        last_frame = None
        for frame, intervention in self.rss_intervention_history:
            if last_frame is None:
                last_frame = frame
            else:
                #fill missing frames
                if last_frame+1 < frame-1:
                    for x in range(last_frame+1, frame):
                        history[x] = intervention
                last_frame = frame

            if not frame in history:
                history[frame] = intervention
            else:
                if intervention:
                    history[frame] = True
        return history

    def enable_info(self):
        self._show_info = True

    def disable_info(self):
        self._show_info = False

    def toggle_info(self):
        self._show_info = not self._show_info

    def render(self, display):

        if self._show_info:
            # paint info console
            info_surface = pygame.Surface((250, self.dim[1]))
            info_surface.set_alpha(100)
            display.blit(info_surface, (0, 0))

            v_offset = 16
            bar_h_offset = 120
            bar_width = 106
            for item in self._info_text:
                text_color = (255, 255, 255)
                if v_offset + 18 > self.dim[1]:
                    break
                if isinstance(item, list):
                    if len(item) > 1:
                        points = [(x + 8, v_offset + 8 + (1.0 - y) * 30) for x, y in enumerate(item)]
                        pygame.draw.lines(display, (255, 136, 0), False, points, 2)
                    item = None
                    v_offset += 18
                elif isinstance(item, tuple):
                    if isinstance(item[1], bool):
                        rect = pygame.Rect((bar_h_offset + 44, v_offset + 8), (12, 12))
                        pygame.draw.rect(display, (255, 255, 255), rect, 0 if item[1] else 1)
                    else:
                        rect_border = pygame.Rect((bar_h_offset, v_offset + 8), (bar_width, 12))
                        pygame.draw.rect(display, (255, 255, 255), rect_border, 1)
                        f = (item[1] - item[2]) / (item[3] - item[2])
                        if item[2] < 0.0:
                            rect = pygame.Rect((bar_h_offset + f * (bar_width - 12), v_offset + 8), (12, 12))
                        else:
                            rect = pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 12))
                        pygame.draw.rect(display, (255, 255, 255), rect)
                        if len(item) == 6:
                            if item[1] != item[4] or item[5]:
                                pygame.draw.rect(display, (255, 0, 0), rect_border, 1)
                                f = (item[4] - item[2]) / (item[3] - item[2])
                                if item[2] < 0.0:
                                    rect = pygame.Rect((bar_h_offset + f * (bar_width - 12), v_offset + 8), (12, 12))
                                else:
                                    rect = pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 12))
                                pygame.draw.rect(display, (255, 0, 0), rect)
                                text_color = (255, 0, 0)
                    item = item[0]
                #workaround, as sometimes item seems to get discarded (render reports 'empty string')
                if isinstance(item, str) and len(item) > 0:  # At this point has to be a str and not empty
                    try:
                        surface = self._font_mono.render(item, True, text_color)
                        display.blit(surface, (16, v_offset))
                    except pygame.error as message:
                        print(message)
                        pass
                v_offset += 18

            v_offset += 10
            #rss states
            if self.rss_states:
                surface = self._font_mono.render('RSS States:', True, (255, 255, 255))
                display.blit(surface, (16, v_offset))
                v_offset += 26
                for state in self.rss_states:
                    object_name = "Obj"
                    if state.rss_state.objectId == 18446744073709551614:
                        object_name = "Border Left"
                    elif state.rss_state.objectId==18446744073709551615:
                        object_name = "Border Right"
                    else:
                        actor = self.vehicles.find(state.rss_state.objectId)
                        if actor:
                            li = list(actor.type_id.split("."))
                            if li:
                                li.pop(0)
                            li = [element.capitalize() for element in li]

                            object_name = " ".join(li).strip()[:18]

                    item = '% 5dm %8s' % (state.margin, object_name)
                    # print("X {}".format(state.rss_state))
                    # print("XXX {}".format(state.rss_state.longitudinalState.rssStateInformation.evaluator))

                    surface = self._font_mono.render(item, True, text_color)
                    display.blit(surface, (15, v_offset))
                    color = (0, 255, 0)
                    if state.is_dangerous:
                        color = (255,0,0)
                    pygame.draw.circle(display, color, (20, v_offset+7), 5)
                    # print(type(state.rss_state.longitudinalState.rssStateInformation.evaluator))
                    xpos = 200
                    if state.actor_calculation_mode == ad.rss.map.RssMode.Structured:
                        if not state.rss_state.longitudinalState.isSafe and ((state.rss_state.longitudinalState.rssStateInformation.evaluator == ad.rss.state.RssStateEvaluator.LongitudinalDistanceSameDirectionOtherInFront) or (state.rss_state.longitudinalState.rssStateInformation.evaluator == ad.rss.state.RssStateEvaluator.LongitudinalDistanceSameDirectionEgoFront)):
                            pygame.draw.polygon(display, (255, 255, 255), ((xpos+1, v_offset+1+4), (xpos+6, v_offset+1+0), (xpos+11, v_offset+1+4), (xpos+7, v_offset+1+4), (xpos+7, v_offset+1+12), (xpos+5, v_offset+1+12), (xpos+5, v_offset+1+4)))
                            xpos += 14

                        if not state.rss_state.longitudinalState.isSafe and ((state.rss_state.longitudinalState.rssStateInformation.evaluator == ad.rss.state.RssStateEvaluator.LongitudinalDistanceOppositeDirectionEgoCorrectLane) or (state.rss_state.longitudinalState.rssStateInformation.evaluator == ad.rss.state.RssStateEvaluator.LongitudinalDistanceOppositeDirection)):
                            pygame.draw.polygon(display, (255, 255, 255), ((xpos+2, v_offset+1+8), (xpos+6, v_offset+1+12), (xpos+10, v_offset+1+8), (xpos+7, v_offset+1+8), (xpos+7, v_offset+1+0), (xpos+5, v_offset+1+0), (xpos+5, v_offset+1+8)))
                            xpos += 14

                        if not state.rss_state.lateralStateRight.isSafe and not (str(state.rss_state.lateralStateRight.rssStateInformation.evaluator) == "None"):
                            pygame.draw.polygon(display, (255, 255, 255), ((xpos+0, v_offset+1+4), (xpos+8, v_offset+1+4), (xpos+8, v_offset+1+1), (xpos+12, v_offset+1+6), (xpos+8, v_offset+1+10), (xpos+8, v_offset+1+8), (xpos+0, v_offset+1+8)))
                            xpos += 14
                        if not state.rss_state.lateralStateLeft.isSafe and not (str(state.rss_state.lateralStateLeft.rssStateInformation.evaluator) == "None"):
                            pygame.draw.polygon(display, (255, 255, 255), ((xpos+0, v_offset+1+6), (xpos+4, v_offset+1+1), (xpos+4, v_offset+1+4), (xpos+12, v_offset+1+4), (xpos+12, v_offset+1+8), (xpos+4, v_offset+1+8), (xpos+4, v_offset+1+10)))
                            xpos += 14
                        #arrow up

                        #pygame.draw.polygon(display, (255, 255, 255), ((1, 4), (6, 0), (11, 4), (7, 4), (7, 12), (5, 12), (5, 4)))
                        #arrow down
                        #pygame.draw.polygon(display, (255, 255, 255), ((1, 8), (6, 12), (11, 8), (7, 8), (7, 0), (5, 0), (5, 8)))
                    elif state.actor_calculation_mode == ad.rss.map.RssMode.Unstructured:
                        text = ""
                        if state.rss_state.unstructuredSceneState.response == ad.rss.state.UnstructuredSceneResponse.DriveAway:
                            text = "  D"
                        elif state.rss_state.unstructuredSceneState.response == ad.rss.state.UnstructuredSceneResponse.ContinueForward:
                            text = "  C"
                        elif state.rss_state.unstructuredSceneState.response == ad.rss.state.UnstructuredSceneResponse.Brake:
                            text = "  B"
                        surface = self._font_mono.render(text, True, text_color)
                        display.blit(surface, (xpos, v_offset))

                    v_offset += 14

#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog
import math

try:
    from carla import ad
except ImportError:
    print("Module 'carla' not found.")
    pass

class Dashboard(BaseDialog):
    def __init__(self, width, height):
        super(Dashboard, self).__init__(width, height)

        self._current_speed = 0
        self._vehicle_control = None
        self._restricted_vehicle_control = None
        self._restrict_longitudinal_active = False
        self._restrict_lateral_active = False
        self._rss_proper_response = None
        self._speed_limit = 0
        self._throttle_input = 0

        self._dim = (800,130)
        self._bg_surface = pygame.Surface(self._dim)
        self._bg_surface.set_alpha(200)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[0]/2, self._screen_dim[1] - self._bg_surface.get_size()[1])

        self._surface = pygame.Surface(self._dim)
        self._surface.set_colorkey(pygame.Color('black'))

        self.blit_text(self._surface, "Speed (km/h)", (40,10), self._font_normal)

        self.blit_text(self._surface, "   Reverse", (205,91), self._font_normal)

        #steering center
        rect = pygame.Rect((439, 67), (1, 20))
        pygame.draw.rect(self._surface, (255, 255, 255), rect)

        self.blit_text(self._surface, "RSS Response", (620,10), self._font_normal)

        self._car_image = pygame.image.load("images/car_white_front.png")

    def tick(self, player, rss_sensor,
            restricted_vehicle_control,
            restrict_longitudinal_active,
            restrict_lateral_active,
            speed_limit,
            throttle_input):
        self._vehicle_control = player.get_control()

        v = player.get_velocity()
        speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
        if speed > 0.1 and self._vehicle_control.reverse:
            speed = -speed

        if speed > speed_limit:
            speed = speed_limit

        self._throttle_input = throttle_input
        self._current_speed = '%2.0f' % (speed)

        self._restricted_vehicle_control = restricted_vehicle_control
        self._restrict_longitudinal_active = restrict_longitudinal_active
        self._restrict_lateral_active = restrict_lateral_active
        if rss_sensor:
            self._rss_proper_response = rss_sensor.proper_response
        self.render_dynamic()

    def render_dynamic(self):
        self._dynamic_surface = pygame.Surface(self._dim)
        self._dynamic_surface.set_colorkey(pygame.Color('black'))

        #speed
        self.blit_text(self._dynamic_surface, self._current_speed, (60,30), self._font_extrahuge)

        if self._restricted_vehicle_control is not None:
            self.drawBar((215,10), " Throttle", (310, 13), self._throttle_input, 0.0, 1.0, self._restricted_vehicle_control.throttle, self._restrict_longitudinal_active)
            self.drawBar((210,37), "      Brake", (310, 40), self._vehicle_control.brake, 0.0, 1.0, self._restricted_vehicle_control.brake, self._restrict_longitudinal_active)
            self.drawBar((210,64), " Steering", (310, 67), self._vehicle_control.steer, -1.0, 1.0, self._restricted_vehicle_control.steer, self._restrict_lateral_active)
        else:
            self.drawBar((215,10), " Throttle", (310, 13), self._throttle_input, 0.0, 1.0, None, None)
            self.drawBar((210,37), "      Brake", (310, 40), self._vehicle_control.brake, 0.0, 1.0, None, None)
            self.drawBar((210,64), " Steering", (310, 67), self._vehicle_control.steer, -1.0, 1.0, None, None)

        #reverse
        rect = pygame.Rect((310, 96), (16, 16))
        pygame.draw.rect(self._dynamic_surface, (255, 255, 255), rect, 0 if self._vehicle_control.reverse else 1)

        self._dynamic_surface.blit(self.getRssSurface(), (620, 43))


    def getRssSurface(self):
        dim = (138,130-43)
        surface = pygame.Surface(dim)

        if self._rss_proper_response is not None:
            #left car border
            left_color = (0, 255, 0)
            if str(self._rss_proper_response.lateralResponseLeft) != "None":
                left_color = (255, 0, 0)
            left_poly = [(0,0), (40,40), (40,dim[1]), (0,dim[1])]
            pygame.draw.polygon(surface, left_color, left_poly, 0)

            #right car border
            right_color = (0, 255, 0)
            if str(self._rss_proper_response.lateralResponseRight) != "None":
                right_color = (255, 0, 0)
            right_poly = [(138,0), (98,40), (98, dim[1]), (138, dim[1])]
            pygame.draw.polygon(surface, right_color, right_poly, 0)

            #top car border
            top_color = (0, 255, 0)
            if str(self._rss_proper_response.longitudinalResponse) != "None" or str(self._rss_proper_response.unstructuredSceneResponse) == 'Brake':
                top_color = (255, 0, 0)
            top_poly = [(0,0), (138,0), (98,40), (40, 40)]
            pygame.draw.polygon(surface, top_color, top_poly, 0)


            pygame.draw.polygon(surface, (255, 255, 255), left_poly, 1)
            pygame.draw.polygon(surface, (255, 255, 255), right_poly, 1)
            pygame.draw.polygon(surface, (255, 255, 255), top_poly, 1)

            surface.blit(self._car_image, (-1, 9))
        return surface

    def drawBar(self, text_pos, text, pos, val, min_val, max_val, restricted_val, restrict_active):
        text_color = (255, 255, 255)
        bar_width = 260 - 4
        bar_h_offset = pos[0] + 2
        v_offset = pos[1] + 2
        rect_border = pygame.Rect(pos, (bar_width + 4, 20))
        pygame.draw.rect(self._dynamic_surface, (255, 255, 255), rect_border, 1)

        f = (val - min_val) / (max_val - min_val)
        if min_val < 0.0:
            rect = pygame.Rect((bar_h_offset + f * (bar_width - 12), v_offset), (12, 16))
        else:
            rect = pygame.Rect((bar_h_offset, v_offset), (f * bar_width, 16))
        pygame.draw.rect(self._dynamic_surface, (255, 255, 255), rect)

        if restricted_val is not None:
            if val != restricted_val or restrict_active:
                pygame.draw.rect(self._dynamic_surface, (255, 0, 0), rect_border, 1)
                f = (restricted_val - min_val) / (max_val - min_val)
                if min_val < 0.0:
                    rect = pygame.Rect((bar_h_offset + f * (bar_width - 12), v_offset), (12, 16))
                else:
                    rect = pygame.Rect((bar_h_offset, v_offset), (f * bar_width, 16))
                pygame.draw.rect(self._dynamic_surface, (255, 0, 0), rect)
                text_color = (255, 0, 0)

        self.blit_text(self._dynamic_surface, text, text_pos, self._font_normal, text_color)

    def render(self, display):
        if self._render:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surface, self._pos)
            display.blit(self._dynamic_surface, self._pos)

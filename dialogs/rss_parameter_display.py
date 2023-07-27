#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog
from rss_sensor import RssSensor

class RssParameterDisplay(BaseDialog):
    def __init__(self, width, height):
        super(RssParameterDisplay, self).__init__(width, height)
        self._bg_surface = None
        self._surface = None
        self._white_car_image = pygame.image.load("images/car_white_front.png")
        self._blue_car_short_image = pygame.image.load("images/car_blue_back_short.png")
        self._blue_car_image = pygame.image.load("images/car_blue_back.png")
        self._accel_image = pygame.image.load("images/accel.png")

    def set_param_assertive(self, assertive, rss_sensor):
        color=(255, 255, 255)
        dim = (400,400)
        #|-20-| Conservative (180) |-10-|-10-| Assertive (180) |-20-|
        self._bg_surface = pygame.Surface(dim)
        self._bg_surface.set_alpha(150)
        self._pos = (self._screen_dim[0] - self._bg_surface.get_width() - 80, self._screen_dim[1] - self._bg_surface.get_height() - 60)

        self._surface = pygame.Surface(self._bg_surface.get_size())
        self._surface.set_colorkey((0,0,0))

        #conservative surrface
        self._conservative_surface = pygame.Surface(self._bg_surface.get_size())
        self._conservative_surface.set_colorkey((0,0,0))
        conservative_texture = self._font_big.render("Conservative", True, color)

        other_car_text = self._font_big.render("% 1.1f .. % 1.1f" % (-RssSensor.get_default_parameters().alphaLon.brakeMax, RssSensor.get_default_parameters().alphaLon.accelMax), True, color)
        ego_text = self._font_big.render("% 1.1f .. % 1.1f" % (-RssSensor.get_default_parameters().alphaLon.brakeMin, RssSensor.get_default_parameters().alphaLon.accelMax), True, color)

        self._conservative_surface.blit(conservative_texture, (20 + (180 - conservative_texture.get_width())/2, 10))
        self._conservative_surface.blit(self._white_car_image, (20 + (180 - self._white_car_image.get_width())/2, dim[1] - self._white_car_image.get_height() - ego_text.get_height() - 10))
        self._conservative_surface.blit(self._blue_car_short_image, (20 + (180 - self._blue_car_short_image.get_width())/2, 80))

        self._conservative_surface.blit(other_car_text, (20 + (180 - other_car_text.get_width() - self._accel_image.get_width())/2, 50))
        self._conservative_surface.blit(self._accel_image, (20 + (180 - other_car_text.get_width() - self._accel_image.get_width())/2 + other_car_text.get_width(), 57))

        self._conservative_surface.blit(ego_text, (20 + (180 - ego_text.get_width() - self._accel_image.get_width())/2, dim[1] - ego_text.get_height() - 10))
        self._conservative_surface.blit(self._accel_image, (20 + (180 - ego_text.get_width() - self._accel_image.get_width())/2 + ego_text.get_width(), dim[1] - ego_text.get_height() - 3))


        rect_center = pygame.Rect((20 + 180/2 - 6/2, 80 + self._blue_car_short_image.get_height()), (6, dim[1]-self._white_car_image.get_height() - ego_text.get_height() - 10 - 80 - self._blue_car_short_image.get_height()))
        pygame.draw.rect(self._conservative_surface, (255, 255, 255), rect_center, 0)
        rect_bottom = pygame.Rect((20 + 180/2 - 20/2, dim[1] - self._white_car_image.get_height() - ego_text.get_height() - 10 - 6), (20, 6))
        pygame.draw.rect(self._conservative_surface, (255, 255, 255), rect_bottom, 0)
        rect_top = pygame.Rect((20 + 180/2 - 20/2, 80 + self._blue_car_short_image.get_height()), (20, 6))
        pygame.draw.rect(self._conservative_surface, (255, 255, 255), rect_top, 0)

        #assertive surrface
        self._assertive_surface = pygame.Surface(self._bg_surface.get_size())
        self._assertive_surface.set_colorkey((0,0,0))
        assertive_texture = self._font_big.render("Assertive", True, color)

        other_car_text2 = self._font_big.render("% 1.1f .. % 1.1f" % (-RssSensor.get_assertive_parameters().alphaLon.brakeMax, RssSensor.get_assertive_parameters().alphaLon.accelMax), True, color)
        ego_text2 = self._font_big.render("% 1.1f .. % 1.1f" % (-RssSensor.get_assertive_parameters().alphaLon.brakeMin, RssSensor.get_assertive_parameters().alphaLon.accelMax), True, color)

        self._assertive_surface.blit(assertive_texture, (20 + 180 + (180 - assertive_texture.get_width())/2, 10))
        self._assertive_surface.blit(self._white_car_image, (20 + 180  + (180 - self._white_car_image.get_width())/2, dim[1]-self._white_car_image.get_height() - ego_text2.get_height() - 10))
        self._assertive_surface.blit(self._blue_car_image, (20 + 180 + (180 - self._blue_car_image.get_width())/2, 80))

        self._assertive_surface.blit(other_car_text2, (20 + 180 + (180 - other_car_text2.get_width() - self._accel_image.get_width())/2, 50))
        self._assertive_surface.blit(self._accel_image, (20 + 180 + (180 - other_car_text2.get_width() - self._accel_image.get_width())/2 + other_car_text2.get_width(), 57))

        self._assertive_surface.blit(ego_text2, (20 + 180 + (180 - ego_text2.get_width() - self._accel_image.get_width())/2, dim[1] - ego_text2.get_height() - 10))
        self._assertive_surface.blit(self._accel_image, (20 + 180 + (180 - ego_text2.get_width() - self._accel_image.get_width())/2 + ego_text2.get_width(), dim[1] - ego_text2.get_height() - 3))

        rect_center = pygame.Rect((20 + 180 + 180/2 - 6/2, 80 + self._blue_car_image.get_height()), (6, dim[1]-self._white_car_image.get_height() - ego_text.get_height() - 10 - 80 - self._blue_car_image.get_height()))
        pygame.draw.rect(self._assertive_surface, (255, 255, 255), rect_center, 0)
        rect_bottom = pygame.Rect((20 + 180 + 180/2 - 20/2, dim[1] - self._white_car_image.get_height() - ego_text.get_height() - 10 - 6), (20, 6))
        pygame.draw.rect(self._assertive_surface, (255, 255, 255), rect_bottom, 0)
        rect_top = pygame.Rect((20 + 180 + 180/2 - 20/2, 80 + self._blue_car_image.get_height()), (20, 6))
        pygame.draw.rect(self._assertive_surface, (255, 255, 255), rect_top, 0)

        if assertive:
            self._conservative_surface.set_alpha(100)
        else:
            self._assertive_surface.set_alpha(100)



        self._surface.blit(self._conservative_surface, (0,0))
        self._surface.blit(self._assertive_surface, (0,0))



        self.enable()

    def render(self, display):
        if self._render and self._surface and self._bg_surface:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surface, self._pos)

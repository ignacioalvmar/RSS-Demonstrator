#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog

class Notification(BaseDialog):
    def __init__(self, width, height):
        super(Notification, self).__init__(width, height)
        self._seconds_left = 0
        self._bg_surface = None
        self._surface = None
        self._static_warning_active = False
        self._warning_image = pygame.image.load("images/warning.png")


    def set_notification(self, text, color=(255, 255, 255), seconds=2.0):
        if self._static_warning_active:
            return
        text_texture = self._font_bigger.render(text, True, color)

        self._bg_surface = pygame.Surface((text_texture.get_width() + 40, text_texture.get_height() + 20))
        self._bg_surface.set_alpha(150)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_width()/2, 40)
        
        self._surface = pygame.Surface(self._bg_surface.get_size())
        self._surface.set_colorkey((127,127,127))
        self._surface.fill((127,127,127))
        self._seconds_left = seconds
        self._surface.blit(text_texture, (20, 10))
        self.enable()

    def set_static_warning(self, text, color=(255, 255, 255)):
        self._static_warning_active = True
        text_texture = self._font_bigger.render(text, True, color)

        self._bg_surface = pygame.Surface((text_texture.get_width() + 140, text_texture.get_height() + 20))
        self._bg_surface.set_alpha(150)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_width()/2, 40)
        
        self._surface = pygame.Surface(self._bg_surface.get_size())
        self._surface.set_colorkey((127,127,127))
        self._surface.fill((127,127,127))
        self._seconds_left = 999999999
        self._surface.blit(text_texture, (70, 10))
        self._surface.blit(self._warning_image, (20, 10))
        self._surface.blit(self._warning_image, (text_texture.get_width() + self._warning_image.get_width() + 30, 10))
        self.enable()

    def remove_static_warning(self):
        self._static_warning_active = False
        self._seconds_left = 0

    def tick(self, clock):
        delta_seconds = 1e-3 * clock.get_time()
        if self._bg_surface and self._surface:
            self._seconds_left = max(0.0, self._seconds_left - delta_seconds)
            self._surface.set_alpha(500.0 * self._seconds_left)
            self._bg_surface.set_alpha(min(150, 500.0 * self._seconds_left))
        if self._seconds_left == 0:
            self.disable()

    def render(self, display):
        if self._render and self._surface and self._bg_surface:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surface, self._pos)

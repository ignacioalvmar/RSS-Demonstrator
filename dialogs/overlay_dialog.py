#!/usr/bin/env python

import pygame
# ==============================================================================
# -- OverlayDialog ------------------------------------------------------------------
# ==============================================================================

class OverlayDialog(object):
    def __init__(self, width, height):
        self._font_mono = pygame.font.Font('fonts/intelone-display-light.ttf', 14)
        self._font_mono_big = pygame.font.Font('fonts/intelone-display-light.ttf', 26)
        self.dim = (width, height)
        self.pos = (0,0)
        self._render = False
        self._logo = pygame.image.load("images/intellabs_logo_70.png")
        self.set_text("")

    def set_text(self, text):
        text_color = (255, 255, 255)
        self.surface = pygame.Surface(self.dim)
        self.surface.fill((0, 0, 0, 0))
        self.surface.blit(self._logo, (20, self.dim[1] - self._logo.get_height() - 20))
        self.text_surface = self._font_mono_big.render(text, True, text_color)
        self.surface.blit(self.text_surface, (self.dim[0]/2 - self.text_surface.get_rect().width/2, self.dim[1]/2 - self.text_surface.get_rect().height/2))

    def enable(self):
        self._render = True
        
    def disable(self):
        self._render = False

    def toggle(self):
        self._render = not self._render

    def render(self, display):
        if self._render:
            display.blit(self.surface, self.pos)

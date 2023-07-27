#!/usr/bin/env python

import pygame

class BaseDialog(object):
    def __init__(self, width, height):
        self._render = False
        self._screen_dim = (width, height)
        self._font_normal = pygame.font.Font('fonts/intelone-display-light.ttf', 22)
        self._font_big = pygame.font.Font('fonts/intelone-display-light.ttf', 26)
        self._font_bigger = pygame.font.Font('fonts/intelone-display-light.ttf', 36)
        self._font_huge = pygame.font.Font('fonts/intelone-display-light.ttf', 48)
        self._font_extrahuge = pygame.font.Font('fonts/intelone-display-light.ttf', 76)
    
    def blit_text(self, surface, text, pos, font, color=pygame.Color('white')):
        words = [word.split(' ') for word in text.splitlines()]  # 2D array where each row is a list of words.
        space = font.size(' ')[0]  # The width of a space.
        max_width, _ = surface.get_size()
        x, y = pos
        for line in words:
            for word in line:
                word_surface = font.render(word, True, color)
                word_width, word_height = word_surface.get_size()
                if x + word_width >= max_width:
                    x = pos[0]  # Reset the x.
                    y += word_height  # Start on new row.
                surface.blit(word_surface, (x, y))
                x += word_width + space
            x = pos[0]  # Reset the x.
            y += word_height  # Start on new row.

    def is_enabled(self):
        return self._render

    def enable(self):
        self._render = True
        
    def disable(self):
        self._render = False

    def toggle(self):
        self._render = not self._render

    def render(self, display):
        pass
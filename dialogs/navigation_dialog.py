#!/usr/bin/env python

import pygame

class NavigationDialog(object):
    def __init__(self):
        self._render = False
        self._surface_id = None
        self._image_surfaces = []

    def load_image(self, image, pos):
        surface = pygame.image.load(image)
        # dim = (surface.get_width(), surface.get_height())
        # surface = pygame.Surface(dim)
        # surface.set_colorkey(pygame.Color(127,127,127,255))
        # surface.blit(image, (0,0))
        surface.set_alpha(100)
        alpha = 160
        surface.fill((255, 255, 255, alpha), None, pygame.BLEND_RGBA_MULT)
        surface_id = len(self._image_surfaces)
        self._image_surfaces.append((surface, pos))
        return surface_id
    
    def enable(self, surface_id):
        self._surface_id = surface_id
        self._render = True
        
    def disable(self):
        self._surface_id = None
        self._render = False

    def toggle(self):
        self._render = not self._render

    def render(self, display):
        if self._render and self._surface_id != None:
            display.blit(self._image_surfaces[self._surface_id][0], self._image_surfaces[self._surface_id][1])
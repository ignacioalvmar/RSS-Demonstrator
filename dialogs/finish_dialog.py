#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog

class FinishDialog(BaseDialog):
    
    def __init__(self, width, height):
        super(FinishDialog, self).__init__(width, height)
        self.dim = (1000, 480)
        self.pos = (width/2 - self.dim[0]/2, height/2 - self.dim[1]/2)

        text_color = (255, 255, 255)
        self._bg_surface = pygame.Surface(self.dim)
        self._bg_surface.fill((0, 0, 0, 0))
        self._bg_surface.set_alpha(200)
        
        self._title_surface = self._font_big.render("CARLA RSS Demo", True, text_color)
        self._title_surface_pos = (width/2 - self._title_surface.get_width()/2, height/2 - self.dim[1]/2 + 30)

        self._carla_logo = pygame.image.load("images/carla-white-s.png")
        self._carla_logo_pos = (width/2 + self.dim[0]/2 - self._carla_logo.get_width() - 20, height/2 +  self.dim[1]/2 - self._carla_logo.get_width() - 20)
        
        self._rss_restrictions_surface = None
        self._rss_restrictions_surface_pos = (0,0)
        self.set_rss_restrictions("0")

        self._rss_link_surface = self._font_big.render("AD RSS Library: https://github.com/intel/ad-rss-lib/", True, (255, 255, 255))
        self._rss_link_surface_pos = (width/2 - self.dim[0]/2 + 20, height/2 - self.dim[1]/2 + 300)

        self._carla_link_surface = self._font_big.render("CARLA Simulator: http://carla.org/", True, (255, 255, 255))
        self._carla_link_surface_pos = (width/2 - self.dim[0]/2 + 20, height/2 - self.dim[1]/2 + 340)

    def set_rss_restrictions(self, text):
        self._rss_restrictions_surface = self._font_huge.render("RSS Restrictions Count: {}".format(text), True, (255, 255, 255))
        self._rss_restrictions_surface_pos = (self._screen_dim[0]/2 - self._rss_restrictions_surface.get_width()/2, self._screen_dim[1]/2 - self.dim[1]/2 + 150)

    def render(self, display):
        if self._render:
            display.blit(self._bg_surface, self.pos)
            #display.blit(self.surface, self.pos)
            display.blit(self._title_surface, self._title_surface_pos)
            display.blit(self._carla_logo, self._carla_logo_pos)
            display.blit(self._rss_restrictions_surface, self._rss_restrictions_surface_pos)
            display.blit(self._rss_link_surface, self._rss_link_surface_pos)
            display.blit(self._carla_link_surface, self._carla_link_surface_pos)

#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog

class LeftTheRoadDialog(BaseDialog):
    def __init__(self, width, height):
        super(LeftTheRoadDialog, self).__init__(width, height)
        
        dim = (800,520)
        self._bg_surface = pygame.Surface(dim)
        #self._bg_surface.blit(image, (0,0))
        self._bg_surface.set_alpha(200)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[0]/2, self._screen_dim[1]/2 - self._bg_surface.get_size()[1]/2)


        self._surface = pygame.Surface(dim)
        self._surface.set_colorkey(pygame.Color('black'))
        self.blit_text(self._surface, "You left the supported area.", (80,100), self._font_huge)

        btn_image = pygame.image.load("images/g29_button_small.png")
        btn_dim = (btn_image.get_width(), btn_image.get_height())
        btn_image_surface = pygame.Surface(btn_dim)
        btn_image_surface.set_colorkey(pygame.Color('black'))
        btn_image_surface.blit(btn_image, (0,0))
        self._surface.blit(btn_image_surface, (300,340))
        self.blit_text(self._surface, "Press", (200,370), self._font_bigger)
        self.blit_text(self._surface, "to continue.", (400,370), self._font_bigger)

    def render(self, display):
        if self._render:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surface, self._pos)
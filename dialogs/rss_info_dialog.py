#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog

class RssInfoDialog(BaseDialog):
    def __init__(self, width, height):
        super(RssInfoDialog, self).__init__(width, height)
        self._surface_id = None
        self._surfaces = []
        self._show_loading = False
        self._text_pos = 20

        self._bg_surface = pygame.Surface((1000,520))
        self._bg_surface.fill((0, 0, 0, 0))
        self._bg_surface.set_alpha(200)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[0]/2, self._screen_dim[1]/2 - self._bg_surface.get_size()[1]/2)

        self._loading_surface = None
        self._loading_pos = (0,0)
        self._start_button_surface = None 
        self._start_button_pos = (0,0)
        self.show_loading(False)

    def load_content(self, image, text, text_pos):
        surface = pygame.Surface(self._bg_surface.get_size())
        surface.set_colorkey(pygame.Color('black'))
        image = pygame.image.load(image)
        dim = (image.get_width()+2, image.get_height()+2)
        image_surface = pygame.Surface(dim)
        image_surface.set_colorkey(pygame.Color('black'))
        image_surface.fill((255, 255, 255, 0))
        image_surface.blit(image, (1,1))
        surface.blit(image_surface, (498,28))

        text_surface = pygame.Surface((460,460))
        text_surface.set_colorkey(pygame.Color('black'))
        self.blit_text(text_surface, text, (1,1), self._font_huge)
        self._text_pos = text_pos
        surface.blit(text_surface, text_pos)

        surface_id = len(self._surfaces)
        self._surfaces.append((surface, self._pos))
        return surface_id
    
    def show_loading(self, val, text="Loading..."):
        self._show_loading = val
        if val:
            self._loading_surface = self._font_bigger.render(text, True, (255,255,255))
            self._loading_pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[0]/2 + self._text_pos[0], self._screen_dim[1]/2 + self._bg_surface.get_size()[1]/2 - self._loading_surface.get_size()[1]  - 80)
        else:
            self._start_button_surface = pygame.Surface((420,100))
            self._start_button_surface.set_colorkey(pygame.Color('black'))
            self._start_button_pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[1]/2 - self._start_button_surface.get_size()[0]/2 + 10, self._screen_dim[1]/2 + self._bg_surface.get_size()[1]/2 - self._start_button_surface.get_size()[1]  - 50)
            btn_image = pygame.image.load("images/g29_button_small.png")
            btn_dim = (btn_image.get_width(), btn_image.get_height())
            btn_image_surface = pygame.Surface(btn_dim)
            btn_image_surface.set_colorkey(pygame.Color('black'))
            btn_image_surface.blit(btn_image, (0,0))
            self._start_button_surface.blit(btn_image_surface, (100,0))
            self.blit_text(self._start_button_surface, "Press", (0,30), self._font_bigger)
            self.blit_text(self._start_button_surface, "to continue.", (200,30), self._font_bigger)


    def enable_id(self, surface_id):
        self._surface_id = surface_id
        self.enable()

    def render(self, display):
        if self._render and self._surface_id != None:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surfaces[self._surface_id][0], self._surfaces[self._surface_id][1])

            if self._show_loading:
                if self._loading_surface:
                    display.blit(self._loading_surface, self._loading_pos)
            else:
                if self._start_button_surface:
                    display.blit(self._start_button_surface, self._start_button_pos)
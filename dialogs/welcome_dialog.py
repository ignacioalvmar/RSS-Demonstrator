#!/usr/bin/env python

import pygame
from base_dialog import BaseDialog

class WelcomeDialog(BaseDialog):
    def __init__(self, width, height):
        super(WelcomeDialog, self).__init__(width, height)
        self._show_loading = True
        #image = pygame.image.load("images/bg.png")
        #dim = (image.get_width()+2, image.get_height()+2)
        dim = (1200,500)
        self._bg_surface = pygame.Surface(dim)
        #self._bg_surface.blit(image, (0,0))
        self._bg_surface.set_alpha(200)
        self._pos = (self._screen_dim[0]/2 - self._bg_surface.get_size()[0]/2, self._screen_dim[1]/2 - self._bg_surface.get_size()[1]/2)

        self._surface = pygame.Surface(dim)
        self._surface.set_colorkey(pygame.Color('black'))

        # self._logo = pygame.image.load("images/intellabs_logo_70.png")
        # self._surface.blit(self._logo, (dim[0]/2 - self._logo.get_width()/2, 20))

        word_surface = self._font_huge.render("Demonstration", True, (255,255,255))
        self._surface.blit(word_surface, (dim[0]/2 - word_surface.get_width()/2, 105))
        word_surface = self._font_big.render("of", True, (255,255,255))
        self._surface.blit(word_surface, (dim[0]/2 - word_surface.get_width()/2, 160))
        word_surface = self._font_huge.render("Responsibility Sensitive Safety", True, (255,255,255))
        self._surface.blit(word_surface, (dim[0]/2 - word_surface.get_width()/2, 190))
        word_surface = self._font_big.render("An open, transparent, technology neutral safety model for autonomous driving", True, (255,255,255))
        self._surface.blit(word_surface, (dim[0]/2 - word_surface.get_width()/2, 260))

        self.show_loading(False)
    
    def show_loading(self, val, text="Loading..."):
        self._show_loading = val
        if val:
            self._loading_surface = self._font_bigger.render(text, True, (255,255,255))
            self._loading_pos = (self._screen_dim[0]/2 - self._loading_surface.get_size()[0]/2, self._screen_dim[1]/2 + self._bg_surface.get_size()[1]/2 - self._loading_surface.get_size()[1]  - 50)
        else:
            self._start_button_surface = pygame.Surface((340,100))
            self._start_button_surface.set_colorkey(pygame.Color('black'))
            self._start_button_pos = (self._screen_dim[0]/2 - self._start_button_surface.get_size()[0]/2, self._screen_dim[1]/2 + self._bg_surface.get_size()[1]/2 - self._start_button_surface.get_size()[1]  - 50)
            btn_image = pygame.image.load("images/g29_button_small.png")
            btn_dim = (btn_image.get_width(), btn_image.get_height())
            btn_image_surface = pygame.Surface(btn_dim)
            btn_image_surface.set_colorkey(pygame.Color('black'))
            btn_image_surface.blit(btn_image, (0,0))
            self._start_button_surface.blit(btn_image_surface, (100,0))
            self.blit_text(self._start_button_surface, "Press", (10,30), self._font_bigger)
            self.blit_text(self._start_button_surface, "to start.", (200,30), self._font_bigger)

    def render(self, display):
        if self._render:
            display.blit(self._bg_surface, self._pos)
            display.blit(self._surface, self._pos)
            if self._show_loading:
                display.blit(self._loading_surface, self._loading_pos)
            else:
                display.blit(self._start_button_surface, self._start_button_pos)

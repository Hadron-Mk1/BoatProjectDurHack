"""
The background terrain used for the program
"""
import pygame
from AnimatedBackground import AnimatedBackground

class Terrain(AnimatedBackground):
    """
    Defines a background that can be used for the program with the number of animation frames available
    """
    def __init__(self):
        super().__init__()
        self.image_one = pygame.image.load('graphics/terrain1.png').convert_alpha()
        self.image_two = pygame.image.load('graphics/terrain2.png').convert_alpha()
        self.image_three = pygame.image.load('graphics/terrain3.png').convert_alpha()
        self.image_four = pygame.image.load('graphics/terrain4.png').convert_alpha()
        self.image_five = pygame.image.load('graphics/terrain5.png').convert_alpha()
        self.image_six = pygame.image.load('graphics/terrain6.png').convert_alpha()
        self.animation_image_quant = 6
        self.terrain_animation_images = [self.image_one, self.image_two,self.image_three,self.image_four,
                                         self.image_five,self.image_six]
        self.image = self.image_one
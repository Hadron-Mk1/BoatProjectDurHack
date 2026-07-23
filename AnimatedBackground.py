"""
Super class used by any animated background
"""

import pygame

class AnimatedBackground:
    """
    Super class used to set up the animated backgrounds animation; by default animation is only 2 images
    """
    def __init__(self):
        self.frame_index = 0
        self.frame_timer = 0
        self.image_one = pygame.image.load('graphics/terrain1.png').convert_alpha()
        self.image_two = pygame.image.load('graphics/terrain2.png').convert_alpha()
        self.animation_image_quant = 2
        self.terrain_animation_images = [self.image_one, self.image_two]
        self.image = self.image_one

    def animate(self):
        """
        Switches the displayed animation image
        """
        self.frame_timer += 1
        self.image = self.terrain_animation_images[self.frame_index]

        if self.frame_timer >= 10:
            self.frame_timer = 0
            self.frame_index = (self.frame_index + 1) % len(self.terrain_animation_images)
        return self.image

    def update_size(self, width, height):
        """
        Alters the size of the animated background
        :param width: New width to set
        :param height: New height to set
        """
        for image_count in range(self.animation_image_quant):
            self.terrain_animation_images[image_count] = pygame.transform.scale(
                                                       self.terrain_animation_images[image_count], (width, height))
        self.image = self.terrain_animation_images[self.frame_index]
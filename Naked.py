"""
Clothing object used by 'person'
"""
import pygame
from Clothing import Clothing

class Naked(Clothing):
    """
    A 'Naked' clothing item applied to a Person that increases the confidence score by 0 and tracks the total
    number of Naked instances created.
    """
    count = 0

    def __init__(self, person_tracking, person_start_x, person_start_y):

        super().__init__(person_tracking, person_start_x, person_start_y)

        self.clothes_image = pygame.image.load('clothes/naked.png').convert_alpha()
        self.clothes_image = pygame.transform.scale(self.clothes_image, (110,110))
        self.person_tracking = person_tracking
        self.confidence_addition = 0

        Naked.count += 1
        Clothing.hat_list[self.give_name()] = Naked.count

    def copy(self):
        naked = Naked(self.person_tracking, self.x_trace,self.y_trace)
        naked.clothes_image = self.clothes_image.copy()
        return naked

    @classmethod
    def give_name(cls):
        return "Naked"
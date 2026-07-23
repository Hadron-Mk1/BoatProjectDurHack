"""
Clothing object used by 'person'
"""
import pygame

from Clothing import Clothing


class Tophat(Clothing):
    """
    A Top hat clothing item applied to a Person that increases the confidence score by 10 and tracks the total
    number of Top hat instances created.
    """
    count = 0
    def __init__(self, person_tracking, person_start_x, person_start_y):

        super().__init__(person_tracking, person_start_x, person_start_y)

        self.clothes_image = pygame.image.load('clothes/tophat.png').convert_alpha()
        self.clothes_image = pygame.transform.scale(self.clothes_image, (110,110))
        self.person_tracking = person_tracking
        self.confidence_addition = 10

        Tophat.count +=1
        Clothing.hat_list[self.give_name()] = Tophat.count

    def copy(self):
        tophat = Tophat(self.person_tracking, self.x_trace,self.y_trace)
        tophat.clothes_image = self.clothes_image.copy()
        return tophat

    @classmethod
    def give_name(cls):
        return "Top hats"


"""
Clothing object used by 'person'
"""
import pygame

from Clothing import Clothing


class CowboyHat(Clothing):
    """
    A Cowboy hat clothing item applied to a Person that increases the confidence score by 15 and tracks the total
    number of Cowboy hat instances created.
    """

    count = 0

    def __init__(self, person_tracking, person_start_x, person_start_y):

        super().__init__(person_tracking, person_start_x, person_start_y)

        self.clothes_image = pygame.image.load('clothes/cowboy_hat.png').convert_alpha()
        self.clothes_image = pygame.transform.scale(self.clothes_image, (110,110))
        self.person_tracking = person_tracking
        self.confidence_addition = 15

        CowboyHat.count += 1
        Clothing.hat_list[self.give_name()] = CowboyHat.count

    def copy(self):
        cowboy_hat = CowboyHat(self.person_tracking, self.x_trace,self.y_trace)
        cowboy_hat.clothes_image = self.clothes_image.copy()
        return cowboy_hat

    @classmethod
    def give_name(cls):
        return "Cowboy hats"


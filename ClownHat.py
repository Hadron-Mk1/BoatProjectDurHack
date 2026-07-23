"""
Clothing object used by 'person'
"""
import pygame

from Clothing import Clothing


class ClownHat(Clothing):
    """
    A Clown hat clothing item applied to a Person that increases the confidence score by 13 and tracks the total
    number of Clown Hat instances created.
    """
    count = 0

    def __init__(self, person_tracking, person_start_x, person_start_y):

        super().__init__(person_tracking, person_start_x, person_start_y)


        self.clothes_image = pygame.image.load('clothes/clown_hat.png').convert_alpha()
        self.clothes_image = pygame.transform.scale(self.clothes_image, (110,110))
        self.person_tracking = person_tracking
        self.confidence_addition = 13

        ClownHat.count += 1
        Clothing.hat_list[self.give_name()] = ClownHat.count

    def copy(self):
        clown_hat = ClownHat(self.person_tracking, self.x_trace,self.y_trace)
        clown_hat.clothes_image = self.clothes_image.copy()
        return clown_hat

    @classmethod
    def give_name(cls):
        return "Clown Hats"


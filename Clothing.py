"""
Clothing super class used by all clothing types
"""
import pygame

#39x40 grid center should be 19:13 piskel
class Clothing:
    """
    Clothing class used by all clothing types, by default sets initial hat list for future use and sets clothes image
    to none
    """

    hat_list = {}
    def __init__(self, person_tracking,person_start_x,person_start_y,clothes_image = None):

        if clothes_image is None:
            self.clothes_image =None

        self.x_trace = person_start_x
        self.y_trace = person_start_y

        self.clothes_image_location = pygame.Rect(self.x_trace, self.y_trace, 20, 20)
        self.person_tracking = person_tracking
        Clothing.hat_list["Naked"] = 0

    def update_clothing_head(self,new_x,new_y,coord_fix):
        """
        Adjusts where the next piece of clothing should be placed
        :param new_x: New x coordinate
        :param new_y: New y coordinate
        :param coord_fix: x and y coordinate fixes
        """
        self.x_trace = new_x
        self.y_trace = new_y
        self.clothes_image_location = (self.x_trace + coord_fix[0],self.y_trace + coord_fix[1])

    def draw_clothes(self,screen,coord_fix):
        """
        Draws the clothes at the current location using internal coordinates
        :param screen: Screen to draw on
        :param coord_fix Coordinate adjustment due to different possible character models
        """
        self.update_clothing_head(self.x_trace,self.y_trace, coord_fix)
        screen.blit(self.clothes_image, self.clothes_image_location)
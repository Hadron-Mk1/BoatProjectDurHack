"""
A possible 'person' that can be chosen in the simulation
"""
from Person import *

lucy_list = []
class Lucy(Person):
    """
    Adds a person to the lucy_list and generates the hitbox,speed,animation,images and confidence score for that person
    """
    def __init__(self, width_in, height_in):

        super().__init__(width_in, height_in)

        self.hitbox = pygame.Rect(self.x + 25, self.y, 55, 50)
        self.hitbox.topleft = (self.x, self.y)
        # Hitbox must match png
        self.hitbox_edit = [5,15]
        # How 'off center' the hat png is from the head of the characters in coords
        self.head_coord_fix = [-25, -5]
        self.speed = 0.8

        self.walk_animation_images = create_image_setup_walk(self,[60,60])
        self.talking_animation_images = create_image_setup_talk(self,[60,60])

        self.frame_index = 0
        self.frame_timer = 0

        self.self_confidence = int(random.randrange(20,80))
        if self.clothing is None:
            self.clothes_confidence = 0
        else:
            self.clothes_confidence = self.clothing.confidence_addition
        self.total_confidence = self.clothes_confidence + self.self_confidence

        lucy_list.append(self)

    def animate(self):
        self.frame_timer += 1
        if self.frame_timer >= 15:
            self.frame_timer = 0

            if self.talking_to_who is not None:
                self.frame_index = (self.frame_index + 1) % len(self.talking_animation_images)
                self.image = self.talking_animation_images[self.frame_index]
            else:
                self.frame_index = (self.frame_index + 1) % len(self.walk_animation_images)
                self.image = self.walk_animation_images[self.frame_index]
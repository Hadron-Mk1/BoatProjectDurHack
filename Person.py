"""
Super class used for all 'people'
"""
import random
import time
import pygame
from collections import defaultdict

from CowboyHat import CowboyHat
from ClownHat import ClownHat
from Naked import Naked
from Tophat import Tophat
from GoldenTophat import GoldenTophat

#Initial values each 'person' will assume the screen dimensions are
person_width = 700
person_height = 600
#Initial screen for tasks such as drawing the 'characters'
screen = pygame.display.set_mode((person_width, person_height))

person_width = person_height = 0
people_list = []

grid = defaultdict(list)
grid_box_size = 150
#png created on 40x40 grid piskel
class Person:
    """
    Super class used by all 'people'; initializes any variables not altered by other 'people' and sets a start position,
    starting path, starting velocity, etc. Appends each person to person_list and assigns a clothing item at random
    """
    def __init__(self, person_width_in, person_height_in):

        global person_width, person_height
        person_width, person_height = person_width_in, person_height_in

        initial_velocity = [random.randrange(0, 4) + 1, random.randrange(0, 4) + 1]
        self.velocity = initial_velocity.copy()
        self.restoration_velocity = initial_velocity.copy()
        self.direction = [-1, -1]
        self.hitbox_edit = [0,0]
        self.path = [0,0]
        self.speed_stat = 1

        self.talking = 0
        self.cooldown = True
        self.talking_to_who = None
        self.last_person = None

        self.walking_animation = [None]*2
        self.cooldown_animation = [None]*2
        self.talking_animation = [None]*4

        x_start = random.randrange(0, person_width - int(person_width/15))
        y_start = random.randrange(0, person_height - int(person_height/9))
        self.x = x_start
        self.y = y_start
        self.speed_multiplier = 1

        self.random_pick_clothing()
        self.hitbox = pygame.Rect(self.x, self.y , 30, 80)
        self.hitbox.topleft = (self.x, self.y)

        self.frame_index = 0
        self.frame_timer = 0
        self.hitbox_edit = [0,0]
        people_list.append(self)


    def move(self,x_hitbox_edit, y_hitbox_edit,sped_up,paused):
        """
        :param x_hitbox_edit: x coordinate to move to
        :param y_hitbox_edit: y coordinate to move to
        :param sped_up: Speed of simulation
        :param paused: If game is paused
        """
        self.find_direction(x_hitbox_edit,y_hitbox_edit)

        if sped_up:
            game_speed = 2
        else:
            game_speed = 1

        if paused:
            self.velocity[0]= self.velocity[1] = 0
            self.talking_to_who = None
            self.cooldown = False
        elif self.velocity[0] == 0 and self.velocity[1] == 0 and not paused and self.talking_to_who is None :
            self.velocity = self.restoration_velocity.copy()

        if self.direction[0] == 0:
            self.x += self.velocity[0] * game_speed * self.speed_stat
        elif self.direction[0] < 0:
            self.x -= self.velocity[0]* game_speed * self.speed_stat

        if self.direction[1] == 0:
            self.y += self.velocity[1] * game_speed * self.speed_stat
        elif self.direction[1] < 0:
            self.y -= self.velocity[1] * game_speed * self.speed_stat

        self.clothing.update_clothing_head(self.x, self.y,[0,0])


    def check_path_change(self, width_in, height_in):
        """
        Checks to see if the path of the 'person' should be changed due to an edit in terrain size
        :param width_in: Width of the screen
        :param height_in: Height of the screen
        :return: True if the path of the 'person' should be changed
        """
        global person_width, person_height

        if width_in != person_width or height_in != person_height:
            self.find_direction(self.hitbox_edit[0],self.hitbox_edit[1])
            person_width = width_in
            person_height = height_in
            return True
        else:
            return False


    def find_direction(self,x_hitbox_edit,y_hitbox_edit):
        """
        Changes the direction of the 'person' and if a path is complete generates a new one
        :param x_hitbox_edit: x coordinate to move to
        """
        global person_width, person_height

        self.hitbox.topleft = (self.x + x_hitbox_edit, self.y+y_hitbox_edit)
        new_path_x = True
        new_path_y = True
        #pygame.draw.rect(screen, (255, 255, 255), self.hitbox)

        if self.direction[0] == 0 and self.x >= self.path[0]:
            self.direction[0] = -1
        elif self.direction[0] < 0 and self.x <= self.path[0]:
            self.direction[0] = 0
        else:
            new_path_x = False

        if self.direction[1] == 0 and self.y >= self.path[1]:
            self.direction[1] = -1
        elif self.direction[1] < 0 and self.y <= self.path[1]:
            self.direction[1] = 0
        else:
            new_path_y = False

        #If the path is finished in either dimension a new path should be made
        if new_path_x:
            self.path = [random.randrange(int(person_width/40), person_width - int(person_width/20)), self.path[1]]

        if new_path_y:
            self.path = [self.path[0], random.randrange(int(person_height/30), person_height -  int(person_height/10))]


    def random_pick_clothing(self):
        """
        Randomly assigns clothing based on a number from 1 to 100
        """
        random_number = random.randint(1, 100)

        if random_number == 100:
            self.clothing = GoldenTophat(self,self.x,self.y)
        elif random_number >= 80:
            self.clothing = Tophat(self,self.x, self.y)
        elif random_number >= 60:
            self.clothing = ClownHat(self,self.x, self.y)
        elif random_number >= 40:
            self.clothing = CowboyHat(self, self.x, self.y)
        else:
            self.clothing = Naked(self,self.x, self.y)


def talk(instanced_people_one, instanced_people_two):
    """
    Checks to see whether two 'people' should begin talking and begins the talking phase
    :param instanced_people_one: 'person' one
    :param instanced_people_two: 'person' two
    """
    if instanced_people_one.talking_to_who is None and instanced_people_two.talking_to_who is None:
        should_talk = True
        talk_core_code(instanced_people_one, instanced_people_two, should_talk)
    elif instanced_people_one.talking_to_who is not None or instanced_people_two.talking_to_who is not None:
        should_talk = False
        talk_core_code(instanced_people_one, instanced_people_two, should_talk)


def talk_core_code(instanced_people_one, instanced_people_two, should_talk):
    """
    Checks to see whether two 'people' should begin talking and begins the talking phase if so
    Determines if the 'people' should enter a cooldown state not allowing conversation.
    Edits the displayed png to reflect if the 'person' is talking or not while setting velocity to 0 if they begin conversation

    :param instanced_people_one: 'person' one
    :param instanced_people_two:  'person' two
    :param should_talk: Whether the 'people' should engage
    """

    both_cooldown = instanced_people_one.cooldown and instanced_people_two.cooldown
    #Whoever has the longer talking time should be chosen to prevent premature one-sided finishing in the conversation
    timer_trigger = max(instanced_people_one.talking, instanced_people_two.talking)

    #No back-to-back conversation can happen with the same two people
    if (instanced_people_one.hitbox.colliderect(instanced_people_two.hitbox) and should_talk and both_cooldown and
       (instanced_people_one.last_person != instanced_people_two or instanced_people_two.last_person != instanced_people_one)):

        instanced_people_one.talking_to_who = instanced_people_two
        instanced_people_two.talking_to_who = instanced_people_one
        instanced_people_one.last_person = instanced_people_two
        instanced_people_two.last_person = instanced_people_one

        instanced_people_one.image = instanced_people_one.talking_animation[0]
        instanced_people_two.image = instanced_people_two.talking_animation[0]
        trade_clothes(instanced_people_one, instanced_people_two)

        instanced_people_one.cooldown = instanced_people_two.cooldown = False
        #They should stop moving as they are talking
        instanced_people_one.velocity = [0, 0]
        instanced_people_two.velocity = [0, 0]

        instanced_people_one.talking = instanced_people_two.talking = time.time()

    # If they can now talk again and 3 seconds has passed
    elif should_talk and time.time() >= timer_trigger + 3:
        instanced_people_one.image = instanced_people_one.walking_animation[0]
        instanced_people_two.image = instanced_people_two.walking_animation[0]
        instanced_people_one.cooldown = instanced_people_two.cooldown = True
        instanced_people_one.talking = instanced_people_two.talking = time.time()

    #Wait 2 seconds before allowing conversation to begin again
    elif not should_talk and time.time() >= timer_trigger + 2:
        instanced_people_one.velocity = instanced_people_one.restoration_velocity.copy()
        instanced_people_two.velocity = instanced_people_two.restoration_velocity.copy()

        instanced_people_one.talking_to_who = None
        instanced_people_two.talking_to_who = None


def trade_clothes(person_one, person_two):
    """
    Chooses the 'person' with the highest confidence between the two and the loser gets the winners clothes
    :param person_one: Person one
    :param person_two: Person two
    """
    if person_one.total_confidence < person_two.total_confidence:
        person_one.clothing.__class__.count -= 1
        person_two.clothing.__class__.count += 1

        person_one.total_confidence += person_two.clothes_confidence - person_one.clothes_confidence
        person_one.clothes_confidence = person_two.clothes_confidence
        person_one.clothing = person_two.clothing

    elif person_one.total_confidence > person_two.total_confidence:
        person_one.clothing.__class__.count += 1
        person_two.clothing.__class__.count -= 1

        person_two.total_confidence += person_one.clothes_confidence - person_two.clothes_confidence
        person_two.clothes_confidence = person_one.clothes_confidence
        person_two.clothing = person_one.clothing


def create_image_setup_walk(name,dimension):
    """
    sets up the walking animations to be used in program
    :param name: name of the 'person'
    :param dimension: dimensions of 'person'
    :return: animation images in an array
    """
    name_obj = name
    name = name_obj.__class__.__name__.lower()

    name_obj.image = pygame.image.load('characters/'+name+'_walking1.png').convert_alpha()
    name_obj.walking_animation[0] = pygame.transform.scale(name_obj.image, (dimension[0], dimension[1]))

    name_obj.image = pygame.image.load('characters/'+name+'_walking2.png').convert_alpha()
    name_obj.walking_animation[1] = pygame.transform.scale(name_obj.image, (dimension[0], dimension[1]))

    return [name_obj.walking_animation[0], name_obj.walking_animation[1]]


def create_image_setup_talk(name,dimension):
    """
    sets up the talking animations to be used in program
    :param name: name of the 'person'
    :param dimension: dimensions of 'person'
    :return: animation images in an array
    """
    name_obj = name
    name = name_obj.__class__.__name__.lower()

    name_obj.image = pygame.image.load('characters/' + name + '_talking1.png').convert_alpha()
    name_obj.talking_animation[0] = pygame.transform.scale(name_obj.image, (dimension[0], dimension[1]))

    name_obj.image = pygame.image.load('characters/' + name + '_talking2.png').convert_alpha()
    name_obj.talking_animation[1] = pygame.transform.scale(name_obj.image, (dimension[0], dimension[1]))

    return [name_obj.talking_animation[0], name_obj.talking_animation[1]]


def update_grid_and_collisions():
    """
    Creates and destroys a grid to allow for more efficient optimisation of which 'people' each 'person' must check
    """

    grid.clear()

    for person in people_list:
        cell_x = person.x // grid_box_size
        cell_y = person.y // grid_box_size
        grid[(cell_x, cell_y)].append(person)

    #Ensure 'people' only need to check other 'people' in the same grid
    for people in grid.values():
        for i in range(len(people)):
            for j in range(i + 1, len(people)):
                talk(people[i], people[j])

def animate():
    """
    Used by all 'people' objects to create custom animations
    """
    pass

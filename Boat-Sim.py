"""
Main file that runs program

Used for:
pygame initialization
player input
character generation
rendering
game completion logic
"""

import math
from Clothing import Clothing
from Person import *
from Bobby import Bobby
from Lucy import Lucy
from Peter import Peter
from Marika import Marika
from Terrain import Terrain
import os
import pygame
import sys

pygame.init()
pygame.display.set_caption("Whats he wearing?")
max_frame_clock = pygame.time.Clock()
fullscreen_bordered = False
fullscreen_borderless = False

pygame.font.init()

text_size = 50
font = pygame.font.SysFont("Arial", text_size)
width = 700
height = 600
button_width = width / 9
button_height = height / 7
size = pygame.display.Info()

#Background
test_surface = Terrain()
test_surface.update_size(width, height)

#Set and convert all needed images
generating_screen = pygame.image.load('graphics/generating_screen.png').convert()
bobby_question_screen = pygame.image.load('graphics/select_char_bobby_texture.png').convert()
lucy_question_screen = pygame.image.load('graphics/select_char_lucy_texture.png').convert()
peter_question_screen = pygame.image.load('graphics/select_char_peter_texture.png').convert()
marika_question_screen = pygame.image.load('graphics/select_char_marika_texture.png').convert()

screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)

generating_word_timer = time.time()
random_word = ""


def generate(person_type, amount_in):
    """
    Generates the specific number of a 'person' type while displaying screen that generation is occurring
    :param person_type: The type of 'person' to generate
    :param amount_in: Amount wanted to be generated
    """
    global number_to_gen, number_of_person, generating_word_timer, random_word

    for amount in range(0, amount_in):
        person_type(screen.get_width(), screen.get_height())

        set_generating_screen()
        number_rect = pygame.Rect(0, 0, screen.get_width(), screen.get_height())

        number = random.randint(0, 10)
        #To enhance the generating screen random words are placed in
        if generating_word_timer + 1 < time.time():
            if number <= 2:
                random_word = "Sit tight"
            elif number <= 4:
                random_word = "Thinking"
            elif number <= 6:
                random_word = "Creating"
            else:
                random_word = "Generating"
            generating_word_timer = time.time()

        text = font.render(random_word, True, (255, 255, 255))
        text_box = text.get_rect()
        text_box.center = number_rect.center
        screen.blit(text, text_box)
        pygame.display.update()


def generate_remaining_half_odd_or_even(person, number_to_gen_in):
    """
    Used to find the necessary number of 'people' left to generate as odd or even and then generate that amount
    :param person: The 'person' you want to generate
    :param number_to_gen_in: The amount of 'people' to generate
    """
    if number_to_gen_in % 2 != 0:
        generate(person, int(number_to_gen_in / 2 + 1))
    else:
        generate(person, int(number_to_gen_in / 2))


def generate_with_sprite_correction():
    """
    Uses previous generation methods to generate 'people' but in a way to allow for png layers to appear mixed
    """
    global number_to_gen_bobby, number_to_gen_lucy, number_to_gen_peter, number_to_gen_marika

    #Split to allow the PNGs to be 'shuffled' and give a more immersive illusion
    generate(Bobby, int(number_to_gen_bobby / 2))
    generate(Lucy, int(number_to_gen_lucy / 2))
    generate(Peter, int(number_to_gen_peter / 2))
    generate(Marika, int(number_to_gen_marika / 2))

    generate_remaining_half_odd_or_even(Bobby, int(number_to_gen_bobby))
    generate_remaining_half_odd_or_even(Lucy, int(number_to_gen_lucy))
    generate_remaining_half_odd_or_even(Peter, int(number_to_gen_peter))
    generate_remaining_half_odd_or_even(Marika, int(number_to_gen_marika))


def toggle_fullscreen(border):
    """
    Alters the size of the terrain to allow for intricate png interaction
    :param border: The terrain chosen to alter
    """
    global screen, test_surface, size
    #I increase the actual available screen space so fullscreen will not work
    pygame.display.quit()
    pygame.display.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0," + str(border) + ""
    screen = pygame.display.set_mode((0, 0), pygame.RESIZABLE)
    test_surface.update_size(screen.get_width(), screen.get_height())


def toggle_minimise():
    """
    Minimizes the screen
    """
    global screen, test_surface, size
    #Forcing the minimised window to appear in the centre of the screen
    pygame.display.quit()
    pygame.display.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "center"
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    test_surface.update_size(screen.get_width(), screen.get_height())


def check_borders():
    """
    Checks the state of the screen and alters boolean values to reflect screen change
    """
    global fullscreen_bordered, fullscreen_borderless
    if fullscreen_bordered:
        if fullscreen_borderless:
            fullscreen_bordered = False
    elif fullscreen_borderless:
        if fullscreen_bordered:
            fullscreen_bordered = False
    else:
        fullscreen_bordered = False
        fullscreen_borderless = False


def update_displayed_number():
    """
    Updates the displayed generation number of the specific 'person'
    """
    global number_to_gen, number_of_person
    number_as_string = ""
    for character in number_of_person:
        number_as_string += character
    number_to_gen = number_as_string


def ask_how_many(person):
    """
    Displays a screen asking how many of that 'person' you would like to generate
    """
    global bobby_question_screen, lucy_question_screen, marika_question_screen, peter_question_screen

    screen_height = screen.get_height()
    screen_width = screen.get_width()
    number_rect = pygame.Rect(0, 0, screen_width, screen.get_height())

    if person.lower() == "bobby":
        bobby_question_screen = pygame.transform.scale(bobby_question_screen, (screen_width, screen_height))
        screen.blit(bobby_question_screen, (0, 0))
    elif person.lower() == "lucy":
        lucy_question_screen = pygame.transform.scale(lucy_question_screen, (screen_width, screen_height))
        screen.blit(lucy_question_screen, (0, 0))
    elif person.lower() == "peter":
        peter_question_screen = pygame.transform.scale(peter_question_screen, (screen_width, screen_height))
        screen.blit(peter_question_screen, (0, 0))
    elif person.lower() == "marika":
        marika_question_screen = pygame.transform.scale(marika_question_screen,(screen_width, screen_height))
        screen.blit(marika_question_screen, (0, 0))

    text_num = font.render(str(number_to_gen), True, (255, 255, 255))
    text_box_num = text_num.get_rect()
    text_box_num.center = number_rect.center
    if fullscreen_bordered or fullscreen_borderless:
        text_box_num.centerx -= int(screen_height / 3)
    else:
        text_box_num.centerx -= int(screen_width / 4.5)
    screen.blit(text_num, text_box_num)


def set_loading_screen():
    """
    Displays the loading screen and the current screen width and height
    """
    global loading_screen
    loading_screen = pygame.transform.scale(loading_screen, (screen.get_width(), screen.get_height()))
    screen.blit(loading_screen, (0, 0))


def set_generating_screen():
    """
    Displays the generating screen and the current screen width and height
    """
    global generating_screen
    generating_screen = pygame.transform.scale(generating_screen, (screen.get_width(), screen.get_height()))
    screen.blit(generating_screen, (0, 0))


def show_end_screen(clothing):
    """
    Shows the end winning screen
    """
    screen_w = screen.get_width()
    temp_font = pygame.font.SysFont("Arial", int(screen_w / 10), True)
    text = temp_font.render("Thanks for playing!", True, (255, 255, 255))
    text_box = text.get_rect()
    text_box.centerx = int(screen_w / 2)
    text_box.centery = int(screen.get_height() / 3)
    screen.blit(text, text_box)

    temp_font = pygame.font.SysFont("Arial", int(screen_w / 15), True)
    text = temp_font.render(clothing.__class__.give_name() + " Won!", True, (255, 255, 255))
    text_box = text.get_rect()
    text_box.centerx = int(screen_w / 2)
    text_box.centery = int(screen.get_height() / 2)
    screen.blit(text, text_box)


first_pass_for_hats = True
hats_to_update = [Tophat, GoldenTophat, ClownHat, CowboyHat, Naked]
def show_amount_of_hats():
    """
    Shows the number of current hats on the screen
    """
    global first_pass_for_hats
    global show_hats
    temp_font = pygame.font.SysFont("Arial", 25, True)

    #Only show the hats you had to start with
    if first_pass_for_hats:
        for hats in hats_to_update:
            if hats.count == 0:
                hats_to_update.remove(hats)
        first_pass_for_hats = False

    if not show_hats:
        text = temp_font.render("Press Tab to show stats and F for fullscreen!", True, (0, 0, 0))
        text_box = text.get_rect()
        text_box.x = 40
        if fullscreen_bordered and not fullscreen_borderless:
            text_box.bottom = screen.get_height() - text_box.height
        else:
            text_box.bottom = screen.get_height()
        screen.blit(text, text_box)
    else:
        for hats in hats_to_update:
            Clothing.hat_list[hats.give_name()] = hats.count

        indent = 170
        for hats in hats_to_update:
            text = temp_font.render(hats.give_name() + ": " + str(hats.count), True, hat_colours[hats])
            text_box = text.get_rect()
            text_box.y = indent
            indent += text_box.height + 20

        indent -= 20
        pygame.draw.rect(screen, (242,240,239), (10, 10, 220, indent))
        pygame.draw.rect(screen, (0, 0, 0), (10, 10, 220, indent), 2)

        indent = 170
        for hats in hats_to_update:
            text = temp_font.render( hats.give_name() + ": " +str(hats.count), True, hat_colours[hats])
            text_box = text.get_rect()
            text_box.y = indent
            text_box.x = 20

            screen.blit(text, text_box)
            indent += text_box.height + 20


def fill_arc(screen_in, center, radius, start_angle, end_angle, color):
    """
    Fills in the colours for the arc
    :param screen_in: Screen to draw on
    :param center: Centre of the arc
    :param radius: Radius of the arc
    :param start_angle: Start angle of the arc
    :param end_angle: End angle of the arc
    :param color: Colour of the arc to fill in
    """
    points = [center]

    steps = 50
    for index in range(steps + 1):
        angle = start_angle + (end_angle - start_angle) * index / steps

        x_point = center[0] + math.cos(angle) * radius
        y_point = center[1] + math.sin(angle) * radius

        points.append((x_point, y_point))

    pygame.draw.polygon(screen_in, color, points)


hat_colours = {Naked: (162,87,79),Tophat: (0,0,128),GoldenTophat: (218,165,32),ClownHat: (99,149,238),
CowboyHat: (136,45,23)}
def generate_and_show_graph():
    """
    Generates and shows the pie chart graph
    """
    global hat_colours, show_hats
    if show_hats:
        all_hat_types = [Naked,Tophat,GoldenTophat,ClownHat,CowboyHat]
        total = 0
        radius = 70
        center = (radius+45, radius + 20)
        for hats in all_hat_types:
            total += hats.count

        end_angle = 0
        if total != 0:
            for hat in all_hat_types:
                start_angle = end_angle
                fraction = hat.count / total
                arc = fraction * 2 * math.pi
                end_angle += arc
                fill_arc(screen,center,radius,start_angle,end_angle,hat_colours[hat])


fps_clock_timer = 0
fps = ""
def show_fps():
    """
    Displays the fps in 1/2 second intervals
    """
    global fps_clock_timer, fps
    if time.time() > fps_clock_timer + 0.5:
        fps = str(int(clock.get_fps()))
        fps_clock_timer = time.time()

    temp_font = pygame.font.SysFont("Arial", 25, True)
    text = temp_font.render(fps, True, (0, 0, 0))
    text_box = text.get_rect()

    if fullscreen_bordered and not fullscreen_borderless:
        text_box.bottom = screen.get_height() - text_box.height
    else:
        text_box.bottom = screen.get_height()
    screen.blit(text, text_box)


def show_text():
    """
    Displays all the info/text on the screen
    """
    show_amount_of_hats()
    generate_and_show_graph()
    show_fps()


digit = 0
number_to_gen = ""
number_of_person = []
def reset_displayed_number():
    """
    Resets the displayed number that shows how many of a 'person' you want to generate
    """
    global number_to_gen, number_of_person, digit
    digit = 0
    number_to_gen = ""
    number_of_person = []


pause_button = pygame.image.load('graphics/unpaused.png').convert_alpha()
pause_button = pygame.transform.scale(pause_button, (button_width, button_height))
pause_rect = pause_button.get_rect()

speed_button = pygame.image.load('graphics/speed_slow.png').convert_alpha()
speed_button = pygame.transform.scale(speed_button, (button_width, button_height))
speed_rect = speed_button.get_rect()


def alter_button_image(sped_up_in, paused_in):
    """
    Edits the image of the pause/speed up button
    :param sped_up_in: Whether the game is sped up or slowed down
    :param paused_in:  Whether the game is paused or unpaused
    """
    global speed_button, speed_rect, pause_button, pause_rect
    if sped_up_in:
        speed_button = pygame.image.load('graphics/speed_fast.png').convert_alpha()
    else:
        speed_button = pygame.image.load('graphics/speed_slow.png').convert_alpha()

    speed_button = pygame.transform.scale(speed_button, (button_width, button_height))
    speed_rect = speed_button.get_rect()

    if paused_in:
        pause_button = pygame.image.load('graphics/paused.png').convert_alpha()
    else:
        pause_button = pygame.image.load('graphics/unpaused.png').convert_alpha()

    pause_button = pygame.transform.scale(pause_button, (button_width, button_height))
    pause_rect = pause_button.get_rect()

#Initialisations are for each character, once a character amount is selected then it reaches the next 'initialise'
first_pass_initialise_question = True
second_pass_initialise_question = True
third_pass_initialise_question = True
fourth_pass_initialise_question = True
sped_up = False
paused = False
def allow_amount_to_be_typed(person, boolean_check):
    """
    :param person: The 'person' desired to generate
    :param boolean_check: Whether that 'person' is the correct one that should be generated
    """
    global number_to_gen, digit, first_pass_initialise_question, second_pass_initialise_question,\
        third_pass_initialise_question,fourth_pass_initialise_question, number_of_person, number_to_gen_bobby,\
        number_to_gen_lucy, number_to_gen_peter, number_to_gen_marika

    if event.key == pygame.K_BACKSPACE:
        if number_of_person:
            digit -= 1
            number_of_person.remove(number_of_person[digit])
            update_displayed_number()
    elif event.key != pygame.K_RETURN:
        boolean_check = True
        if event.unicode.isdigit():
            number_of_person.append(event.unicode)
            digit += 1
        update_displayed_number()
    else:

        if number_to_gen == "":
            number_to_gen = "0"
        number_to_gen = int(number_to_gen)
        boolean_check = False

        if person == "Bobby":
            number_to_gen_bobby = number_to_gen
        elif person == "Lucy":
            number_to_gen_lucy = number_to_gen
        elif person == "Peter":
            number_to_gen_peter = number_to_gen
        elif person == "Marika":
            number_to_gen_marika = number_to_gen

        number_to_gen = ""
        number_of_person = []
        reset_displayed_number()

    if person == "Bobby":
        first_pass_initialise_question = boolean_check
    elif person == "Lucy":
        second_pass_initialise_question = boolean_check
    elif person == "Peter":
        third_pass_initialise_question = boolean_check
    elif person == "Marika":
        fourth_pass_initialise_question = boolean_check


clock = pygame.time.Clock()
generation_complete = False
number_to_gen_bobby = 0
number_to_gen_lucy = 0
number_to_gen_peter = 0
number_to_gen_marika = 0
attempt_finished = False
check_game_over_timer = 0
winning_clothing = None
show_hats = False
while True:
    screen_start_w = screen.get_width()
    screen_start_h = screen.get_height()

    if not paused:
        test_surface.animate()

    amount_selected = (not first_pass_initialise_question and not second_pass_initialise_question
                       and not third_pass_initialise_question and not fourth_pass_initialise_question)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        # Set screen while asking
        elif first_pass_initialise_question and event.type == pygame.KEYDOWN:
            allow_amount_to_be_typed("Bobby", first_pass_initialise_question)
        elif second_pass_initialise_question and event.type == pygame.KEYDOWN:
            allow_amount_to_be_typed("Lucy", second_pass_initialise_question)
        elif third_pass_initialise_question and event.type == pygame.KEYDOWN:
            allow_amount_to_be_typed("Peter", third_pass_initialise_question)
        elif fourth_pass_initialise_question and event.type == pygame.KEYDOWN:
            allow_amount_to_be_typed("Marika", fourth_pass_initialise_question)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                check_borders()
                fullscreen_borderless = not fullscreen_borderless
                if fullscreen_borderless:
                    toggle_fullscreen(0)
                else:
                    toggle_fullscreen(32)
                    fullscreen_bordered = not fullscreen_bordered
            elif event.key == pygame.K_TAB:
                show_hats = not show_hats
        elif event.type == pygame.WINDOWMAXIMIZED:
            check_borders()
            fullscreen_bordered = not fullscreen_bordered
            if fullscreen_bordered:
                toggle_fullscreen(32)
            else:
                toggle_minimise()
        elif event.type == pygame.MOUSEBUTTONDOWN and not winning_clothing:
            if speed_rect.collidepoint(event.pos):
                sped_up = not sped_up
                alter_button_image(sped_up, paused)
            elif pause_rect.collidepoint(event.pos):
                paused = not paused
                alter_button_image(sped_up, paused)

    current_h = screen.get_height()
    current_w = screen.get_width()

    if screen_start_h != current_h or screen_start_w != current_w:
        test_surface.update_size(current_w, current_h)

    screen.fill((100, 0, 0))
    screen.blit(test_surface.image, (0, 0))

    for people in people_list:

        people.move(people.hitbox_edit[0], people.hitbox_edit[1], sped_up, paused)
        if paused:
            people.image = people.walk_animation_images[0]
        else:
            people.animate()

        screen.blit(people.image, (people.x, people.y))
        people.clothing.draw_clothes(screen, people.head_coord_fix)

        people.check_path_change(current_w, current_h)
        last_persons_clothing = people.clothing

    update_grid_and_collisions()

    # Must be above background before update
    if first_pass_initialise_question:
        ask_how_many("Bobby")

    if second_pass_initialise_question and not first_pass_initialise_question:
        ask_how_many("Lucy")

    if third_pass_initialise_question and not second_pass_initialise_question:
        ask_how_many("Peter")

    if fourth_pass_initialise_question and not third_pass_initialise_question:
        ask_how_many("Marika")

    if amount_selected and not generation_complete:
        generate_with_sprite_correction()
        generation_complete = True

    if amount_selected and generation_complete:
        speed_rect.center = (int(current_w / 1.07), int(current_h / 1.1))
        screen.blit(speed_button, speed_rect)

        pause_button_adj = 80
        pause_rect.center = (int(current_w / 1.07 - pause_button_adj), int(current_h / 1.1))
        screen.blit(pause_button, pause_rect)
        show_text()

    if time.time() > check_game_over_timer and amount_selected:

        attempt_finished = True
        for i in range(1, len(people_list)):
            last_persons_clothing = people_list[i - 1].clothing

            if people_list[i].clothing.__class__ != last_persons_clothing.__class__:
                attempt_finished = False

        check_game_over_timer = time.time() + 3

    if attempt_finished:
        if people_list:
            show_end_screen(people_list[0].clothing)
            winning_clothing = people_list[0].clothing
        else:
            show_end_screen(winning_clothing)
        paused = True

    clock.tick(60)
    pygame.display.update()
    maxframe = max_frame_clock.tick(60)







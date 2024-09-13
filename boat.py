import sys
import os
import math
import random
import argparse
import time
import glob

# TODO: Look at migrating this to pygame-ce
import pygame
import opc

import numpy

from pprint import pprint

FADECANDY_HOST = 'localhost'
FADECANDY_PORT = 7890
TEMPORAL_DITHERING = True

# Note: Modes are selected on a USB keypad.  Each mode should be K_KP*
MODES = {pygame.K_KP1: 'boat',
         pygame.K_KP2: 'fast_boat',
         pygame.K_KP3: 'speed_boat',
         pygame.K_KP4: 'disco',
         pygame.K_KP5: 'slow',
         pygame.K_KP6: 'panic',
         pygame.K_KP7: 'debug',
         pygame.K_KP8: 'bright',
         pygame.K_KP9: 'off',
         pygame.K_KP0: 'america',
         pygame.K_KP_MULTIPLY: 'space',
         pygame.K_1: 'boat',
         pygame.K_2: 'fast_boat',
         pygame.K_3: 'speed_boat',
         pygame.K_4: 'disco',
         pygame.K_5: 'slow',
         pygame.K_6: 'panic',
         pygame.K_7: 'debug',
         pygame.K_8: 'bright',
         pygame.K_9: 'off',
         pygame.K_0: 'america',
         pygame.K_BACKQUOTE: 'space',
        }
SFX_KEYS = {'w': 'warp',
            'p': 'plaid',
            't': 'theme',
            'c': 'comms',
            'v': 'whistle',
            'r': 'alert',
            'a': 'alarm',
            'f': 'fire'
           }
SFX_CHANNELS = {'warp': 0, 'fire': 1, 'alert': 2, 'general': 4}
DEFAULT_MODE = 'space'

# IMPORTANT: As noted, a lot of the debugging (and actual coding) was done
#            while sitting on the floor of a garage. This is not the best 
#            development enviornment to say the least.  I'm going to blame
#            this on the fact that my config.json file got corrupted so I
#            just reverted to padding each strand in software.  Sorry, this
#            is not the best example of how to configure a FadeCandy.

# This is the number of LEDs in each element of the boat. Doesn't directly
# map to the LED positions on the fade candy.
RAIL_SIZE = 120
KITT_SIZE = 20
STERN_SIZE = 15
NOSE_SIZE = 30
WAVE_SIZE = 30
PROW = RAIL_SIZE - NOSE_SIZE
SPINNER_SIZE = 16
TAIL_SIZE = 8

# Note: Removed the poop deck lighting when they caught on fire a bit.
#       Also removed the ground effect when we redid the decking.  May add these back.

# The spinners are for the warp nacelles.
SPINNER_X = 550
SPINNER_TOP = 200
SPINNER_BOT = 350

TAIL_X = 350

OFF = [(0, 0, 0)] * 64

# For display purposes.  The size of each LED in pixels and the space between LEDs
LED_SIZE = 8
LED_GAP  = 2

# Cheap way of controlling the animation speed.  We just change the frame rate.
RATES = dict(boat=20, 
             fast_boat=60, 
             speed_boat=120,
             disco=5, 
             slow=1,   # But I cheat here...
             panic=200,
             debug=10,
             bright=10,
             off=10,
             america=50,
             space=20,
            )

# How much the brightness is increased or decreased each step
BRIGHT_STEP = 0.1

# These are long (1+ hour) ambient sound loops to run in the background.
BOAT_MUSIC = './boat_background.mp3'
SPACE_MUSIC = './space_background.mp3'

SFX_DIR = './sfx'
FADE_TIME = 1000

# This is a single LED object.  If I were to start fresh, I might not
# do it this way but this let me develop/debug the boat and get it into
# a working state.
class Led:
    def __init__(self, pos, size, color=(0,0,0)):
        self.color = color
        self.rect = pygame.Rect(pos, size)

    def draw(self, surf, scale=1.0):
        color = [int(c * scale) for c in self.color]
        pygame.draw.rect(surf, color, self.rect)

# Contains all of the LED strand animation routines.
class Boat:
    # The boat has a Larson Scanner on the bow because... why would you
    # not if that was an option.  If the pirates of the mid-1600's had
    # addressable LEDs you can be 100% sure they would have done this too.
    kitt_size = 3
    kitt_dark = (64, 64, 64)

    rail_level = (128, 128, 128)
    rail_decay = 20
    rail_prob = 0.13

    # Note: The ground effect (wave) LEDs have been removed for renovation
    #       but will probably be added back at some point
    wave_level = 192
    nacelle_level = 128

    # Note: The poop deck LEDs are gone and good riddance to the GBR fire
    #       hazards! Also, they made wiring way more difficult that any
    #       ammount of colourfull joy they brought to this world.  Also,
    #       they tended to smoke or burn at high brightnesses.
    # poop_level = (96, 0, 0)
    # poop_decay = 15
    # poop_fires = 3

    def __init__(self, nacelle_freq=1.0, verbose=False):
        self.wave_left  = generate_waves(self.wave_level, True)
        self.wave_right = generate_waves(self.wave_level, False)
        self.rail_left  = generate_rail(self.rail_level, True)
        self.rail_right = generate_rail(self.rail_level, False)
        self.kitt = generate_kitt(self.kitt_dark)
        self.nacelle_left = generate_nacelle(self.nacelle_level, True)
        self.nacelle_right = generate_nacelle(self.nacelle_level, False)

        self.strips = (self.wave_left,
                       self.wave_right,
                       self.rail_left,
                       self.rail_right,
                       self.kitt,
                       self.nacelle_left,
                       self.nacelle_right,
                      )

        self.kitt_pos = 0
        self.kitt_dir = 1

        self.wave_offset = 0.0

        self._mode = DEFAULT_MODE
        self.brightness = 1.0

        self.disco_delay = 0
        self.verbose = verbose

        self.spin_rate = 360 / numpy.pi
        self.nacelle_angles = numpy.linspace(0, 360, SPINNER_SIZE + 1)[:-1]
        self.nacelle_brightness = (numpy.sin(numpy.arange(360) * nacelle_freq / (2 * numpy.pi)) + 1) * 0.5
        self.nacelle_brightness *= 255 - self.nacelle_level
    
    @property
    def spin_rate(self):
        return self._spin_rate / 60
    
    @spin_rate.setter
    def spin_rate(self, rpm):
        self._spin_rate = rpm * 60

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        self._mode = value
        self.disco_delay = 0

    @property
    def strands(self):
        strands = [[] for i in range(8)]
        empty = [(0, 0, 0)] * 4

        # Old setup: [Initial Incorrect Guesses]
        # Strand 0: Ground effects -- 850 mA
        # Strand 1: Left stern -- 600 mA
        # Strand 2: Left bow -- 480 mA
        # Strand 3: Right stern -- 600 mA
        # Strand 4: Right bow -- 480 mA
        # Strand 5: Poop deck -- 350 mA

        # Strand[0]: Right stern (reversed)
        strands[0] = [led.color for led in self.rail_right[::-1][RAIL_SIZE//2-KITT_SIZE:]] + \
                     empty

        # Strand[1]: Right bow
        strands[1] = [led.color for led in self.rail_right[RAIL_SIZE//2:]] + \
                     [led.color for led in self.kitt[:KITT_SIZE]] + \
                     empty

        # Strand[2]: Left stern (reversed)
        strands[2] = [led.color for led in self.rail_left[::-1][RAIL_SIZE//2-KITT_SIZE:]] + \
                     empty

        # Strand[3]: Left bow
        strands[3] = [led.color for led in self.rail_left[RAIL_SIZE//2:]] + \
                     [led.color for led in self.kitt[KITT_SIZE:][::-1]] + \
                     empty

        # Strand[4]: Ground Effects
        strands[4] = [led.color for led in self.wave_left] + \
                     [led.color for led in self.wave_right[::-1]] + \
                     empty
        
        # Strand[5]: Left nacelle
        strands[5] = [led.color for led in self.nacelle_left] + ([(0, 0, 0)] * (64 - 24))

        # Strand[6]: Left nacelle
        strands[6] = [led.color for led in self.nacelle_right] + ([(0, 0, 0)] * (64 - 24))
        
        return strands

    def click(self, pos):
        # Only really useful in debug mode
        for strip_ix, strip in enumerate(self.strips):
            for led_ix, led in enumerate(strip):
                if led.rect.collidepoint(pos):
                    old = led.color
                    new = (255, 255, 255) if old == (0, 0, 0) else (0, 0, 0)
                    print(f"Strand{strip_ix}[{led_ix}]: {old} -> {new}")
                    led.color = new
                    return

    def update(self, dt_ms):
        if not hasattr(self, self.mode):
            #raise NotImplemented
            print(f"Mode {self.mode!r} not implemented")
            self.mode = DEFAULT_MODE
        
        dt = dt_ms / 1e3
        alpha = dt * self.spin_rate
        self.nacelle_angles = (self.nacelle_angles + alpha) % 360
        
        # Run the currently selected animation routine.
        getattr(self, self.mode)()
        
    def debug(self):
        pass

    # Only useful for the space ship
    def spin_nacelles(self, america=False):
        for ix, angle in enumerate(self.nacelle_angles):
            red = self.nacelle_level + self.nacelle_brightness[int(angle)]
            self.nacelle_left[ix].color = (red, red // 4, 0)
            self.nacelle_right[ix].color = (red, red // 4, 0)

            if ix < TAIL_SIZE:
                self.nacelle_left[ix + SPINNER_SIZE].color = (red, red // 4, 0)
                self.nacelle_right[ix + SPINNER_SIZE].color = (red, red // 4, 0)

    # This routine was used for the Rose, White, and Blue parade.  Unfortunatly:
    # (a) The parade was in full daylight and no one could see the LEDs
    # (b) The white stripes were on the wrong side of the boat.
    def america(self):
        if not hasattr(self, 'usa'):
            self.usa = [(255, 0, 0), (255, 255, 255), (0, 0, 255)]

        # Animate the waves
        changed = False
        r, g, b = self.usa[0]
        d_color = 5
        for ix in range(len(self.wave_left)):
            for edge in (self.wave_left, self.wave_right):
                if edge[ix].color != self.usa[0]:
                    changed = True
                    next = (edge[ix].color[0] + max(-d_color, (min(d_color, r - edge[ix].color[0]))),
                            edge[ix].color[1] + max(-d_color, (min(d_color, g - edge[ix].color[1]))),
                            edge[ix].color[2] + max(-d_color, (min(d_color, b - edge[ix].color[2]))),
                           )
                    edge[ix].color = next
        if not changed:
            self.usa = self.usa[1:] + [self.usa[0]]

        # Animate Larson scanner
        self.kitt_pos += self.kitt_dir
        if (self.kitt_pos < 1) or (self.kitt_pos > (KITT_SIZE - 2) * 2):
            edge = self.rail_left if self.kitt_pos < 1 else self.rail_right
            for i in range(RAIL_SIZE - KITT_SIZE - 6, RAIL_SIZE - KITT_SIZE):
                edge[i].color = (255, 255, 255)
            self.kitt_dir *= -1
            self.kitt_pos += self.kitt_dir
        else:
            self.rail_left[RAIL_SIZE - KITT_SIZE - 1].color = (255, 0, 0)
            self.rail_right[RAIL_SIZE - KITT_SIZE - 1].color = (0, 0, 255)
        
        for led in self.kitt:
            led.color = self.kitt_dark
        for ix in range(self.kitt_pos, self.kitt_pos + self.kitt_size):
            self.kitt[ix].color = (255, 255, 255)
        half = self.kitt_pos + self.kitt_size if self.kitt_dir == 1 else self.kitt_pos - 1
        self.kitt[half].color = (192, 192, 192)

        # Pull the white stripes along the rails
        for ix in range(RAIL_SIZE-KITT_SIZE-1):
            self.rail_left[ix].color = self.rail_left[ix+1].color
            self.rail_right[ix].color = self.rail_right[ix+1].color

        self.spin_nacelles(america=True)

    def speed_boat(self):
        self.boat()     # The regular boat but super fast

    def fast_boat(self):
        self.boat()     # The regular boat but faster

    # The enterprise LED routines.
    def space(self):
        self.boat(in_space=True)

    # The pirate ship LED routines.
    def boat(self, in_space=False):
        # Animate the waves:
        #       Remember the old biorythm BASIC programs you could type
        #       in from a computer magazine.  This is basically that only
        #       without the cheat code where my cirthday was always the 
        #       best one.  Makes a scrolling sin wave with a smaller sine
        #       wave (noise) on top.  The waves are in shades of blue with
        #       peaks in pure white (chop)
        self.wave_offset += 0.31
        t = self.wave_offset
        for ix, led in enumerate(self.wave_left):
            level = self.wave_level
            level += math.sin(t + ix) * 64
            level += math.sin(t + (ix >> 2)) * 24
            color = (0, 0, level) if level <= 255 else (255, 255, 255)
            self.wave_left[ix].color = color
            self.wave_right[ix].color = color

        # Update speckles:
        #       The rails are solid grey but have spots to break up the
        #       monotony. The spots fade to grey over time.
        target = self.rail_level[0]
        for rail in (self.rail_left, self.rail_right):
            for ix, led in enumerate(rail):
                if led.color[0] != target:
                    new_color = max(self.rail_level[0], led.color[0] - self.rail_decay)
                    led.color = (new_color, new_color, new_color)

            if random.random() < self.rail_prob:
                dot = random.randrange(RAIL_SIZE - KITT_SIZE - 2) + 1
                rail[dot].color = (255, 255, 255)
                rail[dot-1].color = (200, 200, 200)
                rail[dot+1].color = (200, 200, 200)

        # The enterprise doesn't get the KITT-esque Larson scanner
        if not in_space:
            self.kitt_pos += self.kitt_dir
            if (self.kitt_pos < 1) or (self.kitt_pos > (KITT_SIZE - 2) * 2):
                self.kitt_dir *= -1
                self.kitt_pos += self.kitt_dir
            for led in self.kitt:
                led.color = self.kitt_dark
            for ix in range(self.kitt_pos, self.kitt_pos + self.kitt_size):
                self.kitt[ix].color = (255, 0, 0)
            half = self.kitt_pos + self.kitt_size if self.kitt_dir == 1 else self.kitt_pos - 1
            self.kitt[half].color = (192, 0, 0)
        else:
            for led in self.kitt:
                led.color = (255, 255, 255)
                # TODO: If in red alert, make this (255, 0, 0)

        # Add indicators:
        #       Add collision lights on the corners of the boat.  Red on the left
        #       and green on the right.
        for starboard, rail in enumerate([self.rail_left, self.rail_right]):
            color = (0, 255, 0) if starboard else (255, 0, 0)  # Good port wine is red
            for ix in range(STERN_SIZE, STERN_SIZE+3):
                rail[ix].color = color
            for ix in range(RAIL_SIZE-NOSE_SIZE-2, RAIL_SIZE-NOSE_SIZE+1):
                rail[ix].color = color

        # Rotate the LEDs in the nacelles.  If the motor and slipring had worked
        # this would have been done in hardware.
        self.spin_nacelles()

    def slow(self):
        if self.disco_delay == 0:
            #self.disco(low=128)  # Too pastel
            self.disco()
            self.disco_delay = 5
        else:
            self.disco_delay -= 1

    def panic(self):
        self.disco()

    def disco(self, low=0, high=255):
        for strip in self.strips:
            for led in strip:
                led.color = (random.randint(low, high),
                             random.randint(low, high),
                             random.randint(low, high))

    # Added this after figuring out that there was no way to turn off the
    # lights except to unplug the LED power supply or the Pi.
    def off(self):
        for strip in self.strips:
            for led in strip:
                led.color = (0, 0, 0)

    # Turn on all of the LEDs to full power.  Great for debugging and setting
    # the poop deck on fire.
    def bright(self):
        for strip in self.strips:
            for led in strip:
                led.color = (255, 255, 255)

    def draw(self, surf):
        for strip in self.strips:
            for led in strip:
                led.draw(surf, self.brightness)

# Only needed for funky poop deck LEDs
def rgb2gbr(c):
    return (c[1], c[0], c[2])

def generate_waves(level, top=True):
    color = (0, 0, level)

    y = (LED_SIZE + LED_GAP) * 12
    if not top:
        bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
        y = bottom - y
    base_x = (LED_SIZE + LED_GAP) * 30

    pixels = []
    for ix in range(WAVE_SIZE):
        x = ((LED_SIZE + LED_GAP) * ix) + base_x
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), color))
    return pixels

def get_rail_pos(ix):
    if ix < STERN_SIZE:
        x = 0
        dy = (LED_SIZE + LED_GAP) * (STERN_SIZE - ix)
    else:
        x = (LED_SIZE + LED_GAP) * (ix - STERN_SIZE)
        dy = max(0, (LED_SIZE + LED_GAP) * (ix - PROW))

    return x, dy

def get_spinner_pos(ix, port):
    base_x = SPINNER_X
    base_y = SPINNER_TOP if port else SPINNER_BOT

    if ix < 4: # Top
        x = base_x + (LED_SIZE + LED_GAP) * ix
        y = base_y
    elif ix < 8:
        x = base_x + (LED_SIZE + LED_GAP) * 4
        y = base_y + (LED_SIZE + LED_GAP) * (ix - 4 + 1)
    elif ix < 12:
        x = base_x + (LED_SIZE + LED_GAP) * 3
        x -= (LED_SIZE + LED_GAP) * (ix - 8)
        y = base_y + (LED_SIZE + LED_GAP) * 5
    else:
        x = base_x - (LED_SIZE + LED_GAP)
        y = base_y + (LED_SIZE + LED_GAP) * 3
        y -= (LED_SIZE + LED_GAP) * (ix - 12 - 1)
    return x, y

def get_tail_pos(ix, port):
    x = TAIL_X + (LED_SIZE + LED_GAP) * (ix % (TAIL_SIZE // 2))
    y = (SPINNER_TOP if port else SPINNER_BOT) + (LED_SIZE + LED_GAP)

    if ix >= (TAIL_SIZE / 2):
        y += (LED_SIZE + LED_GAP) * 3

    return x, y

def generate_nacelle(colour, port):
    pixels = []
    c = (colour, colour // 4, 0)

    for ix in range(SPINNER_SIZE):
        x, y = get_spinner_pos(ix, port)
        # print(f"Nacelle {ix}: {(x, y)}")
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), c))
    
    for ix in range(TAIL_SIZE):
        x, y = get_tail_pos(ix, port)
        # print(f"Tail {ix}: {(x, y)}")
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), c))

    return pixels

def generate_rail(brightness, top=True):
    bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
    pixels = []

    for ix in range(RAIL_SIZE - KITT_SIZE):
        x, dy = get_rail_pos(ix)
        y = dy if top else bottom - dy
        pixels.append(Led((x, y), (LED_SIZE, LED_SIZE), brightness))
    return pixels

def generate_kitt(dark_level):
    bottom = ((LED_SIZE + LED_GAP) * NOSE_SIZE * 2) - LED_SIZE - LED_GAP
    pixels = []

    for ix in range(RAIL_SIZE - KITT_SIZE, RAIL_SIZE):
        x, dy = get_rail_pos(ix)
        pixels.append(Led((x, dy), (LED_SIZE, LED_SIZE), dark_level))

    for ix in range(RAIL_SIZE - 1, RAIL_SIZE - KITT_SIZE - 1, -1):
        x, dy = get_rail_pos(ix)
        pixels.append(Led((x, bottom - dy), (LED_SIZE, LED_SIZE), dark_level))

    return pixels

def parse_args():
    global LED_SIZE     # Hacky McHack calling
    
    parser = argparse.ArgumentParser(description='Pirate LED Controller')
    parser.add_argument('--host', action='store', default=FADECANDY_HOST,
                        help='Fadecandy client hostname')
    parser.add_argument('--port', action='store', type=int, default=FADECANDY_PORT,
                        help='Fadecandy client port number')
    parser.add_argument('--size', action='store', type=int, default=LED_SIZE,
                        help='Size of the LEDs in pixels')
    parser.add_argument('-n', '--dry_run', action='store_true', help='No fadecandy connection')
    parser.add_argument('-f', '--freq', type=float, default=1.0, help='Nacelle brightness frequency')
    args = parser.parse_args()
    assert 1024 <= args.port <= 65535
    assert 1 <= args.size

    LED_SIZE = args.size
    
    # This is only used for the Nacelle
    args.freq *= 1 / numpy.pi

    return args

def play_background(in_space):
    # Note: The background sound should be a MP3 as, for some reason,
    #       I can't get it to work with OGG files.
    if in_space:
        pygame.mixer.music.load(SPACE_MUSIC)
        pygame.mixer.music.set_volume(0.707)
    else:
        pygame.mixer.music.load(BOAT_MUSIC)
        pygame.mixer.music.set_volume(1.0)

    pygame.mixer.music.play(loops=-1)
    # print(f"{pygame.mixer.music.get_volume()=}")

def background_low():
    print("Ducking background")
    pygame.mixer.music.set_volume(0.3)

def background_high():
    print("Restore background")
    pygame.mixer.music.set_volume(0.707)

# Preload all of the sound files.
def load_sounds(sfx_dir):
    alarms = []
    for filename in glob.glob(os.path.join(sfx_dir, 'alarm*.mp3')):
        alarms.append(pygame.mixer.Sound(filename))

    fire = []
    for filename in glob.glob(os.path.join(sfx_dir, 'fire_*.mp3')):
        fire.append(pygame.mixer.Sound(filename))

    comms = pygame.mixer.Sound(os.path.join(sfx_dir, 'comms.mp3'))
    whistle = pygame.mixer.Sound(os.path.join(sfx_dir, 'whistle.mp3'))
    theme = pygame.mixer.Sound(os.path.join(sfx_dir, 'theme.mp3'))
    warp_long = pygame.mixer.Sound(os.path.join(sfx_dir, 'warp_long.mp3'))
    warp_exit = pygame.mixer.Sound(os.path.join(sfx_dir, 'warp_exit.mp3'))
    warp_plaid = pygame.mixer.Sound(os.path.join(sfx_dir, 'warp_plaid.mp3'))
    alert = pygame.mixer.Sound(os.path.join(sfx_dir, 'red_alert.mp3'))

    sfx = {'alarms': alarms,
           'fire': fire,
           'comms': comms,
           'whistle': whistle,
           'theme': theme,
           'alert': alert,
           'warp': {'long': warp_long, 
                    'exit': warp_exit, 
                    'plaid': warp_plaid},
          }
    return sfx

def main(args):
    client = opc.Client(f'{args.host}:{args.port}') if not args.dry_run else None

    warping = None
    
    pygame.init()
    pygame.mixer.init()
    width = (RAIL_SIZE - STERN_SIZE) * (LED_SIZE + LED_GAP)
    height = NOSE_SIZE * (LED_SIZE + LED_GAP) * 2
    screen = pygame.display.set_mode((width, height), 0, 32)
    pygame.display.set_caption("Boat Light Sim")
    print("Loading SFX...", flush=True)
    sfx = load_sounds(SFX_DIR)
    
    assert pygame.mixer.get_num_channels() >= len(SFX_CHANNELS)
    channels = dict()
    for name, ch in SFX_CHANNELS.items():
        channels[name] = pygame.mixer.Channel(ch)
    sfx_queue = dict()
    
    boat = Boat(nacelle_freq=args.freq)
    rate = int(1.0 / RATES[boat.mode] * 1000)  # frame rate in ms
    mute = False

    play_background(boat.mode == 'space')

    running = True
    while running:
        # Great big giant IF/THEN/ELSE for the event queue.  Not ideal.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # Handle the key presses.
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Mute or unmute.  This is on KP_0 so it's easy to get
                # to on a numeric keyboard.  Useful if you are going to
                # be parked somewhere and want the lights but don't want
                # to interfere with someone else's music.
                if event.key == pygame.K_KP_PERIOD:
                    mute = not mute
                    if mute:
                        pygame.mixer.music.pause()
                    else:
                        pygame.mixer.music.unpause()

                # Handle the change in animation routines.
                elif event.key in MODES:
                    new_mode = MODES[event.key]
                    if new_mode != boat.mode:
                        print(f"Setting mode: {MODES[event.key]!r}")
                        was_space = boat.mode == 'space'
                        is_space = new_mode == 'space'
                        if was_space != is_space:
                            play_background(new_mode == 'space')
                        boat.mode = new_mode
                        rate = int(1.0 / RATES[boat.mode] * 1000)  # frame rate in ms

                # The default is to run the lights at full brightness.  This can
                # be a bit much is some situations.  Use the +/- on the numeric
                # keypad to change the brightness.
                elif event.key == pygame.K_KP_PLUS:
                    boat.brightness = min(1.0, boat.brightness + BRIGHT_STEP)
                    print(f"Brightness increased to {boat.brightness:0.02f}")
                elif event.key == pygame.K_KP_MINUS:
                    boat.brightness = max(0.1, boat.brightness - BRIGHT_STEP)
                    print(f"Brightness decreased to {boat.brightness:0.02f}")

                # Sounds can be played by pressing keys.  The keyboard is hidden
                # in the starboard poopdeck area.  Be subtle and it looks/sounds
                # amazing.
                elif event.unicode in SFX_KEYS:
                    sound_type = SFX_KEYS[event.unicode]
                    # SFX_CHANNELS = {'warp': 0, 'fire': 1, 'alert': 2, 'general': 4}

                    # Oh dear... I added this hours before the first sailing with
                    # the spaceship.  This is a poorly designed sound queue and
                    # mostly, kinda, works... not my proudest moment.
                    if sound_type == 'alarm':
                        snd = random.choice(sfx['alarms'])
                        if channels['general'].get_busy():
                            channels['general'].fadeout(500)
                            sfx_queue['general'] = snd
                        else:
                            channels['general'].play(snd)
                    elif sound_type == 'fire':
                        snd = random.choice(sfx['fire'])
                        if channels['fire'].get_busy():
                            channels['fire'].fadeout(500)
                            sfx_queue['fire'] = snd
                        else:
                            channels['fire'].play(snd)
                    elif sound_type == 'warp':
                        if not channels['warp'].get_busy():
                            warping = None
                        # print(f"{warping=}")
                        if warping == 'plaid':
                            channels['warp'].fadeout(1000)
                            sfx_queue['warp'] = sfx['warp']['long']
                            warping = 'long'
                            # print("Plaid -> Warp")
                        elif warping == 'exit':
                            sfx_queue['warp'] = sfx['warp']['long']
                            warping = 'long'
                            # print("Exit -> Warp")
                        elif warping == 'long':
                            channels['warp'].fadeout(500)
                            sfx_queue['warp'] = sfx['warp']['exit']
                            warping = 'exit'
                            print("Warp -> Exit")
                        elif warping is None:
                            sfx_queue['warp'] = sfx['warp']['long']
                            warping = 'long'
                            # print("Warp Entry")
                        else:
                            print(f"Funky warp detected", file=sys.stderr)
                    elif sound_type == 'plaid':
                        # print("PLAID!")
                        if not channels['warp'].get_busy():
                            warping = None
                        # print(f"{warping=}")
                        if warping == 'plaid':
                            channels['warp'].fadeout(1000)
                            warping = None
                            # print("Plaid -> None")
                        elif warping == 'exit':
                            sfx_queue['warp'] = sfx['warp']['plaid']
                            warping = 'plaid'
                            # print("Exit -> plaid")
                        elif warping == 'long':
                            channels['warp'].fadeout(1000)
                            sfx_queue['warp'] = sfx['warp']['plaid']
                            warping = 'plaid'
                            # print("Warp -> Plaid")
                        elif warping is None:
                            sfx_queue['warp'] = sfx['warp']['plaid']
                            warping = 'plaid'
                            # print("Plaid Entry")
                        else:
                            print(f"Funky plaid warp detected", file=sys.stderr)
                    elif sound_type == 'alert':
                        if channels['alert'].get_busy():
                            channels['alert'].fadeout(1000)
                        else:
                            channels['alert'].play(sfx['alert'], loops=-1)
                    else:
                        snd = sfx[sound_type]
                        if channels['general'].get_busy():
                            channels['general'].fadeout(500)
                            sfx_queue['general'] = snd
                        else:
                            channels['general'].play(snd)
                else:
                    # print(f"Unknown key {event.unicode!r}, {event.key=}")
                    pass
            
            # For debugging, you can click on an individual LED and have it
            # toggle.  This is great for debugging and finding out which LEDs
            # are bad.
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    boat.click(event.pos)

            # Some SFX ducks the background audio.  This should bring it back
            # when they are done.
            elif event.type == pygame.USEREVENT:
                # background_high()
                print("Restore background")
                pygame.mixer.music.set_volume(0.707)
            else:
                # print(repr(event))
                # print(f"{event=}, {event.type=}")
                pass

        # Update the display.
        dt = pygame.time.wait(rate)
        boat.update(dt)
        boat.draw(screen)
        pygame.display.flip()

        # Dumb sound queue.
        for q in sfx_queue:
            if sfx_queue[q] is not None:
                if not channels[q].get_busy():
                    if q in ('warp', 'plaid'):
                        channels['warp'].set_endevent(pygame.USEREVENT)
                        # background_low()
                        print("Ducking background")
                        pygame.mixer.music.set_volume(0.3)
                    channels[q].play(sfx_queue[q])
                    sfx_queue[q] = None

        # Update the LEDs.
        if client:
            strands = boat.strands
            client.put_pixels(sum(strands, []))
            if not TEMPORAL_DITHERING:
                client.put_pixels(sum(strands, []))

    # When quitting, fade out the LEDs and the sounds.
    quit_fade = [(0, 0, 0)] * 512
    if client:
        client.put_pixels(sum(strands, []))
        time.sleep(FADE_TIME / 1000.0)
        client.put_pixels(quit_fade)

    pygame.mixer.music.fadeout(FADE_TIME)  # Stop the background sounds
    pygame.mixer.fadeout(FADE_TIME)        # Stop any sound effects
    time.sleep(FADE_TIME / 1000.0)

    # Turn off all of the LEDs when exiting
    if client:
        client.put_pixels(quit_fade)
        client.put_pixels(quit_fade)

    pygame.quit()

if __name__ == '__main__':
    main(parse_args())


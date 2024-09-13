# Ye Old Pirate Ship

So, back in 2018? Yeah, probably 2018 we built a pirate ship for Halloween.  Initially, it was just a canvas wrapped frame about the size of a small 
car and every year we add a bit to it.  It's menaced a bunch of Halloweens, a few unSCruz, a Convergence Camp, a couple of parties and one 4th of July
parade.

The heart of the pirate ship is a Raspberry Pi (for now) powered audio/visual setup.  We've upgraded to a, frankly, massively overpowered amp with 
Bluetooth and AUX inputs (run from the Pi) and an array of RGB LEDs around the edge.  This is the code that runs everything.  It's not great, or even
all that good, and most of it was written while sitting on a garage floor.  If I were to redo it now I would do a much better job, but then again, I
say that every year when I think about rewriting from scratch and it hasn't happened yet.


## Hardware

The code runs on a Raspberry Pi but should work on almost anything. It's been tested on a Windows PC (Win 10), a Raspberry Pi (3, 4, 5, and Compute Module), 
and a MacBook Pro (M1).  The sound output on the Pi is a small USB sound card but it works via Bluetooth, too.  If using a wired connection, I run it through
a audio isolation transformer. This connects to the world cheapest car stereo then to a massive amp and on to the outdoor speakers.

The LEDs are driven by a Fade Candy.  They are pretty much unobtainable these days (see below) but work a treat.  The OPC server runs on Windows, Linux, and
with enough swearing, OSX. The largest issue you have to deal with on large project like this is always signal integrity.  To this end I build a few custom
PCBs to route the signals over some Cat-5 cable which works well.  The power to the LEDs is from an industrial +5V regulator via beefy power cables.

The entire ship is powered by a 12V battery.  Initially, it was an old car battery but that was heavy and difficult to charge on the go.  Currently, I use
an EcoFlow power pack and it will run the ship for an entire night on a charge.  

## Software

The boat controller (this package) is a Python visualizer that also drives the RGB LEDs via a USB Fade Candy.  You will need the 
[OPC server](http://openpixelcontrol.org/) to make this work. One is included with the FadeCandy library... which is where this gets *complicated*. For
reasons, the original Fade Candy repository is no longer available.  You can find [various clones](https://github.com/PimentNoir/fadecandy) kicking around. If 
you don't have a Fade Candy attached, run the program with the `-n` option.

You will also need the `pygame` library (though pygame-ce should work, too). This is the library that shows the visualizer, plays the sounds, and controls
the LED animations. The latest incarnation of the pirate ship (the pirate ship Enterprise) requires `numpy` as well to spin the nacelles. Sorry about that.

## Sound Files

You will need some sound files to make this work.  Both the pirate ship and space pirate ship mode require a long ambient loop.  I pulled down a long
ambient sound file from... sources... like YouTube.  However you go about grabbing them, you will need `boat_background.mp3` for the pirate ship and
`space_background.mp3` for the space ship. I'd include them here, but they are of dubious origin. Ask me about them in person.

There are a bunch of small sound files you will need, too. They are also ripped from various sources on the internet and thus not included here.  Have
a look at `load_sounds(sfx_dir)` function to see what is required.

## Keyboard Controls

Originally, all of the effects were triggered from a small USB numeric keypad glued to the inside of the poop deck.  Most of the modes can be controlled
this way.

* `+`/`-`: Brightness
* `.`: Mute
* `1` - `9`: Pirate ship LED Modes
* `9`: America Mode
* `Backtick`: Space Mode 

In `Debug` mode (`7`) all of the LEDs default to full on.  Click on any them to toggle.

## On Fade Candy

Okay, here's the elephant in the room: This project pretty much requires a Fade Candy to work. I have plenty now but they are basically unobtainable
these days.  For *reasons*, the creator of the Fade Candy (scanlime) and Ada Fruit had a falling out and there's a lot of bad blood all around. I'm not
sure what I'd use if I were starting fresh as the Fade Candy is soooo perfect for this kind of project.

There are a few RP2040 projects that offer close to what I want and are (in some ways) even better but I haven't seen any OPC based projects.  I came
really close to designing my own, and I may in the future, but want to do so in a way that is respectful to the original author. Until then, you need
to scrounge your own Fade Candy. I was down to a single remaining one until I came across a bunch of them... when the company I was working for died. So
you know, you win some you loose some.

Finally, on a personal note to scanlime (Micah): I hope you are doing well and want you to know you are an inspiration to a whole pile of artist/engineers
around the world.  

## License

This project is licensed under the [WTFPL-2 License](http://www.wtfpl.net/)- see the LICENSE.md file for details

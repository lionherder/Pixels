Pixels
======
A sample of code that FFT encodes an audio stream and saves unique event data (20G+) into a persistent object on disk.  The event data is then used to project 'cool math stuff' onto a grid of 1024 Neopixels (LEDs).  In this case, a 512-\
band spectrum analyser.

https://www.adafruit.com/category/168

Things of note:

* Multi-processing.  (Tried multi-threading but it didn't help me)
* Persistent objects so I can work with massive data structures that won't entirely fit in memory.
  * Wrote a mySQL version but didn't win any performance
* The 'display' lib is packed with utilities: pixel mapping, multi-color gradients, trig tables, display buffering.
* The 'event' lib is what does the encoding and creation of the event files.


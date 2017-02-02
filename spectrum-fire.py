#!/usr/bin/python2

import sys
import os
import select
import colorsys
import math
import random
import time
import argparse
import traceback

import event
import display
import average
import config

'''A class that uses an event file to create a spectrum of colors'''
class Spectrum(object):

    def __init__(self, args):
        self.args = args
        self.disp = display.display()
        self.config = config.config()
        self.event = None

    def save_config(self):
        print("Saving config")
        event_info = self.event.get_event_info()
        event_info['B_FREQ_HIGH'] = self.config['B_FREQ_HIGH']
        event_info['B_FREQ_LOW'] = self.config['B_FREQ_LOW']
        event_info['FREQ_SCALE'] = self.config['FREQ_SCALE']
        event_info['FPS_BIAS'] = self.config['FPS_BIAS']
        self.event.set_event_info(event_info)

    def load_config(self):
        print("Loading config...")
        try:
            event_info = self.event.get_event_info()
            self.config['B_FREQ_HIGH'] = event_info['B_FREQ_HIGH']
            self.config['B_FREQ_LOW'] = event_info['B_FREQ_LOW']
            self.config['FREQ_SCALE'] = event_info['FREQ_SCALE']
            self.config['FPS_BIAS'] = event_info['FPS_BIAS']
        except:
            print("Spectrum config not present")
            print(traceback.format_exc())

    # Do all the work
    def run(self):
        self.disp.create(self.config['PHYSICAL_X'], self.config['PHYSICAL_Y'], self.config['PHYSICAL_X'], self.config['PHYSICAL_Y'], self.config['FC_HOST'])
        self.disp.fc_connect()
        self.disp.create_trig_tables(self.config['GRAIN'])

        # Our options for the new event
        opts = {
            'freq_bins'  : self.config['FREQ_BINS'],
            'freq_min'   : self.config['F_MIN'],
            'freq_max'   : self.config['F_MAX'],
            'fps'        : self.config['FPS'],
            'frame_size' : self.config['FRAME_SIZE'],
            'chunk_sec'  : self.config['CHUNK_SEC'],
            'procs'      : self.config['PROCS']
        }
        self.event = event.event(self.args.filename, output_file="{}.db".format(os.path.basename(self.args.filename)), **opts)

        # State
        if (self.args.p):
            # Playback
            if (not self.event.load()):
                sys.exit(1)
        elif (self.args.e):
            # Create
            self.event.create_proced()
        # Reload our config to pick up anything new
        self.load_config()

        print("Ready to start the show")
        sys.stdin.readline()

        # XXX: Just a little setup time before starting, for testing
#        time.sleep(3)

        r_avg         = average.rolling(self.config['PHYSICAL_Y'], self.config['ROLLING_SIZE']) # Rolling average
        f_range       = self.config['B_FREQ_HIGH'] - self.config['B_FREQ_LOW']  # frequency band to use
        last_ts       = 0 # Last time stamp
        s_delta       = 0 # Seconds delta since start
        e_map         = self.event.get_event_db() # The event map of events
        e_frames      = self.event.get_event_keys() # Sorted list of event frames
        event_info   = self.event.get_event_info() # Info specific to this event file
        e_frame_count = len(e_frames) # Number of frames
        c_fps         = 0 # Calculated FPS
        index         = 0 # Index into the event frames
        start_time    = time.time() # Event starting time
        bg_color      = ( 0.0, 0.0, 0.0 ) # Background color to use
        rgb           = () # RGB for spectrum line
        f_max         = 0 # Just a little test variable

        while (index < e_frame_count):
            # How many seconds into the stream
            f_start = time.time()
            s_delta = f_start - start_time
    
            # Quit if we're done
            if (index < 0.0 or index >= e_frame_count):
                done = True
                break

            # Get our timestamp and split it
            key = e_frames[index]
            (ts, tf) = key.split(":")
            t_ts = int(ts)
            t_tf = int(tf)

            # Print out stats at the start of each second
            if (t_ts != last_ts):
                # Save the time and index of the second
                hh = int(math.floor(t_ts/float(3600.0)))
                mm = int(math.floor((t_ts - (hh * 3600)) / float(60.0)))
                ss = int(t_ts - ((hh * 3600) + (mm * 60)))
                print("[{}:{}:{}] Second: {}f  Index: {}  Start: {}s  Current: {}fs  FPS: {}fs  FPS Bias: {}fs".format(hh, mm, ss,
                                                                                                                       s_delta,
                                                                                                                       index,
                                                                                                                       start_time, time.time(),
                                                                                                                       c_fps, self.config['FPS_BIAS']))
                print("[{}:{}:{}] Bin High/Hz: {}/{}hz  Bin Low: {}/{}hz:  Freq Scalar: {}f".format(hh, mm, ss,
                                                                                                    self.config['B_FREQ_HIGH'],
                                                                                                    (self.config['B_FREQ_HIGH']+1) * (self.config['F_MAX']/float(self.config['FREQ_BINS'])),
                                                                                                    self.config['B_FREQ_LOW'],
                                                                                                    (self.config['B_FREQ_LOW']+1) * (self.config['F_MAX']/float(self.config['FREQ_BINS'])),
                                                                                                    self.config['FREQ_SCALE']))
                c_fps = 0

            # Clear the physical layer for next render
            self.disp.clear_physical_layer(bg_color)

            # All the frequency bins for this frame (FREQ_BINS)
            f_bins = e_map[key]

            # Create a list of PHYSICAL_Y pixels from list of FREQ_BINS
            f_list = []

            for p_index in range(0, self.config['PHYSICAL_Y']):
                # This is the actual index into the frequency list n = FREQ_BINS
                f_index = int(p_index / float(self.config['PHYSICAL_Y']) * f_range + self.config['B_FREQ_LOW'])
                f_list.append(min(self.config['FREQ_MAX_VOL'], f_bins[f_index]))

            # Roll it into our averages
            r_avg.roll(f_list)

            # Now create the bars
            for p_index in range(0, self.config['PHYSICAL_Y']):
                # Straight up linear mapping of freq to pixels
                t_avg = r_avg.make_avg(p_index)
                freq_bar = int(min(t_avg/self.config['FREQ_SCALE'] * float(self.config['PHYSICAL_X']), self.config['PHYSICAL_X']))
                for x in range(0, freq_bar):
                    f_ratio = x / float(freq_bar) * self.config['GRAIN']
                    rgb = self.disp.grad_tab(int(f_ratio))
                    self.disp.set_physicalRGB_XY(x, p_index, rgb)

            # Update the display
            self.disp.push_physical_layer()
            # Control the fps by short sleeps
            if (self.config['FPS_BIAS'] > 0):
                time.sleep(self.config['FPS_BIAS'])
    
            # Advance our frame counter
            c_fps += 1

            # Update the last timestamp/timeframe
            last_ts = t_ts

#            if (time.time() - f_start) > (1/float(self.config['FPS'])):
#                print("[{}:{}]: Took too long: {} ms".format(ts, tf, time.time() - f_start))

            # Check if we have any keyboard input
            while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                m_index = 0
                m_time = 0
                t_index = 0
                c_line = sys.stdin.readline()
                for c_char in c_line:
                    if c_char:
#                        print("+Starttime: ", start_time)

                        # GTFO
                        if (c_char == '!'):
                            # Set this to 0 will end the show
                            print("Ending the show")
                            e_frame_count = 0

                        # Freq bin high
                        elif (c_char == 'a'):
                            self.config['B_FREQ_HIGH'] = min(self.config['B_FREQ_HIGH'] + 2, self.config['FREQ_BINS'])
                            f_range = self.config['B_FREQ_HIGH'] - self.config['B_FREQ_LOW']
                            print("Freq high up {}".format(self.config['B_FREQ_HIGH']))
                        elif (c_char == 'z'):
                            self.config['B_FREQ_HIGH'] = max(self.config['B_FREQ_HIGH'] - 2, self.config['B_FREQ_LOW'])
                            f_range = self.config['B_FREQ_HIGH'] - self.config['B_FREQ_LOW']
                            print("Freq high down {}".format(self.config['B_FREQ_HIGH']))
                        # Freq bin low
                        elif (c_char == 's'):
                            self.config['B_FREQ_LOW'] = min(self.config['B_FREQ_LOW'] + 2, self.config['B_FREQ_HIGH'])
                            f_range = self.config['B_FREQ_HIGH'] - self.config['B_FREQ_LOW']
                            print("Freq low up {}".format(self.config['B_FREQ_LOW']))
                        elif (c_char == 'x'):
                            self.config['B_FREQ_LOW'] = max(self.config['B_FREQ_LOW'] - 2, 0.0)
                            f_range = self.config['B_FREQ_HIGH'] - self.config['B_FREQ_LOW']
                            print("Freq low down {}".format(self.config['B_FREQ_LOW']))

                        # Scale frequencies
                        elif (c_char == 'd'):
                            self.config['FREQ_SCALE'] += .25
                            print("Freq scalar up {}".format(self.config['FREQ_SCALE']))
                        elif (c_char == 'c'):
                            self.config['FREQ_SCALE'] = max(self.config['FREQ_SCALE'] - .25, 0.00001)
                            print("Freq scalar down {}".format(self.config['FREQ_SCALE']))

                        # Adjust sleep time between frames
                        elif (c_char == 'f'):
                            self.config['FPS_BIAS'] += .001
                            print("FPS Bias up {}".format(self.config['FPS_BIAS']))
                        elif (c_char == 'v'):
                            self.config['FPS_BIAS'] = max(self.config['FPS_BIAS'] - .001, 0.0)
                            print("FPS Bias down {}".format(self.config['FPS_BIAS']))

                        # Sliding the time window for time sync'ing
                        elif (c_char == ']'):
                            print("Speeding up...")
                            start_time -= 0.25
                        elif (c_char == '}'):
                            print("Micro speed up...")
                            start_time -= 0.025
                        elif (c_char == '['):
                            print("Slowing down...")
                            start_time += 0.25
                        elif (c_char == '{'):
                            print("Micro slow down...")
                            start_time += 0.025
                        elif (c_char == '='):
                            # Move to a specific timestamp
                            m_index = c_line.rfind('=')
                            t_index = c_line[m_index+1:]

                            # Do we have a hh:mm:ss format
                            (hh, mm, ss) = ( 0, 0, 0 )
                            if (t_index.rfind(':') > -1):
                                t_split = c_line[m_index+1:].split(':')
                                # Check timestamp format
                                if (len(t_split) == 2):
                                    hh = 0
                                    mm = int(t_split[0])
                                    ss = int(t_split[1])
                                    print("Format MM:SS: [{}, {}, {}]".format(hh, mm, ss))
                                elif (len(t_split) == 3):
                                    hh = int(t_split[0])
                                    mm = int(t_split[1])
                                    ss = int(t_split[2])
                                    print("Format HH:MM:SS: [{}, {}, {}]".format(hh, mm, ss))
                                m_time = (hh * 3600) + (mm * 60) + ss
                            else:
                                # Epoc time, so just plain adjust the start time
                                m_time = float(t_index)
                                print("Format seconds: [{}]".format(m_time))
                            start_time = time.time() - m_time
                            print("Moving to second [{}]".format(m_time))
#                            print("Starttime: ", start_time)
                # Do this after every keypress
                self.save_config()
            index = int(math.ceil((time.time() - start_time) * float(self.event.get_fps())))
        time.sleep(1)
        self.event.close()

if __name__ == '__main__':
    # Create a gradient: (start rgb), (end rgb), (start %, end %)
#    gradient = [ [ (0, 0, 0), (255, 0, 0), (0, 0.40) ],
#                 [ (255, 0, 0), (0, 0, 255), (0.40, .5) ],
#                 [ (0, 0, 255), (0, 255, 0), (0.5, .65) ],
#                 [ (0, 255, 0), (255, 255, 255), (0.65, 1.0) ] ] 

# 6-color gradient
#    gradient = [ [ (228, 3, 3), (255, 140, 0), (0, 0.167) ],
#                 [ (255, 140, 0.0), (255, 237, 0), (0.167, 0.333) ],
#                 [ (255, 237, 0), (0, 128, 38), (0.333, 0.5) ],
#                 [ (0, 128, 38), (0, 77, 255), (0.5, 0.666) ],
#                 [ (0, 77, 255), (117, 7, 135), (0.666, 0.833) ],
#                 [ (117, 7, 135), (228, 3, 3), (0.833, 1.0) ] ]
# Star particle gradient
#    gradient = [ [ (255, 0, 0), (128, 0, 0), (0, .6) ],  # Red
#                 [ (128, 0, 0), (255, 150, 0), (0.6, .65) ], # Yellow
#                 [ (255, 150, 0), (150, 150, 125), (.65, 0.75) ],
#                 [ (200, 200, 125), (230, 230, 210), (0.75, .85) ],
#                 [ (230, 230, 230), (100, 100, 255), (0.85, .9) ],
#               ]
# Plain R->G->B
    gradient = [ [ (255, 0, 0), (0, 255, 0), (0.0, 0.5) ],
                 [ (0, 255, 0), (0, 0, 255), (0.5, 1.0) ] ]

    parser = argparse.ArgumentParser(description="Spectrum display using gradients")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-p', action='store_true', help="playback event file")
    group.add_argument('-e', action='store_true', help="multi-process encode")
    parser.add_argument('filename', help="audio filename")
    args = parser.parse_args()

    spec = Spectrum(args)
    spec.disp.comp_gradient(gradient, grain=32)
    print spec.disp.grad_table
    spec.run()
    print("\nThe show is over.")

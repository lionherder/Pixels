import os
import sys
import shelve
import librosa
import threading
import multiprocessing as MP
import json
import time
import math

import encode_process as EP
import config

'''
   Creates an event database out of a sound file.  Depending on the
   parameters used, this data can be enormous.  The idea is to create
   one event data file and use that for all other visualizations.
'''

class event():

    def __init__(self, input_file, output_file=None, sample_rate=44100, fps=140, procs=6,
                 freq_bins=512, freq_max=22050, freq_min=0, frame_size=600, chunk_sec=60):
        self.config      = config.config.get_config()
        self.input_file  = input_file
        self.output_file = "%s.db".format(input_file) if (not output_file) else output_file
        self.chunk_sec   = chunk_sec  # How many seconds per chunk to FFT
        self.frame_size  = frame_size # How much data is read in at one time
        self.sample_rate = sample_rate # Sample rate of audio
        self.fps         = fps # How many FPS to encode with
        self.hop_length  = int(sample_rate/fps)  # Size of each frame
        self.freq_bins   = freq_bins  # How many frequency bins for the FFT
        self.freq_max    = freq_max  # Max cutoff frequency
        self.freq_min    = freq_min # Min cutoff frequency
        self.procs       = procs # How many processes to spawn
        self.manager     = None # Proceses manager
        self.pool        = None # Process pool
        self.proc_list   = [] # List of procs
        self.event_keys  = [] # List of all top level keys in the event file
        self.event_db    = None # The persistent DB object
        self.clock_sec   = time.time() # Just a timer
        self.queue       = MP.Queue() # Queue for IPC

    # Close down the DB
    def close(self):
        if (self.event_db):
            self.event_db.close()
        
    # Simply opens the database for playing.
    # DB must exists, of course
    # Returns the event db
    def load(self):
        print("Loading event file: {}".format(self.output_file))
        if (not os.path.exists(self.output_file)):
            print("Error: Could not load event file.")
            return None

        # Open and load event file
        self.event_db = shelve.open(self.output_file, writeback=self.config['WRITEBACK'])
        
        if (not self.event_db.has_key('-1:0')):
            print("Error: Could not find information entry in event file.")
            return None

        event_info = self.event_db['-1:0']
        self.freq_bins   = event_info['freq_bins']
        self.sample_rate = event_info['sample_rate']
        self.fps         = event_info['fps']
        self.freq_max    = event_info['freq_max']
        self.freq_min    = event_info['freq_min']
        self.event_keys  = event_info['event_keys']

        print("Event file loaded:")
        print("  - Sample Rate: {}".format(self.sample_rate))
        print("  - Recorded FPS: {}".format(self.fps))
        print("  - Freq bins: {}".format(self.freq_bins))
        print("  - Freq min/max: {}/{}".format(self.freq_min, self.freq_max))
        print("  - Hz per bin: {} hz".format((self.freq_max - self.freq_min)/self.freq_bins))
        print("  - Frames: {}".format(len(self.event_keys)))

        return True

    # Encode using multi-processing
    def create_proced(self):
        print("Starting multiprocess encoding...")
        print("Event DB file: {} -> {}".format(self.input_file, self.output_file))
        print("  - Sample Rate: {}".format(self.sample_rate))
        print("  - Recording FPS: {}".format(self.fps))
        print("  - Freq sample size: {}".format(self.sample_rate/self.fps))
        print("  - Freq bins: {}".format(self.freq_bins))
        print("  - Freq cut off high: {}".format(self.freq_max))
        print("  - Freq cut off low: {}".format(self.freq_min))
        print("  - Frame size: {}s".format(self.frame_size))
        print("  - Chunk size: {}s".format(self.chunk_sec))

        # First lets check if the input file is available
        if (not os.path.exists(self.input_file)):
            print("\nError: Source file '{}' does not exist.".format(self.input_file))
            sys.exit(1)
        
        # Create a new db file
        print("\nClearing old data...  May take a few.")

        if (os.path.exists(self.output_file)):
            print("***")
            print("*** This database exists.  Hit return if you REALLY want to re-encode it.")
            print("***")
            sys.stdin.readline()
            os.remove(self.output_file)

        print("Creating new DB file")
        # Open our PO DB file
        self.event_db = shelve.open(self.output_file, writeback=self.config['WRITEBACK'])
        print("Creating processing pool")
        self.manager = mp.Manager()
        self.queue = self.manager.Queue()
        self.pool = mp.Pool(self.procs)

        # Create our event header information
        event_info = {
            "filename"    : self.input_file,
            "sample_rate" : self.sample_rate,
            "fps"         : self.fps,
            "freq_bins"   : self.freq_bins,
            "freq_max"    : self.freq_max,
            "freq_min"    : self.freq_min,
            "event_keys"  : []
        }
        self.event_db['-1:0'] = event_info

        # Start encoding
        sec_offset = 0
        done = False
        self.clock_sec = time.time()
        while (not done):
            print("Reading {}s [{}K - {}K] @ {} seconds".format(self.frame_size,
                                                                sec_offset * self.sample_rate / 1024,
                                                                ((sec_offset + self.frame_size) * self.sample_rate) / 1024,
                                                                sec_offset))
            y_data, sr = librosa.core.load(self.input_file, self.sample_rate, offset=sec_offset, duration=self.frame_size)
            y_data_num = len(y_data)
            print("Read {}K  Sec: {}".format(y_data_num/1024, y_data_num/self.sample_rate))
            if (y_data_num <= 0):
                print("No more samples")
                done = True
            else:
                print("Splitting %d buffer into %d second chunks".format(y_data_num, self.chunk_sec))
                # Start splitting procs
                time_index = 0
                f_index = 0
                for data_index in range(0, y_data_num, (self.chunk_sec * self.sample_rate)):
                    data_index_next = min(data_index + (self.chunk_sec * self.sample_rate), y_data_num)
                    data_slice = y_data[data_index:data_index_next]
                    p_name = "{}".format(f_index)
                    # Add in the new 
                    new_proc = self.pool.apply_async(start_proc, (sec_offset + time_index, data_slice, event_info, p_name,))
                    self.proc_list.append(new_proc)
                    time_index += self.chunk_sec
                    print("Data index: [{} - {}] - Slice len: [{}]".format(data_index, data_index_next, len(data_slice)))
                    f_index += 1
                print("Created {} procs.  Starting...".format(len(self.proc_list)))
                print("-" * 80)

            self.run_procs()
            sec_offset += self.frame_size

        print("Saving event info...")
        event_info['event_keys'] = self.event_keys
        self.event_db['-1:0'] = event_info
        self.event_db.sync()
        print("Convert time {}s".format( time.time() - self.clock_sec))
        self.load()
        return self.event_db

    def run_procs(self):
        """Run all the procs we just created"""
        index = 0
        # A timekeeper
        start_time = time.time()

        counter = 0
        # Loop until proc list is empty
        while (len(self.proc_list) > 0):
            # If we're not syncing
            # Are we running enough procs.
            for l_proc in self.proc_list:
                try:
                    a_res = l_proc.get(timeout=.01)
                    print("Proc finished: {}".format(len(a_res)))
                    self.proc_list.remove(l_proc)
                    print("[ ()s ] Procs left: {}".format(time.time() - self.clock_sec, len(self.proc_list)))
                    for a_key in a_res:
                        self.event_db[a_key] = a_res[a_key]
                        if not (counter % 100):
                            print("Syncing events: {:.2%}".format(0.0 if len(a_res) == 0 else (counter/float(len(a_res)))))
                        counter += 1
                    self.event_keys += a_res.keys()
                    counter = 0
                except Exception as e:
#                    print("Exception: {}".format(e))
                    pass
                counter = 0

    # Some accessor stuff
    def get_event_keys(self):
        return sorted(self.event_keys)
    
    def get_input_file(self):
        return self.input_file

    def get_output_file(self):
        return self.output_file

    def get_frame_size(self):
        return self.frame_size

    def get_sample_rate(self):
        return self.sample_rate

    def get_hop_length(self):
        return self.hop_length

    def get_fps(self):
        return self.fps

    def get_freq_bins(self):
        return self.freq_bins

    def get_freq_max(self):
        return self.freq_max

    def get_freq_min(self):
        return self.freq_min

    def get_event_db(self):
        return self.event_db

    def get_event_info(self):
        if self.event_db.has_key('-1:0'):
            return self.event_db['-1:0']
        return {}

    def set_event_info(self, event_info):
        self.event_db['-1:0'] = event_info
        return event_info

def start_proc(sec_offset, slice_data, event_info, name):
    p_encoding = EP.Encode(sec_offset, slice_data, event_info, name)
    return p_encoding.run()
                                        
        

import sys
import os.path
import shelve
import librosa
import threading
import multiprocessing
import commands
import time

'''The class that is used by the spawned processes.  It FFT encodes a chunk of audio and returns a dict of events.'''

class Encode():

    def __init__(self, sec_offset, slice_data, event_info, name=None):
        self.sec_offset     = sec_offset
        self.slice_data     = slice_data
        self.event_info     = event_info
        self.start_time     = time.time()
        self.name           = name
        self.enc_data       = {}

    def load_info(self):
        self.fps            = self.event_info['fps']
        self.sample_rate    = self.event_info['sample_rate']
        self.freq_min       = self.event_info['freq_min']
        self.freq_max       = self.event_info['freq_max']
        self.freq_bins      = self.event_info['freq_bins']
        self.sample_fps     = int(round(self.sample_rate / float(self.fps)))

    def run(self):
        self.start_time = time.time()
        self.log("Encoding process starting")

        # Load our info
        self.load_info()

        self.log("Offset: %d sec.  Chunk size: %d" % (self.sec_offset, len(self.slice_data)))

        y = librosa.feature.melspectrogram(self.slice_data, fmin=self.freq_min, fmax=self.freq_max,
                                           sr=self.sample_rate, hop_length=self.sample_fps, n_mels=self.freq_bins)
        self.log("Frequency channels: %d" % (len(y)))
        f_bins = len(y)
        samples = len(y[0])-1
        self.log("Samples: %d - Freq Bins: %d - Seconds: %d" % (samples, f_bins, int(round(samples/float(self.fps)))))

        self.log("Building events...")
        ts = ( 0, 0 )
        t_offset = 0
        for r_index in range(0, samples, self.fps):
            r_index_next = min(r_index+self.fps, samples)
            frame_len = len(y[t_offset][r_index:r_index_next])
            f_index = 0
            self.log("Building event: %ds/%ds [%2.0f%%] - Frame len: %d - FPS: %d - r_index: %d - r_index_next: %d - samples: %d" % (self.sec_offset + t_offset, self.sec_offset + round(samples/float(self.fps)),
                                                                                                                                     (r_index / float(samples)) * 100, frame_len, self.fps, r_index, r_index_next, samples))
            while (f_index < frame_len):
                ts_frac = int(f_index/float(frame_len) * 1000000)
                ts = ( self.sec_offset + t_offset, ts_frac )
                ts_str = "%6.6d:%6.6d" % ts
                bins = []
                for b_index in range(0, f_bins):
                    bins.append(y[b_index][r_index + f_index])
                self.enc_data[ts_str] = bins
                f_index += 1
            t_offset += 1

        self.log("Created %d frames" % (len(self.enc_data)))
        self.log("Process ended")
        return self.enc_data

    def log(self, msg):
        print("[%3.3d] %s" % (self.sec_offset, msg))
        pass


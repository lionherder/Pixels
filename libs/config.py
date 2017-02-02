import math
import json

"""A block of globals for the entire project."""

class config(object):
    """
    A rigged up and abused singleton hash table class for global variables.
    Use like a regular hashtable.  Use get_config() to get an instance.
    """

    # Our single instance
    CONFIG_CLASS = None

    GLOBALS = { 
        'FC_HOST'      : '192.168.0.69:7890',
        'F_MAX'        : 22050,
        'F_MIN'        : 0,   
        'FREQ_BINS'    : 512,
        'B_FREQ_HIGH'  : 511,
        'B_FREQ_LOW'   : 0,
        'SAMPLE_RATE'  : 44100,
        'FPS'          : 140,
        'FRAME_SIZE'   : 1200,
        'CHUNK_SEC'    : 120,
        'FPS_BIAS'     : 0.001,
        'FREQ_SCALE'   : 1.0,
        'FREQ_MAX_VOL' : 512,
        'PROCS'        : 6,
        'GRAIN'        : 256,
        'TWO_PI'       : math.pi * 2,
        'PHYSICAL_X'   : 8,
        'PHYSICAL_Y'   : 128,
        'CANVAS_X'     : 8,
        'CANVAS_Y'     : 128,
        'ROLLING_SIZE' : 1,
        'SYNC_TIME'    : 60,
        'WRITEBACK'    : False
    }

    def toJSON(self, filename=None):
        """Spit out a json string of our current GLOBALS hash"""
        if (not filename):
            return json.dumps(self.GLOBALS, sort_keys=True, indent=4)
        else:
            g_fd = open(filename, 'wb')
            json.dump(self.GLOBALS, g_fd, sort_keys=True, indent=4)
            g_fd.close()
        return None

    def fromJSON(self, filename):
        """Load config from a json file"""
        print("Loading config from json: {}".format(filename))
        g_fd = open(filename, 'rb')
        self.GLOBALS = json.load(g_fd)
        g_fd.close()

    # Turn this class into a hash/dict object
    def __getitem__(self, i_key):
        """This will throw an exception if the key doesn't exist"""
        return self.GLOBALS[i_key]

    def __setitem__(self, i_key, i_value):
        self.GLOBALS[i_key] = i_value

    def __delitem__(self, key):
        if self.GLOBALS.has_key(key):
            del self.GLOBALS[key]

    # Pretty print of class
    def __str__(self):
        p_str = "GLOBALS:\n"
        p_str += self.toJSON()
        return p_str

    # Create and/or give us our singleton
    @classmethod
    def get_config(cls):
        """This give us a singleton instance"""
        if (cls.CONFIG_CLASS):
            return cls.CONFIG_CLASS

        cls.CONFIG_CLASS = config()
        return cls.CONFIG_CLASS


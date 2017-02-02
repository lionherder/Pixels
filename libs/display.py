import os
import sys
import math
import json
import traceback

import opc
import config

'''A class that is the interface between the math and the real physical pixels'''

class display(object):

    def __init__(self):
        self.config = config.config.get_config()
        self.grain = int(self.config['GRAIN'])
        self.fc_host = self.config['FC_HOST']
        self.fc_conn = None
        # Persistent object info
        self.db_filename = ""
        # Starting color
        self.init_color = ( 0, 0, 0 )
        # Sin/Cos table
        self.sin_table = []
        self.cos_table = []
        self.grad_table = []
        # Canvas map info
	self.c_map = None
        self.c_size_x = 0
        self.c_size_y = 0
        self.c_num_pixels = (self.c_size_x * self.c_size_y)
        self.c_grid = None
        # Physical pixel map
        self.p_map = None
        self.p_size_x = 0
        self.p_size_y = 0
        self.p_num_pixels = (self.p_size_x * self.p_size_y)
        self.p_grid = None

    def fc_connect(self):
        """Attempt to connect to our fadecandy server"""
        self.fc_conn = opc.Client(self.fc_host)

        if (not self.fc_conn.can_connect()):
            print "Could not connect to server:", self.fc_host

        return self.fc_conn

    def open_db(self, db_filename):
        """Open an existing object file and load it if possible"""
        db_obj = None
        try:
            print("DB Size '{}K'".format(os.path.getsize(db_filename)/1024))
            db_fp = open(db_filename, 'r')
            db_obj = json.load(db_fp)
            print db_obj.keys()
            if (not db_obj.has_key('d_info')):
                raise("No 'info' in object file.  Valid DB?")
            if (not db_obj.has_key('c_info')):
                raise("No canvas layer info in object file.  Valid DB?")
            if (not db_obj.has_key('p_info')):
                raise("No physical layer info in object file.  Valid DB?")
        except:
            print("Problem opening object file: {}".format(sys.exc_info()[0]))
            tb = sys.exc_info()[2]
            print("Traceback: {}".format(traceback.print_tb(tb)))
            sys.exit(1)
        
        return db_obj
        
    def load(self, db_filename):
        """Open an existing object file and load it if possible"""
        db_obj = self.open_db(db_filename)

        # Load up the json'd configuration
        self.config.fromJSON(db_obj['config'])

        # Load all the state information about this display object
        d_info = db_obj['d_info']
        print("D_INFO: {}".format(", ".join(d_info.keys())))
        self.fc_conn = None
        self.fc_host = d_info['fc_host']
        self.init_color = d_info['init_color']

        # Canvas map info
        c_info = db_obj['c_info']
        print("C_INFO: {}".format(", ".join(c_info.keys())))
	self.c_map = c_info['c_map']
        self.c_size_x = c_info['c_size_x']
        self.c_size_y = c_info['c_size_y']
        self.c_num_pixels = c_info['c_num_pixels']
        self.c_grid = c_info['c_grid']

        # Physical map info
        p_info = db_obj['p_info']
        print("P_INFO: {}".format(", ".join(p_info.keys())))
	self.p_map = p_info['p_map']
        self.p_size_x = p_info['p_size_x']
        self.p_size_y = p_info['p_size_y']
        self.p_num_pixels = p_info['p_num_pixels']
        self.p_grid = p_info['p_grid']

        self.fc_connect()
	self.init_map()
        self.create_trig_tables(self.config['GRAIN'])
        db_obj.clear()

    def save(self, db_name=None):
        """Create and save a database for us.  Can preserve the canvas
        layer if so desired.
        """
        database_name = db_name if db_name else self.db_filename
        db_info = {}

        print("Saving display to db '{}'".format(database_name))
        db_info['config'] = self.config.toJSON()

        # General stuff
        d_info = {}
        d_info['fc_host'] = self.fc_host
        d_info['init_color'] = self.init_color
        d_info['db_filename'] = self.db_filename
        db_info['d_info'] = d_info
        

        # Canvas map info
        c_info = {}
	c_info['c_map'] = self.c_map
        c_info['c_size_x'] = self.c_size_x
        c_info['c_size_y'] = self.c_size_y
        c_info['c_num_pixels'] = self.c_num_pixels
        c_info['c_grid'] = self.c_grid
        db_info['c_info'] = c_info

        # Physical map info
        p_info = {}
	p_info['p_map'] = self.p_map
        p_info['p_size_x'] = self.p_size_x
        p_info['p_size_y'] = self.p_size_y
        p_info['p_num_pixels'] = self.p_num_pixels
        p_info['p_grid'] = self.p_grid
        db_info['p_info'] = p_info

        # Save it as straight up json
        try:
            db_fp = open(self.db_filename, 'w')
            json.dump(db_info, db_fp)
            db_fp.close()
        except:
            print("Problem saving display db: {}".format(sys.exc_info()[0]))
            tb = sys.exc_info()[2]
            print("Traceback: {}".format(traceback.print_tb(tb)))
            sys.exit(1)
        
    def create(self, c_size_x, c_size_y, p_size_x, p_size_y, fc_host, grain=0, db_filename=None, color=(0,0,0)):
        """Create a new display and object db"""
        self.init_color = color
        self.fc_host = fc_host
        self.db_filename = db_filename
        self.grain = max(self.config['GRAIN'], grain)

        # Canvas map
	self.c_map = {}
        self.c_size_x = c_size_x
        self.c_size_y = c_size_y
        self.c_num_pixels = (c_size_x * c_size_y)
        self.c_grid = [ color ] * self.c_num_pixels

        # Physical pixel map
        self.p_map = {}
        self.p_size_x = p_size_x
        self.p_size_y = p_size_y
        self.p_num_pixels = (p_size_x * p_size_y)
        self.p_grid = [ color ] * self.p_num_pixels

        self.fc_connect()
	self.init_map()
        self.create_trig_tables(self.grain)
        # Don't force a sync here.  This keeps it optional 
        
    def push_pixels(self, pixel_list):
        """Push a list of pixels to the fadecandy"""
        self.fc_conn.put_pixels(pixel_list)

    def push_physical_layer(self):
        """Push our pysical layer to the fadecandy"""
        self.fc_conn.put_pixels(self.get_physical_layer())

    def get_fc_conn(self):
        """Return our fadecandy connect object"""
        return self.fc_conn

    def get_fc_host(self):
        """Return our fadecandy host"""
        return self.fc_host

    def get_max_colors(self):
        """Return max colors"""
        return self.maxColors

    def get_physical_pixel_count(self):
        """Return number of physical pixels"""
        return self.p_num_pixels

    def get_canvas_pixel_count(self):
        """Return number of canvas pixels"""
        return self.c_num_pixels

    def get_canvas_dim(self):
        """Return a touple of (x, y) size for canvas layer"""
        return (self.c_size_x, self.c_size_y)

    def get_physical_dim(self):
        """Return a touple of (x, y) size for physical layer"""
        return (self.p_size_x, self.p_size_y)

    def get_canvasXY_Pixel(self, pixel):
        """Return a touple of (x, y) for a canvas pixel"""
	return self.c_map[pixel]

    def get_physicalXY_Pixel(self, pixel):
        """Return a touple of (x, y) for a physical pixel"""
	return self.p_map[pixel]

    def valid_canvas_coord_XY(self, x, y):
        """Check if this is a valid canvas (x, y) coord"""
        key = "%d,%d" % (x, y)
        (i, j) = self.get_canvas_dim()
        if ((int(x) >= int(i)) or (int(x) < 0) or (int(y) >= int(j)) or (int(y) < 0)):
#            print "No! [%d, %d] [%d, %d]" % (x, y, i, j)
            return False
#        print "Yes! [%d, %d] [%d, %d]" % (x, y, i, j)
        return True

    def valid_physical_coord_XY(self, x, y):
        """Check if this is a valid physical (x, y) coord"""
        key = "%d,%d" % (x, y)
        (i, j) = self.get_physical_dim()
#        print "[%d, %d] [%d, %d]" % (x, y, i, j)
        if ((int(x) >= int(i)) or (int(y) >= int(j))):
#            print "No! [%d, %d] [%d, %d]" % (x, y, i, j)
            return False
#        print "Yes! [%d, %d] [%d, %d]" % (x, y, i, j)
        return True

    def get_canvasRGB_XY(self, x, y):
        """Return the (r, g, b) value of canvas (x, y) point"""
        pixel = self.get_canvas_pixel_XY(x, y)
        return self.c_grid[pixel]

    def set_canvasRGB_XY(self, x, y, rgb):
        """Set the (r, g, b) value of canvas (x, y) point"""
        pixel = self.get_canvas_pixel_XY(x, y)
#        print "[ %d, %d ] = %s" % (x, y, rgb)
        self.c_grid[pixel] = rgb

    def get_physicalRGB_XY(self, x, y):
        """Return the (r, g, b) value of physical (x, y) point"""
        pixel = self.get_physical_pixel_XY(x, y)
        return self.p_grid[pixel]

    def set_physicalRGB_XY(self, x, y, rgb):
        """Set the (r, g, b) value of physical (x, y) point"""
        pixel = self.get_physical_pixel_XY(x, y)
#        print x, y, pixel, rgb, self.physicalDim(), self.physicalPixelCount()
#        self.p_grid[pixel] = rgb
        self.p_grid[pixel] = rgb

    def get_canvas_pixel_XY(self, x, y):
        """Return canvas pixel from (x, y)"""
	key = "%d,%d" % (x, y)
#        print("Key: %s" % (key))
        if (self.valid_canvas_coord_XY(x,y)):
            #  print "Value: %d" % (self.map[key])
            return self.c_map[key]
        else:
            return 0

    def get_physical_pixel_XY(self, x, y):
        """Return physical pixel from (x, y)"""
	key = "%d,%d" % (x, y)
        #  print("Key: %s" % (key))
        if (self.valid_physical_coord_XY(x,y)):
#            print "Value: %d" % (self.p_map[key])
            return self.p_map[key]
        else:
            return 0

    def get_physical_layer(self):
        """Return the layer layer hashmap"""
        return self.p_grid

    # Return a list of r,g,b tuples
    def get_canvas_layer(self):
        """Return the canvas layer hashmap"""
        return self.c_grid

    def clear_physical_layer(self, init_color=[0, 0, 0]):
        """Fill the physical layer with color (r, g, b)"""
        self.init_color = init_color
        self.p_grid = [ self.init_color ] * self.p_num_pixels

    def clear_canvas_layer(self, init_color=[0, 0, 0]):
        """Fill the physical layer with color (r, g, b)"""
        self.init_color = init_color
        self.c_grid = [ self.init_color ] * self.c_num_pixels

    def collapse_NN(self):
        """Collapse physical to canvas using Nearest Neighbor"""
        scale_x = self.c_size_x / float(self.p_size_x)
        scale_y = self.c_size_y / float(self.p_size_y)
        print("Scale: [{}, {}]".format(scale_x, scale_y))

        for x in range(0, self.p_size_x):
            for y in range(0, self.p_size_y):
                sum_rgb = [ 0.0, 0.0, 0.0 ]
                loc_rgb = None
                avg_points = 0

                c_x = x * scale_x
                c_y = y * scale_y

                # Sum x + scale_x; x - scale_x
                for offset_x in range(int(c_x - scale_x), int(c_x + scale_x)):
                    if self.valid_canvas_coord_XY(offset_x, c_y):
                        loc_rgb = self.get_canvasRGB_XY(offset_x, c_y)
                        sum_rgb[0] += loc_rgb[0]
                        sum_rgb[1] += loc_rgb[1]
                        sum_rgb[2] += loc_rgb[2]
                        avg_points += 1
                # Sum y + scale_y; y - scale_y
                for offset_y in range(int(c_y - scale_y), int(c_y + scale_y)):
                    if self.valid_canvas_coord_XY(c_x, offset_y):
                        loc_rgb = self.get_canvasRGB_XY(c_x, offset_y)
                        sum_rgb[0] += loc_rgb[0]
                        sum_rgb[1] += loc_rgb[1]
                        sum_rgb[2] += loc_rgb[2]
                        avg_points += 1

                avg_rgb = ( sum_rgb[0] / float(avg_points),
                            sum_rgb[1] / float(avg_points),
                            sum_rgb[2] / float(avg_points) )
                self.set_physicalRGB_XY(x, y, avg_rgb)
#                print("[{}] [{}, {}] sum_rgb: [{}]  avg_rgb: [{}]".format(avg_points, x, y, sum_rgb, avg_rgb))
                avg_points = 0

        return self.p_grid

    def collapse_flat(self, x, y):
        """Collapse physical to canvas flatly using (x, y)"""
        for pixel_x in range(0, self.p_size_x):
            for pixel_y in range(0, self.p_size_y):
                c_rgb = self.get_canvasRGB_XY(x+pixel_x, y+pixel_y)
#                print pixel_x, pixel_y, pixel, c_rgb
                self.set_physicalRGB_XY(pixel_x, pixel_y, c_rgb)

    def create_trig_tables(self, grain):
        two_pi = math.pi * 2.0
        self.sin_table = []
        self.cos_table = []

        for index in range(0, grain):
            self.sin_table.append(math.sin((two_pi/grain) * index))
            self.cos_table.append(math.cos((two_pi/grain) * index))

    def comp_gradient(self, g_list, grain=0):
        """Compute our multi-gradient scale here.  If we're going to use the
        same gradient all the time, this will make things faster
        because it creates a list and stores it for the next query so
        it doesn't need to be re-computed each query.
        """
        # Our gradient list of rgb values to be computed
        grain = grain if grain > 0 else self.config['GRAIN']
        self.grad_table = [ (0.0, 0.0, 0.0) ] * grain

        for e_list in g_list:
            # Starting rgb value
            start_rgb = e_list[0]
            # Ending value
            end_rgb = e_list[1]
            # Start position in the whole gradient
            s_index = int(e_list[2][0] * grain)
            # End position in the whole gradient
            e_index = int(e_list[2][1] * grain)
            # Our local time slice
            delta = e_index - s_index
            # Our gradient size per slice
            (d_r, d_g, d_b) = ( (end_rgb[0] - start_rgb[0]) / float(delta),
                                (end_rgb[1] - start_rgb[1]) / float(delta),
                                (end_rgb[2] - start_rgb[2]) / float(delta) )
            print start_rgb, end_rgb, s_index, e_index, delta, grain, d_r, d_g, d_b
            # Make RGB for each slice
            for d_index in range(delta):
                self.grad_table[d_index + s_index] = ( (d_r * d_index) + start_rgb[0],
                                                       (d_g * d_index) + start_rgb[1],
                                                       (d_b * d_index) + start_rgb[2] )

    def sin_tab(self, index):
        if (len(self.sin_table) > index):
            return self.sin_table[index]
        return 0

    def cos_tab(self, index):
        if (len(self.cos_table) > index):
            return self.cos_table[index]
        return 0
            
    def grad_tab(self, index):
        # Just cap both ends so we always have a color
        if (index < 0):
            return self.grad_table[0]
        elif (index >= len(self.grad_table)):
            return self.grad_table[-1]

        return self.grad_table[int(index)]

    def init_map(self):
        """Create the mapping from x,y coord to pixel number
        This can be used to map any coord to any pixel.  This mapping
        is specific to my own LED layout. A pixel = [ r, g, b ]
        """
        print("Initializing pixel mapping...")
	# Pixel Num -> Strand Pos
        # Row 1
        # 0:63 -> 63:0
	pos = 63  # 0
	for pixel in range(0,64):
            # Map back and forth
            key = "0,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 64:127 -> 960:1023
        pos = 960
        for pixel in range(64, 128):
            # Map back and forth
            key = "0,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1
                
        # Row 2
        # 128:191 -> 127:64
        pos = 127
        for pixel in range(0, 64):
            # Map back and forth
            key = "1,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 192:255 -> 896:959
        pos = 896
        for pixel in range(64, 128):
            # Map back and forth
            key = "1,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1
                        
        # Row 3
        # 256:319 -> 191:128
        pos = 191
        for pixel in range(0, 64):
            # Map back and forth
            key = "2,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1
            
        # 320:383 -> 832:895
        pos = 832
        for pixel in range(64, 128):
            # Map back and forth
            key = "2,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Row 4
        # 384:447 -> 255:192
        pos = 255
        for pixel in range(0, 64):
            # Map back and forth
            key = "3,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 448:511 -> 768:831
        pos = 768
        for pixel in range(64, 128):
            # Map back and forth
            key = "3,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Row 5
        # 512:575 -> 319:256
        pos = 319
        for pixel in range(0, 64):
            # Map back and forth
            key = "4,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 576:639 -> 704:767
        pos = 704
        for pixel in range(64, 128):
            # Map back and forth
            key = "4,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Row 6
        # 640:703 -> 383:320
        pos = 383
        for pixel in range(0, 64):
            # Map back and forth
            key = "5,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 704:767 -> 640:703
        pos = 640
        for pixel in range(64, 128):
            # Map back and forth
            key = "5,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Row 7
        # 768:831 -> 447:384
        pos = 447
        for pixel in range(0, 64):
            # Map back and forth
            key = "6,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 832:895 -> 576:639
        pos = 576
        for pixel in range(64, 128):
            # Map back and forth
            key = "6,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Row 8
        # 896:959 -> 511:448
        pos = 511
        for pixel in range(0, 64):
            # Map back and forth
            key = "7,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos -= 1

        # 960:1023 -> 512:575
        pos = 512
        for pixel in range(64, 128):
            # Map back and forth
            key = "7,%d" % (pixel)
	    self.p_map[key] = pos
            self.p_map[pos] = key
	    pos += 1

        # Map the canvas layer flatly
        for pixel_x in range(0, self.c_size_x):
            for pixel_y in range(0, self.c_size_y):
                pixel = (pixel_x * self.c_size_y) + pixel_y
		self.c_map["%d,%d" % (pixel_x, pixel_y)] = pixel
                self.c_map["%d" % (pixel)] = (pixel_x, pixel_y)


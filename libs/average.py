
'''Maintain a rolling average of a list of numbers'''
class rolling(object):

    def __init__(self, size, length):
        self.size = size
        self.length = length

        self.rolling = [ [ 0.0 ] * self.size ] * self.length
        self.avgs = [ 0.0 ] * self.size

    def roll(self, num_list):
        if (len(num_list) != self.size):
            raise Exception("Number list not the right size: {} != {}".format(len(num_list), self.size))
        # FILO
        self.rolling.insert(0, num_list)
        self.rolling.pop()

    # Compute all the averages in the list
    def make_avgs(self):
        for s_index in range(0, self.size):
            self.avgs[s_index] = self.make_avg(s_index)

        return self.avgs

    # Compute the average for just one element in the list    
    def make_avg(self, index):
        if (index < 0 or index >= self.size):
            raise Exception("Bad index: {}  Valid 0 - {}.".format(index, self.size-1))

        l_sum = 0
        for l_index in range(0, self.length):
            l_line = self.rolling[l_index]
            l_sum += l_line[index]

        return l_sum/self.length

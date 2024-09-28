from random import seed, randint
from time import time
from typing import List

seed(time())
#seed(100)

class Parameter():
    def __init__(self, cc: int, value: int = 127, value_min: int = 0, value_max: int = 127, name='n/a', ):
        self.cc = cc
        self.value = value
        self.value_min = value_min
        self.value_max = value_max
        self._check_value_bounds()
        self.name = name

    def generate_random_value(self):
        val = randint(self.value_min, self.value_max)
        self.set_value(val)

    def set_value(self, val):
        self.value = val

    def _check_value_bounds(self):
        if (self.value < self.value_min):
            self.set_value(self.value_min)
        elif (self.value > self.value_max):
            self.set_value(self.value_max)
        


class ParameterCollection():

    def __init__(self):
        self.params = []
        pass

    def add_parameter(self, param):
        self.params.append(param)



class ParameterCSVReader:
    def __init__(self):
        pass




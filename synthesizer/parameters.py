from random import seed, randint
from time import time
from typing import List
from collections import UserList, UserDict
import pandas as pd

seed(time())
#seed(100)

class Parameter():
    def __init__(self, cc: int, value: int = 127, value_min: int = 0, value_max: int = 127, name='n/a', ):
        self.cc = cc
        self.name = name
        self.value = value
        self.value_min = value_min
        self.value_max = value_max
        self._check_value_bounds()

    def generate_random_value(self):
        val = randint(self.value_min, self.value_max)
        self.set_value(val)

    def set_value(self, val):
        self.value = val

    def _check_value_bounds(self):
        # set to minimum if it's below
        if (self.value < self.value_min):
            self.set_value(self.value_min)
        # set to maximum if it's above
        elif (self.value > self.value_max):
            self.set_value(self.value_max)
        
    def __str__(self):
        return f'cc: {self.cc}, value: {self.value}'

    def __repr__(self):
        return f'Parameter - cc: {self.cc}, value: {self.value}'

class ParameterCollection(UserList):
# https://docs.python.org/3/library/collections.html#collections.UserList

    """
    def __init__(self):
        super().__init__
        #self.params = []
        self.data = []
    """

    def add_parameter(self, param):
        #self.params.append(param)
        self.data.append(param)

    def create_paramter(self, cc:int , value:int = 127):
        new_param = Parameter(cc, value)
        self.add_parameter(new_param)

    def create_paramter(self, cc:int , value:int , value_min:int, value_max:int):
        new_param = Parameter(cc, value, value_min, value_max)
        self.add_parameter(new_param)




class ParameterCSVReader(UserList):
    def __init__(self, csv_file_path):
        super().__init__(self)
        self.csv_file_path = csv_file_path
        self.read_csv()

    def _set_df(self):
        self._df = pd.read_csv(self.csv_file_path)
        self._df = self._df[['parameter_name', 'cc_msb', 'cc_min_value', 'cc_max_value', 'section']]

    def read_csv(self):
        self._set_df()
        for row, data in self._df.iterrows():
            self.data.append(data.to_dict())

    def get_parameter_collection(self):
        pass



class AnalogRytmParameterCSVReader(ParameterCSVReader):
    def __init__(self, csv_file_path):
        super().__init__(self)
        self._df = pd.read_csv("synthesizer/rytm-limited.csv")
        self.csv_file_path = csv_file_path
        self.read_csv()



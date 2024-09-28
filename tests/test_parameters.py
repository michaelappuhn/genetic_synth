from unittest import TestCase
from synthesizer.parameters import Parameter

p1 = Parameter(1)
p2 = Parameter(2, 120)
p3 = Parameter(3, 59, 50)
p4 = Parameter(4, 60, 51, 100)
p5 = Parameter(4, 40, 52, 101)
p6 = Parameter(4, 120, 52, 102)

class TestParameter(TestCase):

    def test_cc_change(self):
        self.assertEqual(p1.cc, 1)
        self.assertEqual(p2.cc, 2)
        self.assertEqual(p3.cc, 3)
        self.assertEqual(p4.cc, 4)

    def test_default(self):
        # p
        self.assertEqual(p1.value, 127)
        self.assertEqual(p1.value_min, 0)
        self.assertEqual(p1.value_max, 127)
        self.assertEqual(p1.name, 'n/a')
        # p2
        self.assertEqual(p2.value_min, 0)
        self.assertEqual(p2.value_max, 127)
        self.assertEqual(p2.name, 'n/a')
        # p3
        self.assertEqual(p2.value_max, 127)
        self.assertEqual(p2.name, 'n/a')


    def test_val_change(self):
        self.assertEqual(p2.value, 120)
        self.assertEqual(p3.value, 59)

    def test_val_min_change(self):
        self.assertEqual(p3.value_min, 50)
        self.assertEqual(p4.value_min, 51)

    def test_val_max_change(self):
        self.assertEqual(p4.value_max, 100)

    def test_out_of_bounds(self):
        # if a value is below the min, increase to the min
        self.assertEqual(p5.value, 52)

        # if a value is above the max, decrease to the max
        self.assertEqual(p6.value, 102)

"""
# Tester
param_collect = ParameterCollection()

for i in range(0,20):
    p =Parameter(i+1,3)
    p.generate_random_value()
    param_collect.add_parameter(p)

for p in param_collect.params:
    print (p.cc, p.value)
"""

"""
class Parameter():
    def __init__(self, cc: int, value: int = 127, value_min: int = 0, value_max: int = 127, name='n/a', ):
        self.cc = cc
        self.value = value
        self.value_min = value_min
        self.value_max = value_max
        self.name = name

    def generate_random_value(self):
        val = randint(self.value_min, self.value_max)
        self.set_value(val)

    def set_value(self, val):
        self.value = val

"""

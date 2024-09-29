from unittest import TestCase
from synthesizer.parameters import Parameter, ParameterCollection, ParameterCSVReader, AnalogRytmParameterCSVReader

p1 = Parameter(1)
p2 = Parameter(2, 120)
p3 = Parameter(3, 59, 50)
p4 = Parameter(4, 60, 51, 100)
p5 = Parameter(5, 40, 52, 101)
p6 = Parameter(6, 120, 52, 102)
p7 = Parameter(7, 110, 52, 102)
p8 = Parameter(8, 30, 12, 102)

class TestParameter(TestCase):

    def test_cc_set(self):
        self.assertEqual(p1.cc, 1)
        self.assertEqual(p2.cc, 2)
        self.assertEqual(p3.cc, 3)
        self.assertEqual(p4.cc, 4)
        self.assertEqual(p5.cc, 5)
        self.assertEqual(p6.cc, 6)

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

    def test_random(self):
        p7.generate_random_value()
        self.assertNotEqual(p7.value, 110)

    def test_value_set(self):
        p8.set_value(20)
        self.assertEqual(p8.value, 20)


    def test_out_of_bounds(self):
        # if a value is below the min, increase to the min
        self.assertEqual(p5.value, 52)

        # if a value is above the max, decrease to the max
        self.assertEqual(p6.value, 102)



class TestParameterCollection(TestCase):
    def setUp(self):
        self.pc = ParameterCollection()

        for i in range(0,20):
            p = Parameter(i+1,i+1)
            self.pc.add_parameter(p)

       
    def test_has_parameters(self):
        #self.assertIsInstance(param_collect.params[0], Parameter)
        self.assertIsInstance(self.pc[0], Parameter)

    def test_add_parameter(self):
        self.pc.add_parameter(p1)
        #self.assertEqual(len(self.pc.params), 21)
        self.assertEqual(len(self.pc), 21)
        #self.assertEqual(self.pc[-1].cc, 1)

    def test_iteration(self):
        for i in range(0, len(self.pc)):
            self.assertIsInstance(self.pc[i], Parameter)
        self.assertEqual(self.pc[2].cc, 3)



class TestParameterCSVReader(TestCase):

    def setUp(self):
        self.pcsv = ParameterCSVReader("synthesizer/rytm-limited.csv")
        
    def test_csv_load(self):
        #print(pcsv._df)
        self.assertEqual(self.pcsv[0]['cc_msb'], 15)

    def test_get_parameter_collection(self):
        self.assertIsInstance(self.pcsv.get_parameter_collection(), ParameterCollection)
        self.assertEqual(self.pcsv.get_parameter_collection()[0].cc, 15)

    def test_get_random_parameter_collection(self):
        self.assertIsInstance(self.pcsv.get_random_parameter_collection(), ParameterCollection)
        self.assertNotEqual(self.pcsv.get_parameter_collection()[1].value, self.pcsv.get_parameter_collection()[1].value_max)
        print(self.pcsv.get_parameter_collection()[1].value)

class TestAnalogRytmParameterCSVReader(TestCase):

    def setUp(self):
        self.pcsv = AnalogRytmParameterCSVReader()
 
    def test_csv_load(self):
        #print(self.pcsv._df)
        self.assertEqual(self.pcsv[0]['cc_msb'], 16)

    def test_get_parameter_collection(self):
        self.assertIsInstance(self.pcsv.get_parameter_collection(), ParameterCollection)
        self.assertEqual(self.pcsv.get_parameter_collection()[0].cc, 16)

    def test_get_random_parameter_collection(self):
        self.assertIsInstance(self.pcsv.get_random_parameter_collection(), ParameterCollection)
        self.assertNotEqual(self.pcsv.get_parameter_collection()[1].value, self.pcsv.get_parameter_collection()[1].value_max)
        print(self.pcsv.get_parameter_collection()[1].value)



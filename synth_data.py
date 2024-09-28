import pandas as pd
from parameters import ParameterCollection

class MidiDataParamCollection:
    pass

class MidiCSVReader:
    def __init__(self, csv_file_name):
        self.df = pd.read_csv(csv_file_name)

    def get_cc_data(self):
        cc_vals = []
        for num, row in self.df.iterrows():
            cc_vals.append(
                {
                    'param': row['parameter_name'],
                    'cc_msb': row['cc_msb'],
                    'cc_min': row['cc_min_value'],
                    'cc_max': row['cc_max_value'],
                    'section': row['section']
                }
            )
        return cc_vals

class AnalogRytmMidiCSVReader(MidiCSVReader):
    sections = [
        "Trig",
        "Kit",
        "Filter",
        "Amp",
        "LFO"
    ]

    def __init__(self):
        # data pulled from https://github.com/pencilresearch/midi/blob/main/Elektron/Rytm%20MKII.csv 
        # modified to select parameters that are useful to me
        self.df = pd.read_csv("rytm-limited.csv")


def main():
    a = AnalogRytmMidiCSVReader()

    for i in range(0, len(a.sections)):
        print("---")
        print(a.sections[i])
        for j in a.get_cc_data():
            print(j['param'], "CC:", j['cc_msb'], j['section'])


main()

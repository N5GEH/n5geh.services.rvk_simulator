import sys
import pandas as pd
import csv
import time
import numpy as np
import ssl


import demonstrator
import json


################## Defines ###################


def main():
    DM = demonstrator.DummyDemonstrator("./config.json")
    print('enter DM.main()')
    DM.main()
    print('left DM.main()')


if __name__ == "__main__":
    main()


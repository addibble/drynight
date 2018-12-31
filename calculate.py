import sqlite3
import math
from datetime import datetime
from collections import defaultdict
#import numpy as np
#import pandas as pd
#import sys
#import matplotlib.pyplot as plt

db = sqlite3.connect("./data.db")
c = db.cursor()

result = c.execute("select * from accel_raw")

smooth_factor = 0.5
axes={'x': 1, 'y': 2, 'z': 3}
x='x'
y='y'
z='z'

diffs = defaultdict(lambda: 0)
mins = defaultdict(lambda: 0)
maxs = defaultdict(lambda: 0)

for row in result:
    try:
        diffs = {axis: abs(row[axis_num]-vals[axis]) for axis, axis_num in axes.items()}
    except NameError:
        diffs = {}
    vals = {axis: row[axis_num] for axis, axis_num in axes.items()}
    norm_vals = {axis: float(row[axis_num])/128.0 for axis, axis_num in axes.items()}
    mins = {axis: min(mins[axis], vals[axis]) for axis in axes.keys()}
    maxs = {axis: max(maxs[axis], vals[axis]) for axis in axes.keys()}
#    try:
#        x = smooth_factor * float(x_raw) + (1.0 - smooth_factor) * float(x)
#        y = smooth_factor * float(y_raw) + (1.0 - smooth_factor) * float(y)
#        z = smooth_factor * float(z_raw) + (1.0 - smooth_factor) * float(z)
#    except NameError:
#        x = float(x_raw)
#        y = float(y_raw)
#        z = float(z_raw)
    r = math.sqrt(sum([pow(norm_vals[axis], 2) for axis in axes.keys()]))
    rvec = {axis: math.degrees(math.acos(norm_vals[axis]/r)) for axis in axes.keys()}
    roll  = math.degrees(math.atan2(norm_vals[x],norm_vals[z]))
    pitch = math.degrees(math.atan2(norm_vals[y],norm_vals[z]))
    print("{} roll {} pitch {} rvec {} r {} diff {} xyz {}".format(datetime.fromtimestamp(row[0]).ctime(), roll, pitch, rvec, r, sum(diffs.values()), vals))
print(mins, maxs)
#df = pd.DataFrame.from_csv(sys.argv[1], index_col=None)
#print df.head
#df['time'] = pd.to_datetime(df['time'], unit='s')
#df = df.set_index('time')
#print df.describe()
## plt.subplot('111')
## df.plot(kind='line')
## plt.subplot('122')
## df.plot(kind='histogram')
#df.rolling(120).mean().plot()
#plt.show()

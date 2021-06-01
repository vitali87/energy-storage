import pandas as pd
import numpy as np

n_hlf_hrs = 48 # There are 48 half-hours in a day

t = range(1,n_hlf_hrs + 1)
dt = pd.date_range(start='01/01/2018 00:00:00', 
                   end='31/12/2020 23:30:00', 
                   freq="24H")

print(dt.values[0])
# n_days = int(len(dt)/n_hlf_hrs) - 1

profits_ = pd.read_csv("profits.csv",header=None) 
print(profits_)

print(len(dt))
print(len(profits_.index))
print(dt)
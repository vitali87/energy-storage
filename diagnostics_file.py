import pandas as pd
import numpy as np
import pandaspyomo as pdpo

n_hlf_hrs = 48 # There are 48 half-hours in a day

t = range(1,n_hlf_hrs + 1)
dt = pd.date_range(start='01/01/2018 00:00:00', 
                   end='31/12/2020 23:30:00', 
                   freq="24H")
dtt = pd.date_range(start='01/01/2018 00:00:00', 
                   end='31/12/2020 23:30:00', 
                   freq="0.5H")
n_days = int(len(dtt)/n_hlf_hrs)

# n_days = int(len(dt)/n_hlf_hrs) - 1

profits_ = pd.read_csv("profits.csv",header=None) 
print(profits_)

print(len(dt))
print(n_days)
print(len(profits_.index))
print(dt)
# profits_["dt"] = dt
dates = pd.date_range('01/01/2018', periods=1096)
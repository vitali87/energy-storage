import pandas as pd
import numpy as np

dt = pd.date_range(start='01/01/2018 00:00:00',
                   end='31/12/2020 23:30:00',
                   freq="0.5H")
df_OBJ = pd.read_excel("profit.xlsx")

tmp1 = pd.to_datetime(dt.values) 
years_unique = tmp1.year.unique().values # Finding unique years in the given period

yearly_profits = [] # This list will collect yearly profits 
for k in years_unique:
    B = df_OBJ[df_OBJ['dt'].str.contains(str(k))]
    C = B["obj"].sum().tolist()
    yearly_profits.append(C)

df = pd.DataFrame()
df['Year'] = years_unique
df['Profit'] = yearly_profits

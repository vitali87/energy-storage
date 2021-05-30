import pandas as pd
import numpy as np

# Pre-processing part
# Putting Market 3 data in a half-hour format and saving
df = pd.read_excel(r'Copy of Market Data.xlsx',
                    sheet_name = "Daily data",
                    usecols = "A:B")
x = np.array(df["Market 3 Price [£/MWh]"])
y = np.repeat(x, 48, axis=0)
dt = pd.date_range(start='01/01/2018 00:00:00', end='31/12/2020 23:30:00', freq="0.5H")
M3data = {'DateTime':dt,'Price':y} 
M3 = pd.DataFrame(M3data)
M3.to_excel("Market_3_data.xlsx",
                sheet_name = "Daily data_formatted",
                index=False)
M3.to_csv('Market_3_data.dat')
M3.to_csv('Market_3_data.csv')
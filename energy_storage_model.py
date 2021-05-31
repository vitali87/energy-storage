import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import csv
import pandas as pd
import numpy as np

## Global declarations ####
N_hlf_hrs = 48 # There are 48 half-hours in a day
cap_max = 4 # max volume of storage is 4MWh
discharge_rate = charge_rate = 1 # discharge/charge rate possible for half hour is 1MW
N_markets = 3 # How many market are being considered?
discharge_loss_rate = charge_loss_rate = 0.05 # Fraction of energy imported/exported from/to grid that is lost prior to reaching storage/grid 
dch_remain =  1 - discharge_loss_rate
ch_remain =  1 - charge_loss_rate

## Pre-processing part####

# Calculate how many days there are in the given period
t = range(1,N_hlf_hrs + 1)
dt = pd.date_range(start='01/01/2018 00:00:00', 
                   end='31/12/2020 23:30:00', 
                   freq="0.5H")
N_days = int(len(dt)/N_hlf_hrs)

# Reading Market 1 and 3 data
df12 = pd.read_excel(r'Copy of Market Data.xlsx',
                    sheet_name = "Half-hourly data",
                    usecols = "B:C")
y1 = df12['Market 1 Price [£/MWh]']
y2 = df12['Market 2 Price [£/MWh]']

# Putting Market 3 data in a half-hour format
df3 = pd.read_excel(r'Copy of Market Data.xlsx',
                    sheet_name = "Daily data",
                    usecols = "A:B")
x = np.array(df3["Market 3 Price [£/MWh]"])
y3 = np.repeat(x, N_hlf_hrs, axis=0)

# Inital value for storage level at the onset of optimisation. 
# Assuming it is half full at the start. 
# It will naturally fluctuate after each optimisation
cap_end = cap_max/2 

## Iterative optimisation for each day ####
for k in range(1, N_days):

    # Decomposing all data into daily chunks
    y1_ = y1[(k-1)*N_hlf_hrs:k*N_hlf_hrs]
    y2_ = y2[(k-1)*N_hlf_hrs:k*N_hlf_hrs]
    y3_ = y3[(k-1)*N_hlf_hrs:k*N_hlf_hrs]
    M1data = {'I':1,'J':t,'p':y1_} 
    M2data = {'I':2,'J':t,'p':y2_}   
    M3data = {'I':3,'J':t,'p':y3_} 
    
    # Converting to Panda's df and row-binding
    M1 = pd.DataFrame(M1data)
    M2 = pd.DataFrame(M2data)
    M3 = pd.DataFrame(M3data)
    M = pd.concat([M1,M2,M3], ignore_index=True)

    # Saving input file for the Abstract model
    M.to_csv("data.csv", index=False)
    
    ### Modelling part ####
    opt = pyo.SolverFactory('glpk')
    
    model = pyo.AbstractModel()
    
    model.m = pyo.Param(within=pyo.NonNegativeIntegers,default = N_markets)
    model.n = pyo.Param(within=pyo.NonNegativeIntegers,default = N_hlf_hrs)
    
    model.I = pyo.RangeSet(1, model.m)
    model.J = pyo.RangeSet(1, model.n)

    model.p = pyo.Param(model.I,model.J) # Prices in Market 1 
    model.cap = pyo.Param(default = cap_max) # Maximum volume of energy that the battery can store (MWh)
    model.dch_r = pyo.Param(default = discharge_rate) # discharge rate possible for half hour is 1MW
    model.ch_r = pyo.Param(default = charge_rate) # charge rate possible for half hour is 1MW
    # model.dch_loss_r = pyo.Param(default = discharge_loss_rate) # discharge rate possible for half hour is 1MW
    # model.ch_loss_r = pyo.Param(default = charge_loss_rate) # charge rate possible for half hour is 1MW

    # Discharging variables for Market 1,2,3
    model.x = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals)
    model.x_r = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals) # remaining after discharge losses

    # Charging variables for Market 1,2,3. For Market 3 it is equal constant charge rate for each half-hour period
    model.y = pyo.Var(model.I, model.J, domain=pyo.NonNegativeReals)
    model.y_r = pyo.Var(model.I, model.J, domain=pyo.NonNegativeReals) # remaining after charge losses

    # Volume variable
    model.v = pyo.Var(model.J, domain=pyo.NonNegativeReals)
    # Binary charging/discharging mode: 1 - discharging, 0 - charging
    model.mode = pyo.Var(model.J, domain=pyo.Binary)
    # Binary status of Market 3: 1 - used, 0 - not used
    model.used = pyo.Var(domain=pyo.Binary)
    # Binary charging/discharging mode of Market 3: 1 - discharging, 0 - charging
    model.mode_3 = pyo.Var(domain=pyo.Binary)

    # Objective function: maximise daily arbitrage profit
    def obj_expression(m):
        # Actual export is less than what's being discharged, so being paid less based on actual electricity delivered after losses
        # Actual import is less but we pay for the full charge amount as losses incur after electricity is taken from the grid
        return (-pyo.summation(m.p, m.x) + pyo.summation(m.p, m.y))
    model.OBJ = pyo.Objective(rule=obj_expression,sense=pyo.minimize)

    def cons_discharge_cap(m, j):
        return sum(m.x[i,j] for i in m.I) <= m.v[j]
    model.DischargeCapConstraint = pyo.Constraint(model.J, rule=cons_discharge_cap)

    def cons_charge_cap(m, j):
        return sum(m.y[i,j] for i in m.I) <= m.cap - m.v[j]
    model.ChargeCapConstraint = pyo.Constraint(model.J, rule=cons_charge_cap)

    def cons_discharge_rate_combined(m,j):
        return sum(m.x[i,j] for i in m.I) <= m.dch_r * m.mode[j]
    model.DischargeRateCombConstraint = pyo.Constraint(model.J, rule=cons_discharge_rate_combined)

    def cons_charge_rate_combined(m,j):
        return sum(m.y[i,j] for i in m.I) <= m.ch_r * (1 - m.mode[j])
    model.ChargeRateCombConstraint = pyo.Constraint(model.J, rule=cons_charge_rate_combined)

    def cons_volume_change(m,j):
        if j == 1:
            # Storage volume resumes from the same level where it stopped in previous optimisation
            return (m.v[j] == cap_end) 
        # Import into storage incures losses, so actual volume imported during half-hour period is less than actual charge
        return  (m.v[j] ==  m.v[j-1] - sum(m.x[i,j] - m.y[i,j] for i in m.I))
    model.VolumeChangeConstraint = pyo.Constraint(model.J, rule=cons_volume_change)

    def cons_discharge_M3(m):
        return sum(m.x[3,j] for j in m.J) <= m.mode_3 * m.cap
    model.DischargeM3Constraint = pyo.Constraint(rule=cons_discharge_M3)

    def cons_discharge_sum_M3(m,j):
        if j == 1:
            return pyo.Constraint.Skip
        return m.x[3,j-1] == m.x[3,j]
    model.DischargeSumM3Constraint = pyo.Constraint(model.J, rule=cons_discharge_sum_M3)

    def cons_charge_M3(m):
        return sum(m.y[3,j] for j in m.J) <= (1 - m.mode_3) * m.cap
    model.ChargeM3Constraint = pyo.Constraint(rule=cons_charge_M3)

    def cons_charge_sum_M3(m,j):
        if j == 1:
            return pyo.Constraint.Skip
        return m.y[3,j-1] == m.y[3,j]
    model.ChargeSumM3Constraint = pyo.Constraint(model.J, rule=cons_charge_sum_M3)

    def cons_M3_ch_used(m,j):
        return m.y[3,j]  <= m.used * m.cap
    model.M3ChUsedConstraint = pyo.Constraint(model.J, rule=cons_M3_ch_used)

    def cons_M3_dch_used(m,j):
        return m.x[3,j]  <= m.used * m.cap
    model.M3DchUsedConstraint = pyo.Constraint(model.J, rule=cons_M3_dch_used)

    def cons_mode_relation1(m,j):
        return m.mode[j] - m.mode_3 <= 1 - m.used
    model.ModeRelation1Constraint = pyo.Constraint(model.J, rule=cons_mode_relation1)

    def cons_mode_relation2(m,j):
        return m.mode[j] - m.mode_3 >= m.used - 1
    model.ModeRelation2Constraint = pyo.Constraint(model.J, rule=cons_mode_relation2)

    # def cons_discharge_remain(m, i, j):
    #     return m.x_r[i,j] == (1 - m.dch_loss_r) * m.x[i,j]
    # model.DischargeRemainConstraint = pyo.Constraint(model.I,model.J, rule=cons_discharge_remain)

    # def cons_charge_remain(m, i, j):
    #     return m.y_r[i,j] == (1 - m.ch_loss_r) * m.y[i,j]
    # model.ChargeRemainConstraint = pyo.Constraint(model.I,model.J, rule=cons_charge_remain)

    ### Data read ####
    data = pyo.DataPortal()
    data.load(filename = 'data.csv',  
                param = model.p)
    
    ### Solve the problem ####
    instance = model.create_instance(data)
    results = opt.solve(instance)

    # Find the end level of storage volume from previous day which will be the start level on the next day
    cap_end = instance.v[48].value

    ### Output generation part #####
    with open('result.csv','a') as f1:
        for v in instance.component_objects(pyo.Var, active = True):
            varobject = getattr(instance, str(v))
            writer = csv.writer(f1, 
                                delimiter = '\t',
                                lineterminator = '\n',)
            for index in varobject:
                row =  (v,
                        index, 
                        varobject[index].value)
                writer.writerow(row)

    ### Progress of optimisation ####  
    print("Day ",k,"/",N_days," optimisation is finished")      

## Post-processing ####
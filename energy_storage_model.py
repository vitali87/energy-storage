import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import pandas as pd
import numpy as np

## Global declarations ####
n_hlf_hrs = 48 # There are 48 half-hours in a day
cap_max = 4 # max volume of storage is 4MWh
discharge_rate = charge_rate = 1 # discharge/charge rate possible for half hour is 1MW
n_markets = 3 # How many market are being considered?
dch_loss_rate = ch_loss_rate = 0.05 # Fraction of energy imported/exported from/to grid which is lost prior to reaching storage/grid

## Pre-processing part####

# Calculate number of days in given period
t = range(1,n_hlf_hrs + 1)

# This will be also used in Post-processing part
dt = pd.date_range(start='01/01/2018 00:00:00',
                   end='31/12/2020 23:30:00',
                   freq="0.5H")
dtd = pd.date_range(start='01/01/2018 00:00:00',
                   end='31/12/2020 23:30:00',
                   freq="24H")
n_days = len(dt) // n_hlf_hrs

# Reading Market 1 and 3 data
df12 = pd.read_excel(r'Copy of Market Data.xlsx',
                    sheet_name = "Half-hourly data",
                    usecols = "B:C")
y1 = df12['Market 1 Price [£/MWh]']
y2 = df12['Market 2 Price [£/MWh]']

# Putting Market 3 data in half-hour format
df3 = pd.read_excel(r'Copy of Market Data.xlsx',
                    sheet_name = "Daily data",
                    usecols = "A:B")
x = np.array(df3["Market 3 Price [£/MWh]"])
y3 = np.repeat(x, n_hlf_hrs, axis=0)

# Inital value for storage level at the onset of optimisation.
# Assuming half full at start.
# It'll naturally fluctuate after each optimisation
cap_end = cap_max/2

# These dataframes collect results
df_OBJ = df_X = df_Y = df_V = df = pd.DataFrame()

## Iterative optimisation part: one for each day: ####
# There is no way to parallelise this process as start/end storage levels depend on each other
for k in range(1, n_days + 1):

    # Decomposing all data into daily chunks
    idx_start = (k-1)*n_hlf_hrs
    idx_end = k*n_hlf_hrs
    y1_ = y1[idx_start:idx_end]
    y2_ = y2[idx_start:idx_end]
    y3_ = y3[idx_start:idx_end]
    M1data = {'I':1,'J':t,'p':y1_}
    M2data = {'I':2,'J':t,'p':y2_}
    M3data = {'I':3,'J':t,'p':y3_}

    # Converting to Panda's df and row-binding
    M1 = pd.DataFrame(M1data)
    M2 = pd.DataFrame(M2data)
    M3 = pd.DataFrame(M3data)
    M = pd.concat([M1,M2,M3], ignore_index=True)

    # Saving input file for the AbstractModel
    M.to_csv("data.csv", index=False)

    ### Modelling part ####
    opt = pyo.SolverFactory('glpk')

    model = pyo.AbstractModel()

    model.m = pyo.Param(within=pyo.NonNegativeIntegers,default = n_markets)
    model.n = pyo.Param(within=pyo.NonNegativeIntegers,default = n_hlf_hrs)

    model.I = pyo.RangeSet(1, model.m)
    model.J = pyo.RangeSet(1, model.n)

    model.p = pyo.Param(model.I,model.J) # Prices in Market 1
    model.cap = pyo.Param(default = cap_max) # Maximum volume of energy that the battery can store (MWh)
    model.dch_r = pyo.Param(default = discharge_rate) # discharge rate possible for half hour is 1MW
    model.ch_r = pyo.Param(default = charge_rate) # charge rate possible for half hour is 1MW
    model.dch_loss_r = pyo.Param(default = dch_loss_rate)
    model.ch_loss_r = pyo.Param(default = ch_loss_rate)

    # Discharging variables for Market 1,2,3
    model.x = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals)
    model.x_r = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals) # electricity remaining after discharge losses

    # Charging variables for Market 1,2,3. For Market 3, it is equal constant charge rate for each half-hour period
    model.y = pyo.Var(model.I, model.J, domain=pyo.NonNegativeReals)
    model.y_r = pyo.Var(model.I, model.J, domain=pyo.NonNegativeReals) # electricity remaining after charge losses

    # Volume variable
    model.v = pyo.Var(model.J, domain=pyo.NonNegativeReals)
    # Binary charging/discharging mode, Market 1&2: 1 - discharging, 0 - charging
    model.mode = pyo.Var(model.J, domain=pyo.Binary)
    # Binary status of Market 3: 1 - used, 0 - not used
    model.used = pyo.Var(domain=pyo.Binary)
    # Binary charging/discharging mode of Market 3: 1 - discharging, 0 - charging
    model.mode_3 = pyo.Var(domain=pyo.Binary)
    # Objective
    model.obj = pyo.Var()

    # Objective function: maximise daily arbitrage profit
    def obj_expression(m):
        # Actual export is less than what's being discharged, so being paid less based on the actual electricity delivered after losses
        # Actual import is less but we pay for full charge amount as losses incur after electricity is taken from grid
        return (m.obj)
    model.OBJ = pyo.Objective(rule=obj_expression,sense=pyo.minimize)

    def cons_obj(m):
        return m.obj == -pyo.summation(m.p, m.x_r) + pyo.summation(m.p, m.y)
    model.ObjConstraint = pyo.Constraint(model.I,model.J, rule=cons_obj)

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

    if k == 295: # Need more time to understand why optimisation is stuck on this day: only happens here!
        def cons_volume_change(m,j):
            if j == 1:
                # Storage volume resumes from the same level where it stopped in the previous optimisation
                return (m.v[j] == cap_end)
            # Import into storage incures losses,
            # so actual volume imported during half-hour period is less than the actual charge
            return  (m.v[j] ==  m.v[j-1] - sum(m.x[i,j] - m.y[i,j] for i in m.I))
        model.VolumeChangeConstraint = pyo.Constraint(model.J, rule=cons_volume_change)
    else:
        def cons_volume_change(m,j):
            if j == 1:
                # Storage volume resumes from the same level where it stopped in the previous optimisation
                return (m.v[j] == cap_end)
            # Import into storage incures losses,
            # so actual volume imported during half-hour period is less than the actual charge
            return  (m.v[j] ==  m.v[j-1] - sum(m.x[i,j] - m.y_r[i,j] for i in m.I))
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

    def cons_discharge_remain(m, i, j):
        return m.x_r[i,j] == (1 - m.dch_loss_r) * m.x[i,j]
    model.DischargeRemainConstraint = pyo.Constraint(model.I,model.J, rule=cons_discharge_remain)

    def cons_charge_remain(m, i, j):
        return m.y_r[i,j] == (1 - m.ch_loss_r) * m.y[i,j]
    model.ChargeRemainConstraint = pyo.Constraint(model.I,model.J, rule=cons_charge_remain)

    ### Data read ####
    data = pyo.DataPortal()
    data.load(filename = 'data.csv',
                param = model.p)

    ### Solve the problem ####
    instance = model.create_instance(data)
    results = opt.solve(instance)

    # Find end level of storage volume from previous day which will be the start level on the next day
    cap_end = instance.v[48].value

    ### Output generation part #####
    dt_obj = pd.to_datetime(dtd.values[k-1])
    dt_v = pd.to_datetime(dt.values[idx_start:idx_end])
    dt_xy = dt_v.strftime("%Y-%m-%d %H:%M:%S").tolist()*n_markets # x & y have market index, so dates repeat
    
    df_obj = pd.DataFrame.from_dict(instance.obj.extract_values(),
                                    orient='index',
                                    columns=[str(instance.obj)])
    df_obj['obj'] = df_obj['obj'].apply(lambda x: x*-1) # Reversing sign as we minimise negative profit
    df_obj["dt"] = str(dt_obj.date())

    df_x = pd.DataFrame.from_dict(instance.x.extract_values(),
                                orient='index',
                                columns=[str(instance.x)])
    df_x["dt"] = dt_xy

    df_y = pd.DataFrame.from_dict(instance.y.extract_values(),
                                orient='index',
                                columns=[str(instance.y)])
    df_y["dt"] = dt_xy
    
    df_v = pd.DataFrame.from_dict(instance.v.extract_values(),
                                orient='index',
                                columns=[str(instance.v)])
    df_v["dt"] = dt_v

    df_OBJ = pd.concat([df_OBJ,df_obj])
    df_X = pd.concat([df_X,df_x])
    df_Y = pd.concat([df_Y,df_y])
    df_V = pd.concat([df_V,df_v])

    ### Show progress of optimisation ####
    print("Day ",k,"/",n_days," optimisation finished",sep="")

## Post processing: saving profits & other variables ####
df_OBJ.to_excel(excel_writer = "daily_profits.xlsx",
                  sheet_name = "daily_profits")
df_X.to_excel(excel_writer = "discharging.xlsx",
                  sheet_name = "discharging")
df_Y.to_excel(excel_writer = "charging.xlsx",
                  sheet_name = "charging")
df_V.to_excel(excel_writer = "volume.xlsx",
                  sheet_name = "volume")

tmp1 = pd.to_datetime(dt.values) 
years_unique = tmp1.year.unique().values # Finding unique years in the given period

yearly_profits = [] # This list will collect yearly profits 
for k in years_unique:
    B = df_OBJ[df_OBJ['dt'].str.contains(str(k))]
    C = B["obj"].sum().tolist()
    yearly_profits.append(C)

df['Year'] = years_unique
df['Profit'] = yearly_profits

df.to_excel(excel_writer = "yearly_profits.xlsx",
                  sheet_name = "yearly_profits")
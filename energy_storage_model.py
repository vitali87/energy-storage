import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import csv

# Any pre-processing is done in helper_script.py to improve the overall readability of the code!

# Modelling part
opt = pyo.SolverFactory('glpk')

model = pyo.AbstractModel()

model.m = pyo.Param(within=pyo.NonNegativeIntegers,default = 3)
model.n = pyo.Param(within=pyo.NonNegativeIntegers,default = 48)

model.I = pyo.RangeSet(1, model.m)
model.J = pyo.RangeSet(1, model.n)

model.p = pyo.Param(model.I,model.J) # Prices in Market 1 

model.cap = pyo.Param(default = 4) # Maximum volume of energy that the battery can store (MWh)
model.dch_r = pyo.Param(default = 1) # discharge rate possible for half hour is 1MW
model.ch_r = pyo.Param(default = 1) # charge rate possible for half hour is 1MW

# Discharging variables for Market 1,2,3
model.x = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals)

# Charging variables for Market 1 and 2. Charging variable for Market 3: equal constant charge rate for each half-hour period
model.y = pyo.Var(model.I, model.J, domain=pyo.NonNegativeReals)

# Volume variable
model.v = pyo.Var(model.J, domain=pyo.NonNegativeReals)
# Binary charging/discharging mode: 1 - discharging, 0 - charging
model.mode = pyo.Var(model.J, domain=pyo.Binary)
# Binary status of Market 3: 1 - used, 0 - not used
model.used = pyo.Var(domain=pyo.Binary)
# Binary charging/discharging mode of Market 3: 1 - discharging, 0 - charging
model.mode_3 = pyo.Var(domain=pyo.Binary)

def obj_expression(m):
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
        return (m.v[j] == m.cap/2) # assuming storage volume is half full at the start
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

data = pyo.DataPortal()

data.load(filename = 'boo.csv',  
            param = model.p 
            )

instance = model.create_instance(data)
results = opt.solve(instance)
instance.display()

# Output generation part
with open('result.csv','w') as f1:
    for v in instance.component_objects(pyo.Var, active = True):
        varobject = getattr(instance, str(v))
        writer = csv.writer(f1, delimiter = '\t',lineterminator = '\n',)
        for index in varobject:
            row =  (v,index, varobject[index].value)
            writer.writerow(row)        
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import csv

opt = pyo.SolverFactory('glpk')

model = pyo.AbstractModel()

model.m = pyo.Param(within=pyo.NonNegativeIntegers)
model.n = pyo.Param(within=pyo.NonNegativeIntegers)

model.I = pyo.RangeSet(1, model.m)
model.J = pyo.RangeSet(1, model.n)

model.p = pyo.Param(model.I, model.J)
model.b = pyo.Param(model.J)
model.cap = pyo.Param(default=2)
model.dch_r = pyo.Param(default=1)
model.ch_r = pyo.Param(default=1)

# Discharging variable
model.x = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals)
# Charging variable
model.y = pyo.Var(model.I,model.J, domain=pyo.NonNegativeReals)
# Volume variable
model.v = pyo.Var(model.J, domain=pyo.NonNegativeReals)
# Binary charging or discharging mode
model.mode = pyo.Var(model.J, domain=pyo.Binary)

def obj_expression(m):
    return (-pyo.summation(m.p, m.x) + pyo.summation(m.p, m.y))

model.OBJ = pyo.Objective(rule=obj_expression,sense=pyo.minimize)

def cons_discharge_cap(m, j):
    # return the expression for the constraint for i
    return sum(m.x[i,j] for i in m.I) <= m.v[j]
def cons_charge_cap(m, j):
    return sum(m.y[i,j] for i in m.I) <= m.cap - m.v[j]
def cons_discharge_rate(m,i,j):
    return m.x[i,j] <= m.dch_r * m.mode[j]
def cons_charge_rate(m,i,j):
    return m.y[i,j] <= m.ch_r * (1 - m.mode[j])
def cons_volume_change(m,j):
    if j == 1:
        return (m.v[j] == 0) # assuming storage volume is half full at the start
    return  (m.v[j] ==  m.v[j-1] - sum(m.x[i,j] - m.y[i,j] for i in m.I))

model.DischargeCapConstraint = pyo.Constraint(model.J, rule=cons_discharge_cap)
model.ChargeCapConstraint = pyo.Constraint(model.J, rule=cons_charge_cap)
model.DischargeRateConstraint = pyo.Constraint(model.I,model.J, rule=cons_discharge_rate)
model.ChargeRateConstraint = pyo.Constraint(model.I,model.J, rule=cons_charge_rate)
model.VolumeChangeConstraint = pyo.Constraint(model.J, rule=cons_volume_change)

instance = model.create_instance('data.dat')
results = opt.solve(instance)
instance.display()

with open('result.csv','w') as f1:
    for v in instance.component_objects(pyo.Var, active=True):
        varobject = getattr(instance, str(v))
        writer=csv.writer(f1, delimiter='\t',lineterminator='\n',)
        for index in varobject:
            row =  (v,index, varobject[index].value)
            writer.writerow(row)        
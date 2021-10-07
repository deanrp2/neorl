# -*- coding: utf-8 -*-
"""MC2021_neorl.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1rmOQq-zoAillA2SBE_qohVbgLFDmtcpz
"""

#--------------------------------------------------------------------
# Conference: M&C-2021
# Workshop: Scientific Machine Learning for Nuclear Engineering
# Session: NEORL Workshop
# Contact: Majdi I. Radaideh (radaideh@mit.edu)
# Last update: 9/25/2021
#---------------------------------------------------------------------

#Remove unnecessary packages, install neorl, then test neorl quickly
#!pip uninstall -y xarray arviz pymc3 tensorflow-probability pyerfa pyarrow kapre jax jaxlib datascience coveralls astropy albumentations
#!pip install neorl
#!neorl

#--------------------------------------------------------------------
# Session: NEORL Workshop
# Script: Example 1 (toy example)
#---------------------------------------------------------------------

#1- Import an algorithm from NEORL
from neorl import DE

#2- Define the fitness function
def FIT(individual):
    #sphere function
    y=sum(x**2 for x in individual)
    return y

#3-Setup the parameter space (n=5)
nx=5
BOUNDS={}
for i in range(1,nx+1):
    BOUNDS['x'+str(i)]=['float', -5.12, 5.12]

#4- setup and run the optimizer
de=DE(mode='min', bounds=BOUNDS, fit=FIT, npop=60, F=0.5, CR=0.7, ncores=1, seed=1)
x_best, y_best, de_hist=de.evolute(ngen=100, verbose=1)

print(x_best, y_best)

#--------------------------------------------------------------------
# Session: NEORL Workshop
# Script: Example 2 (Ackley Function)
#---------------------------------------------------------------------

#---------------------------------
# Import packages
#---------------------------------
import numpy as np
import matplotlib.pyplot as plt
from neorl import DE, GWO
from math import exp, sqrt, cos, pi

#---------------------------------
# Fitness function
#---------------------------------
def ACKLEY(individual):
    #Ackley objective function.
    d = len(individual)
    f=20 - 20 * exp(-0.2*sqrt(1.0/d * sum(x**2 for x in individual))) \
            + exp(1) - exp(1.0/d * sum(cos(2*pi*x) for x in individual))
    return f

#---------------------------------
# Parameter Space
#---------------------------------
#Setup the parameter space (d=8)
d=10
lb=-32
ub=32
BOUNDS={}
for i in range(1,d+1):
    BOUNDS['x'+str(i)]=['float', lb, ub]

#---------------------------------
# GWO
#---------------------------------
gwo=GWO(mode='min', bounds=BOUNDS, fit=ACKLEY, nwolves=20, seed=1)
x_gwo, y_gwo, gwo_hist=gwo.evolute(ngen=120, verbose=1)

#---------------------------------
# DE
#---------------------------------
de=DE(mode='min', bounds=BOUNDS, fit=ACKLEY, npop=80, F=0.3, CR=0.7, ncores=1, seed=1)
x_de, y_de, de_hist=de.evolute(ngen=120, verbose=1)

#---------------------------------
# Plot
#---------------------------------
#Plot fitness for both methods
plt.figure()
plt.plot(gwo_hist['fitness'], label='GWO')           
plt.plot(np.array(de_hist), label='DE')            
plt.xlabel('Generation')
plt.ylabel('Fitness')
plt.legend()
plt.savefig('ackley_fitness.png',format='png', dpi=300, bbox_inches="tight")
plt.show()

#--------------------------------------------------------------------
# Session: NEORL Workshop
# Script: Example 3 (Pressure Vessel Design)
#---------------------------------------------------------------------

########################
# Import Packages
########################
from neorl import HHO, BAT

#################################
# Define Vessel Function 
#Mixed discrete/continuous/grid
#################################
def Vessel(individual):
    """
    Pressure vesssel design
    x1: thickness (d1)  --> discrete value multiple of 0.0625 in 
    x2: thickness of the heads (d2) ---> categorical value from a pre-defined grid
    x3: inner radius (r)  ---> cont. value between [10, 200]
    x4: length (L)  ---> cont. value between [10, 200]
    """

    x=individual.copy()
    x[0] *= 0.0625   #convert d1 to "in" 

    y = 0.6224*x[0]*x[2]*x[3]+1.7781*x[1]*x[2]**2+3.1661*x[0]**2*x[3]+19.84*x[0]**2*x[2];

    g1 = -x[0]+0.0193*x[2];
    g2 = -x[1]+0.00954*x[2];
    g3 = -pi*x[2]**2*x[3]-(4/3)*pi*x[2]**3 + 1296000;
    g4 = x[3]-240;
    g=[g1,g2,g3,g4]
    
    phi=sum(max(item,0) for item in g)
    eps=1e-5 #tolerance to escape the constraint region
    penality=1e6 #large penality to add if constraints are violated
    
    if phi > eps:  
        fitness=phi+penality
    else:
        fitness=y
    return fitness
########################
# Setup the Space
########################
bounds = {}
bounds['x1'] = ['int', 1, 99]
bounds['x2'] = ['grid', (0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375, 0.5, 0.5625, 0.625)]
bounds['x3'] = ['float', 10, 200]
bounds['x4'] = ['float', 10, 200]
########################
# Setup and evolute HHO
########################
hho = HHO(mode='min', bounds=bounds, fit=Vessel, nhawks=50, 
                  int_transform='minmax', ncores=1, seed=1)
x_hho, y_hho, hho_hist=hho.evolute(ngen=200, verbose=False)
########################
# Setup and evolute BAT
########################
bat=BAT(mode='min', bounds=bounds, fit=Vessel, nbats=50, levy = True, 
        seed = 1, ncores=1)
x_bat, y_bat, bat_hist=bat.evolute(ngen=200, verbose=1)
########################
# Plotting
########################
plt.figure()
plt.plot(hho_hist['global_fitness'], label='HHO')
plt.plot(bat_hist['global_fitness'], label='BAT')
plt.xlabel('Generation')
plt.ylabel('Fitness')
plt.ylim([0,10000]) #zoom in
plt.legend()
plt.savefig('pv_fitness.png',format='png', dpi=300, bbox_inches="tight")
########################
# Comparison
########################
print('---Best HHO Results---')
print(x_hho)
print(y_hho)
print('---Best BAT Results---')
print(x_bat)
print(y_bat)
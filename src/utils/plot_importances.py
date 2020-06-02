# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 12:12:50 2019

@author: Faith
"""
# Note: filters 3,4,5,6 are g,r,i,z respectively
# Types 0,1,2,3,4 are types Ia, Ibc, II, IIn, and superluminous respectively

import numpy as np
import matplotlib.pyplot as plt
import os
import sys
PROJ_HOME = os.environ['DATA_SRCDIR']
sys.path.append(PROJ_HOME)

last_prop = '-100'
last_color_num = 0
#colors = ['r','b','g','c','m','k']
colors = ['#d73027', '#fc8d59', '#fee090', 
          '#91bfdb', '#4575b4']
def next_color(prop=''):
    global last_prop
    global last_color_num
    if prop[:-2] != last_prop[:-2]:
        last_color_num += 1
        if prop:
            last_prop = prop
    return(colors[last_color_num % len(colors)])

def plot_importances(importances, feature_names, dest_name):
    #feature_names correspond to the first entries of importances, the remaining
    #importances are random numbers
    a = []
    labels = []
    colors = []
    filter_specific = []
    for i in range(len(feature_names)):
        if feature_names[i][-2:] not in {'_3','_4','_5','_6'}: 
            #name is not a per-filter property which would end in _filternumber
            a.append(importances[i])
            labels.append(feature_names[i])
            colors.append(next_color())
        else:
            filter_specific.append((importances[i], feature_names[i]))
    filter_specific.sort(key=lambda x:x[1])
    for feature_importance, feature_name in filter_specific:
        a.append(feature_importance)
        labels.append(feature_name)
        colors.append(next_color(feature_name))
            
    
    plt.bar(range(len(a)), a, color=colors[:len(a)])
    
    #plot line at height of random number input which is importances[40]
    plt.plot(np.arange(-1,len(a),1),[importances[-1]]*(len(a)+1), linestyle = "--", color='k')
    plt.xticks(range(len(a)), labels, rotation='vertical', size=8)
    
    
    plt.tick_params(
        axis='x',          # changes apply to the x-axis
        which='both',      # both major and minor ticks are affected
        bottom=False,      # ticks along the bottom edge are off
        top=False,         # ticks along the top edge are off
        ) 
    
    #plt.set_xticklabels(feature_names)
    
    plt.tick_params(
        axis='y',          # changes apply to the x-axis
        which='both',      # both major and minor ticks are affected
        bottom=False,      # ticks along the bottom edge are off
        top=False,         # ticks along the top edge are off
        labelbottom=False) # labels along the bottom edge are off
    
    plt.locator_params(axis = 'y', nbins = 5)
    plt.gcf().subplots_adjust(left=0.3)
    plt.savefig(dest_name)

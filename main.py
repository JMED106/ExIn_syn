#!/usr/bin/python2.7

import sys
import numpy as np
from sconf import parser_init, parser, log_conf
from simu_lib import Data
import progressbar as pb
from timeit import default_timer as timer

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pylab as plt

import Gnuplot

# Use this option to turn off fifo if you get warnings like:
# line 0: warning: Skipping unreadable file "/tmp/tmpakexra.gnuplot/fifo"
Gnuplot.GnuplotOpts.prefer_fifo_data = 0

__author__ = 'jm'


pi = np.pi
pi2 = np.pi * np.pi

# -- Simulation configuration I: parsing, debugging.
conf_file, debug, args1, hlp = parser_init()
if not hlp:
    logger = log_conf(debug)
else:
    logger = None
# -- Simulation configuration II: data entry (second parser).
description = 'Conductance based QIF spiking neural network. All to all coupled with distributed external currents.'
opts, args = parser(conf_file, args1, description=description)  # opts is a dictionary, args is an object

# Parameters are now those introduced in the configuration file:
# >>> args.parameter1 + args.parameter2
d = Data(opts)
# fr = FiringRate(data=d, swindow=0.1, sampling=0.05)
# Progress-bar configuration
widgets = ['Progress: ', pb.Percentage(), ' ',
           pb.Bar(marker='='), ' ', pb.ETA(), ' ']

# ############################################################
# 0) Prepare simulation environment
if args.loop != 0:  # loop variable will force the time loop to iterate "loop" times more or endlessly if "loop" = 0
    pbar = pb.ProgressBar(widgets=widgets, maxval=args.loop * 10.0 * (d.nsteps + 1)).start()
else:
    args.loop = sys.maxint
    pbar = pb.ProgressBar(redirect_stdout=True, max_value=pb.UnknownLength)
time1 = timer()
tstep = 0
temps = 0.0
kp = k = 0

# Time loop: (if loop was 0 in the config step,
#             we can break the time-loop by changing "loop"
#             or explicitly with a break)
while temps < d.tfinal * args.loop:
    # TIme step variables
    kp = tstep % d.nsteps
    k = (tstep + d.nsteps - 1) % d.nsteps
    k2p = tstep % 2
    k2 = (tstep + 2 - 1) % 2
    if tstep == 0:
        logger.debug("Initial firing rate values: (%f, %f)" % (d.re[k], d.ri[k]))

    if d.sys in ('fr', 'both'):
        d.re[kp] = d.re[k] + d.dt / d.tau_me * (d.delta / pi / d.tau_me + 2.0 * d.re[k] * d.ve[k])
        d.ve[kp] = d.ve[k] + d.dt / d.tau_me * (
            d.ve[k] ** 2 + 1.0 - pi2 * (d.re[k] * d.tau_me) ** 2 - d.tau_me * d.j * d.si[k])
        d.se[kp] = d.se[k] + d.dt / d.tau_de * (-d.se[k] + d.re[kp])

        d.ri[kp] = d.ri[k] + d.dt / d.tau_mi * (d.delta / d.tau_mi / pi + 2.0 * d.ri[k] * d.vi[k])
        d.vi[kp] = d.vi[k] + d.dt / d.tau_mi * (
            d.vi[k] ** 2 + 1.0 - d.tau_mi ** 2 * pi2 * d.ri[k] ** 2 + d.tau_mi * d.j * d.se[k])
        d.si[kp] = d.si[k] + d.dt / d.tau_di * (-d.si[k] + d.ri[kp])

    pbar.update(10 * tstep)
    temps += d.dt
    tstep += 1

# Finish pbar
pbar.finish()
temps -= d.dt
tstep -= 1
print temps, d.re[kp], d.ri[kp]
# Stop the timer
print 'Total time: {}.'.format(timer() - time1)

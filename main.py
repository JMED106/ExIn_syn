#!/usr/bin/python2.7

import sys
import numpy as np
import math
import logging
from sconf import parser_init, parser, log_conf
from simu_lib import Data
from simu_gui import MainGui
from libQifFR import conf_w_to_z
from libQifFR import sigmoid_qif as sig
import progressbar as pb
from timeit import default_timer as timer

import gi

try:
    gi.require_version("GObject", "2.0")
except ValueError:
    logging.exception("Requires GObject development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GObject

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
# try:
#     logger.debug("Parameters are: %s" % opts["parameters"])
# except KeyError:
#     opts["parameters"] = None
# Parameters are now those introduced in the configuration file:
# >>> args.parameter1 + args.parameter2
data = Data(opts)


def simulation(dat, var, q_in=None, q_out=None, updaterate=10000):
    d = dat
    p = dat.prmts
    p.update(dat.controls)
    # QIF-FR variables
    re, ve, se, ri, vi, si = (var['re'], var['ve'], var['se'],
                              var['ri'], var['vi'], var['si'])
    # WC FR variables
    rwe, rwi = (var['rwe'], var['rwi'])
    # Kuramoto order parameter and phase
    Re, Pe, Ri, Pi, PePi = (var['Re'], var['Pe'], var['Ri'], var['Pi'], var['PePi'])

    try:
        p.update(q_in.get_nowait())
    except:
        pass

    # Progress-bar configuration
    widgets = ['Progress: ', pb.Percentage(), ' ',
               pb.Bar(marker='='), ' ', pb.ETA(), ' ']

    # ############################################################
    # 0) Prepare simulation environment
    if args.loop != 0:  # loop variable will force the time loop to iterate "loop" times more or endlessly if "loop" = 0
        barsteps = int((d.tfinal - d.t0) / d.dt)
        print barsteps
        pbar = pb.ProgressBar(widgets=widgets, maxval=args.loop * (barsteps + 1)).start()
    else:
        args.loop = sys.maxint
        # noinspection PyTypeChecker
        pbar = pb.ProgressBar(max_value=pb.UnknownLength)

    time1 = timer()
    tstep = 0
    temps = 0.0
    kp = k = 0

    np.seterr(all='raise')

    # Time loop: (if loop was 0 in the config step,
    #             we can break the time-loop by changing "loop"
    #             or explicitly with a break)
    while temps < d.tfinal * args.loop:
        while p['pause']:
            try:
                p.update(q_in.get_nowait())
            except:
                pass
        # Time delay discretization
        delay = int(p['delay'] / d.dt)
        # Time step variables
        kp = tstep % d.nsteps
        k = (tstep + d.nsteps - 1) % d.nsteps
        kd = (tstep + d.nsteps - 1 - delay) % d.nsteps
        if tstep == 0:
            logger.debug("Initial firing rate values: (%f, %f)" % (ri[k], ri[k]))

        if d.sys in ('fr', 'both'):
            # Wilson Cowan Equations ###########################
            rwe[kp] = rwe[k] + d.dt / p['taume'] * (-rwe[k] + sig(p['etae']
                                                                  + p['taume'] * p['js'] * rwe[kd]
                                                                  - p['taume'] * p['jc'] * rwi[kd],
                                                                  p['taume'], p['delta']))
            rwi[kp] = rwi[k] + d.dt / p['taumi'] * (-rwi[k] + sig(p['etai']
                                                                  - p['taume'] * p['js'] * rwi[kd]
                                                                  + p['taume'] * p['jc'] * rwe[kd],
                                                                  p['taumi'], p['delta']))
            # QIF-FR Equations #################################
            # Excitatory population
            # re[kp] = re[k] + d.dt / p['taume'] * (p['delta'] / pi / p['taume'] + 2.0 * re[k] * ve[k])
            # ve[kp] = ve[k] + d.dt / p['taume'] * (ve[k] ** 2 + p['etae'] - pi2 * (re[k] * p['taume']) ** 2
            #                                       - p['taume'] * p['jc'] * si[k] + p['taume'] * p['js'] * se[k])
            # se[kp] = 1.0 * re[kp]  # se[kp] = se[k] + d.dt / p['taude'] * (-se[k] + re[kp])  # Change this for synapses
            # # Inhibitory population
            # ri[kp] = ri[k] + d.dt / p['taumi'] * (p['delta'] / p['taumi'] / pi + 2.0 * ri[k] * vi[k])
            # vi[kp] = vi[k] + d.dt / p['taumi'] * (vi[k] ** 2 + p['etai'] - p['taumi'] ** 2 * pi2 * ri[k] ** 2
            #                                       + p['taumi'] * p['jc'] * se[k] - p['taumi'] * p['js'] * si[k])
            # si[kp] = 1.0 * ri[kp]  # si[kp] = si[k] + d.dt / p['taudi'] * (-si[k] + ri[kp])  # Change this for synapses

            if math.isnan(re[kp]) or math.isnan(ri[kp]) or math.isnan(rwe[kp]) or math.isnan(rwi[kp]):
                logger.error("Overflow encountered! Change parameters before running a new instance of the simulation.")
                break
        # Transform firing rate and mean membrane potential into Kuramoto order parameter and phase variables
        Re[kp], Pe[kp] = conf_w_to_z(re[kp], ve[kp])
        Pe[kp] = Pe[kp] % np.pi + np.pi * (1 - Pe[kp] / np.abs(Pe[kp])) / 2.0
        Ri[kp], Pi[kp] = conf_w_to_z(ri[kp], vi[kp])
        Pi[kp] = Pi[kp] % np.pi + np.pi * (1 - Pi[kp] / np.abs(Pi[kp])) / 2.0
        PePi[kp] = Pe[kp] - Pi[kp]

        pbar.update(tstep)
        if p['exit'] or p['stop']:
            break

        temps += d.dt
        tstep += 1
        var['tstep'].value = tstep

        # We get the data from the GUI
        if q_in and tstep % updaterate == 0:
            try:
                p.update(q_in.get_nowait())
            except:
                pass
    # Finish pbar
    pbar.finish()
    temps -= d.dt
    tstep -= 1
    print temps, re[kp], ri[kp]
    # Stop the timer
    print 'Total time: {}.'.format(timer() - time1)
    # q_out.put('Q')


# GUI initializing
GObject.threads_init()
# print Gtk.thread_supported()
mg = MainGui(data, simulation=simulation)
mg.window.show_all()

Gtk.main()
# Gdk.threads_leave()

import numpy as np
import logging

logging.getLogger('simu_lib').addHandler(logging.NullHandler())

__author__ = 'Jose M. Esnaola Acebes'

""" This file contains classes and functions to be used in the QIF network simulation.

    Data: (to store parameters, variables, and some functions)
    *****
"""


class Data:
    def __init__(self, parameters):
        self.logger = logging.getLogger('nflib.Data')
        self.logger.debug("Creating data structure.")
        # Zeroth mode, determines firing rate of the homogeneous state

        # 0.3) Give the model parameters
        self.delta = parameters['delta']  # Constant external current distribution width
        self.eta = parameters['eta']

        # 0.2) Define the temporal resolution and other time-related variables
        self.t0 = parameters['t0']  # Initial time
        self.tfinal = parameters['tfinal']  # Final time
        self.total_time = parameters['tfinal'] - parameters['t0']  # Time of simulation
        self.dt = parameters['dt']  # Time step

        self.tpoints = np.arange(self.t0, self.tfinal, self.dt)  # Points for the plots and others
        self.nsteps = len(self.tpoints)  # Total time steps
        self.j = parameters['j']
        self.tau_me = parameters['taume']
        self.tau_mi = parameters['taumi']
        self.tau_de = parameters['taude']
        self.tau_di = parameters['taudi']
        self.taum = self.tau_mi / self.tau_me
        self.taue = self.tau_de * np.sqrt(self.eta) / self.tau_me
        self.taui = self.tau_di * np.sqrt(self.eta) / self.tau_me
        self.faketau = parameters['faketau']  # time scale in ms

        self.sys = parameters['system']
        self.systems = []
        if self.sys in ('qif', 'both'):
            self.systems.append('qif')
        if self.sys in ('fr', 'both'):
            self.systems.append('fr')

        self.logger.debug("Simulating %s system(s)." % self.systems)

        if self.sys != 'qif':
            self.re = np.ones(self.nsteps) * 0.1
            self.ve = np.ones(self.nsteps) * (-0.01)
            self.re[len(self.re) - 1] = 2.0
            self.ve[len(self.ve) - 1] = -1.0
            self.se = np.ones(self.nsteps) * 0.1
            self.se[len(self.se) - 1] = 0.0

            self.ri = np.ones(self.nsteps) * 0.1
            self.vi = np.ones(self.nsteps) * (-0.01)
            self.ri[len(self.ri) - 1] = 1.0
            self.vi[len(self.vi) - 1] = -0.5
            self.si = np.ones(self.nsteps) * 0.1
            self.si[len(self.si) - 1] = 0.0


class PlotCanvas:
    """ A class to create plots in a canvas located at a given GTK window using
         different threads to be able to visualize runtime simulations.
        Ideally it will be a generic class object which will used to create multiple
         canvas, plotting different data. """
    def __init__(self):
        pass
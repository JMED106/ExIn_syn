import numpy as np
import logging

logging.getLogger('simu_lib').addHandler(logging.NullHandler())

__author__ = 'Jose M. Esnaola Acebes'

""" This file contains classes and functions to be used in the QIF network simulation.

    Data: (to store parameters, variables, and some functions)
    *****
"""


class Data:
    """ The data structure will have a general structure but must be shaped to match the simulation
        parameters and variables.
    """
    def __init__(self, parameters):
        self.logger = logging.getLogger('nflib.Data')
        self.logger.debug("Creating data structure.")

        # Mutable parameters will be stored in a dictionary called parameters
        self.prmts = parameters['parameters']
        # Non-mutable parameters will be stored as separated variables
        self.t0 = parameters['t0']  # Initial time
        self.tfinal = parameters['tfinal']  # Final time
        self.total_time = parameters['tfinal'] - parameters['t0']  # Time of simulation
        self.dt = parameters['dt']  # Time step

        # 0.2) Define the temporal resolution and other time-related variables
        self.tpoints = np.arange(self.t0, self.tfinal, self.dt)  # Points for the plots and others
        self.nsteps = len(self.tpoints)  # Total time steps
        # self.taum = self.tau_mi / self.tau_me
        # self.taue = self.tau_de * np.sqrt(self.eta) / self.tau_me
        # self.taui = self.tau_di * np.sqrt(self.eta) / self.tau_me

        self.sys = parameters['system']
        self.systems = []
        if self.sys in ('qif', 'both'):
            self.systems.append('qif')
        if self.sys in ('fr', 'both'):
            self.systems.append('fr')

        # self.logger.debug("Simulating %s system(s)." % self.systems)
        self.controls = {'exit': False, 'pause': True, 'stop': False, 'x': None, 'y': None}

        self.vars = {'t': self.tpoints, 'tstep': 0}
        self.lims = {'t': [0.0, self.tfinal], 're': [0, 1], 'ri': [0, 1],
                     've': [-2, 2], 'vi': [-2, 2], 'se': [0, 2], 'si': [0, 2]}
        # Output variables will be stored in dictionaries to make the Queue handling easy
        if self.sys != 'qif':
            self.exc = self.population(self.nsteps, 2.0, -1.0, 0.0, name="e")
            self.inh = self.population(self.nsteps, 1.0, -0.5, 0.0, name="i")
            self.vars.update(self.exc)
            self.vars.update(self.inh)

    @staticmethod
    def population(nsteps, r0=1.0, v0=-1.0, s0=0.0, name=""):
        r = np.ones(nsteps) * 0.1
        v = np.ones(nsteps) * (-0.01)
        r[len(r) - 1] = r0
        v[len(v) - 1] = -v0
        s = np.ones(nsteps) * 0.1
        s[len(s) - 1] = s0
        return {'r' + name: r, 'v' + name: v, 's' + name: s}


class PlotCanvas:
    """ A class to create plots in a canvas located at a given GTK window using
         different threads to be able to visualize runtime simulations.
        Ideally it will be a generic class object which will used to create multiple
         canvas, plotting different data. """

    def __init__(self):
        pass

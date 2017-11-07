import numpy as np
import logging

logging.getLogger('simu_lib').addHandler(logging.NullHandler())

__author__ = 'Jose M. Esnaola Acebes'

""" This file contains classes and functions to be used in the QIF-FR simulation.

"""


def conf_w_to_z(r, v):
    w = np.pi * r + 1.0j * v
    z = (1.0 - np.conjugate(w)) / (1.0 + np.conjugate(w))
    mod = np.abs(z)
    phase = np.angle(z)

    return mod, phase

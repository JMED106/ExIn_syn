import numpy as np
import logging

logging.getLogger('simu_lib').addHandler(logging.NullHandler())

__author__ = 'Jose M. Esnaola Acebes'

""" This file contains classes and functions to be used in the QIF-FR simulation.

"""

pi = np.pi
pi2 = np.pi * np.pi


def conf_w_to_z(r, v):
    w = np.pi * r + 1.0j * v
    z = (1.0 - np.conjugate(w)) / (1.0 + np.conjugate(w))
    mod = np.abs(z)
    phase = np.angle(z)

    return mod, phase


def sigmoid_exp(x):
    alpha = 1.5
    beta = 3.0
    i0 = -1.0
    return alpha / (1 + np.exp(-beta * (x - i0)))


def sigmoid_brunel_hakim(x):
    return 1 + np.tanh(x)


def sigmoid_qif(x, tau, delta):
    return (1.0 / (tau * pi * np.sqrt(2.0))) * np.sqrt(x + np.sqrt(x * x + delta * delta))

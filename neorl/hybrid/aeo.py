#    This file is part of NEORL.

#    Copyright (c) 2021 Exelon Corporation and MIT Nuclear Science and Engineering
#    NEORL is free software: you can redistribute it and/or modify
#    it under the terms of the MIT LICENSE

#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#    SOFTWARE.

import numpy as np
import itertools
import random

from neorl import WOA
from neorl import GWO
from neorl import PSO
from neorl import MFO
from neorl import HHO
from neorl import DE
from neorl import ES

def detect_algo(obj):
    if isinstance(obj, WOA):
        return 'WOA'
    elif isinstance(obj, GWO):
        return 'GWO'
    elif isinstance(obj, PSO):
        return 'PSO'
    elif isinstance(obj, MFO):
        return 'MFO'
    elif isinstance(obj, HHO):
        return 'HHO'
    elif isinstance(obj, DE):
        return 'DE'
    elif isinstance(obj, ES):
        return 'ES'
    raise Exception('%s algorithm object not recognized or supported'%obj)

max_algos = ['PSO', 'DE', 'ES']#algos that change fitness function to make a maximum problem
min_algos = ['WOA', 'GWO', 'MFO', 'HHO']#algos that change fitness function to make a minimum problem


class Population:
    # Class to store information and functionality related to a single population
    # in the AEO algorithm. Should be characterized by an evolution strategy passed
    # as one of the optimization classes from the other algorithms in NEORL.
    def __init__(self, strategy, init_pop, conv = None):
        # strategy should be one of the optimization objects containing an "evolute" method
        # init_pop needs to match the population given to the strategy object initially
        # conv is a function which takes ngen and returns number of evaluations
        self.conv = conv
        self.strategy = strategy
        self.members = init_pop

        self.fitlog = []

    @property
    def fitness(self):
        return self.fitlog[-1]

    def evolute(self, ngen):
        #perform evolution and store relevant information
        print(self.members)
        out = self.strategy.evolute(ngen, x0 = self.members)
        self.members = out[2]['last_pop'].iloc[:, :-1].values.tolist()
        self.member_fitnesses = out[2]['last_pop'].iloc[:, -1].values.tolist()

        self.fitlog.append(max(self.member_fitnesses))
        print('kkkkf', self.fitlog)

    #TODO: method to export members, return them and remove from list
    #TODO: method to reviece members, update them in members
    #TODO: calc strength method, no need to normalize, may need some scaling parametrs

class AEO(object):
    """
    Animorphoc Ensemble Optimizer

    :param mode: (str) problem type, either "min" for minimization problem or "max" for maximization
    :param bounds: (dict) input parameter type and lower/upper bounds in dictionary form. Example: ``bounds={'x1': ['int', 1, 4], 'x2': ['float', 0.1, 0.8], 'x3': ['float', 2.2, 6.2]}``
    :param fit: (function) the fitness function
    :param optimizers: (list) list of optimizer instances to be included in the ensemble
    :param gen_per_cycle: (int) number of generations performed in evolution phase per cycle
    :param alpha: (float or str) option for exponent on g strength measure, if numeric, alpha is taken to be
        that value. If alpha is 'up' alpha is annealed from -1 to 1. If alpha is 'down' it is annealed from
        1 to -1.
    :param g: (str) either 'fitness' or 'improve' for strength measure for exportation number section of migration
    :param g_burden: (bool) True if strength if divided by number of fitness evaluations in evolution phase
    :param wt: (str) 'log', 'lin', 'exp', 'uni' for different weightings in member selection section of migration
    :param beta: (float or str) option for exponent on b strength measure. See alpha for details.
    :param b: (str) either 'fitness' or 'improve' for strength measure for destination selection section of migration
    :param b_burden: (bool) True if strength if divided by number of fitness evaluations in evolution phase
    :param ret: (bool) True if individual can return to original population in destination selection section
    :param order: (str) 'wb' for worst to best, 'bw' for best to worst, prepend 'a' for annealed starting in the given ordering.
    :param kf: (int) 0 or 1 for variant of weighting functions
    :param ngtonevals: (list of callables) list of functions which take number of generations and number of individuals and returns
        number of fitness evaluations ordered according to the algorithms given in optimizers.
    :param ncores: (int) number of parallel processors
    :param seed: (int) random seed for sampling
    """
    def __init__(self, mode, bounds, fit, 
            optimizers, gen_per_cycle,
            alpha, g, g_burden, wt,
            beta, b, b_burden, ret,
            order = None, kf = None, ngtonevals = None,
            ncores = 1, seed = None):

        if not (seed is None):
            random.seed(seed)
            np.random.seed(seed)

        self.mode=mode
        if mode == 'max':
            self.fit=fit
        elif mode == 'min':
            def fitness_wrapper(*args, **kwargs):
                return -fit(*args, **kwargs) 
            self.fit=fitness_wrapper
        else:
            raise ValueError('--error: The mode entered by user is invalid, use either `min` or `max`')

        self.optimizers = optimizers
        self.algos = [detect_algo(o) for o in self.optimizers]
        self.gpc = gen_per_cycle

        self.bounds = bounds
        self.ncores = ncores

        #infer variable types
        self.var_type = np.array([bounds[item][0] for item in bounds])

        self.dim = len(bounds)
        self.lb=[self.bounds[item][1] for item in self.bounds]
        self.ub=[self.bounds[item][2] for item in self.bounds]

        #check that all optimizers have options that match AEO
        self.ensure_consistency()

        #process variant options for exportation number
        self.alpha = alpha
        if (not isinstance(self.alpha, float) and
            not self.alpha in ['up', 'down']):
            raise Exception('invalid value for alpha, make sure it is a float!')

        self.g = g
        if not self.g in ['fitness', 'improve']:
            raise Exception('invalid option for g')

        self.g_burden = g_burden
        if not isinstance(g_burden, bool):
            raise Exception('g_burden should be boolean type')

        #process variant options for member selection
        self.wt = wt
        if not self.wt in ['log', 'lin', 'exp', 'uni']:
            raise Exception('invalid option for wt')

        self.order = order
        if not self.order in ['wb', 'bw', 'awb', 'abw']:
            raise Exception('invalid option for order')

        self.kf = kf
        if not self.kf in [0, 1]:
            raise Exception('invalid option for kf')

        if self.wt == 'uni' and ((self.kf is not None)
                or (self.order is not None)):
            print('--warning: kf and order options ignored for uniform weighting')

        #process variant options for destination selection
        self.beta = beta
        if (not isinstance(self.beta, float) and
            not self.beta in ['up', 'down']):
            raise Exception('invalid value for beta, make sure it is a float!')

        self.b = b
        if not self.b in ['fitness', 'improve']:
            raise Exception('invalid option for b')

        self.b_burden = b_burden
        if not isinstance(b_burden, bool):
            raise Exception('b_burden should be boolean type')

        self.ret = ret
        if not isinstance(ret, bool):
            raise Exception('ret should be boolean type')

        #process number of generations to number of evaluations functions
        if g_burden or b_burden:
            self.ngtonevals = ngtonevals


    def ensure_consistency(self):
        #loop through all optimizers and make sure all options are set to be the same
        gen_warning = ', check that options of all optimizers are the same as AEO'
        for o, a in zip(self.optimizers, self.algos):
            if a in max_algos:
                assert self.mode == o.mode,'%s has incorrect optimization mode'%o + gen_warning
                assert self.bounds == o.bounds,'%s has incorrect bounds'%o + gen_warning
                try:
                    assert self.fit(self.lb) == o.fit(self.lb)
                    assert self.fit(self.ub) == o.fit(self.ub)
                    inner_test = [np.random.uniform(self.lb[i], self.ub[i]) for i in range(len(self.ub))]
                    assert self.fit(inner_test) == o.fit(inner_test)
                except:
                    raise Exception('i%s has incorrect fitness function'%o + gen_warning)
            else:
                assert self.mode == o.mode,'%s has incorrect optimization mode'%o + gen_warning
                assert self.bounds == o.bounds,'%s has incorrect bounds'%o + gen_warning
                try:
                    assert self.fit(self.lb) == -o.fit(self.lb)
                    assert self.fit(self.ub) == -o.fit(self.ub)
                    inner_test = [np.random.uniform(self.lb[i], self.ub[i]) for i in range(len(self.ub))]
                    assert self.fit(inner_test) == -o.fit(inner_test)
                except:
                    raise Exception('i%s has incorrect fitness function'%o + gen_warning)

    def init_sample(self, bounds):

        indv=[]
        for key in bounds:
            if bounds[key][0] == 'int':
                indv.append(random.randint(bounds[key][1], bounds[key][2]))
            elif bounds[key][0] == 'float':
                indv.append(random.uniform(bounds[key][1], bounds[key][2]))
            #elif bounds[key][0] == 'grid':
            #    indv.append(random.sample(bounds[key][1],1)[0])
            else:
                raise Exception ('unknown data type is given, either int, float, or grid are allowed for parameter bounds')
        return indv

    def evolute(self, ncyc, npop0 = None, x0 = None, pop0 = None, verbose = False):
        """
        This function evolutes the AEO algorithm for a number of cycles. Either
        npop0 or x0 and pop0 are required.

        :param ncyc: (int) number of cycles to evolute
        :param pop0: (list of ints) number of individuals in starting population for each optimizer
        :param x0: (list of lists) initial positions of individuals in problem space
        :param pop0: (list of ints) population assignments for x0, integer corresponding to assigned population ordered
            according to self.optimize
        """
        #intepret npop0 or x0 and pop0 input
        if x0 is not None:
            if npop0 is not None:
                print('--warning: x0 and npop0 is defined, ignoring npop0')
            if pop0 is None:
                raise Exception('need to assign individuals in x0 to populations with different evolution'\
                        + ' strategies by using the pop0 argument where a list of integers is used of equal'\
                        + ' length to x0 telling where each individual belongs.')
            assert len(x0) == len(pop0), 'x0 and pop0 must be ov equal length'
        else:
            x0 = [self.init_sample(self.bounds) for i in range(sum(npop0))]
            dup = [[i]*npop0[i] for i in range(len(npop0))]
            pop0 = list(itertools.chain.from_iterable(dup))

        #separate starting positions according to optimizer/strategy, initialize Population objs
        self.pops = []
        for i in range(len(self.optimizers)):
            xpop = []
            for x, p in zip(x0, pop0):
                if p == i:
                    xpop.append(x)
            if self.g_burden or self.b_burden:
                self.pops.append(Population(self.optimizers[i], xpop, self.ngtonevals[i]))
            else:
                self.pops.append(Population(self.optimizers[i], xpop))

        #perform evolution/migration cycle
        for i in range(ncyc):
            #evolution phase
            [p.evolute(self.gpc) for p in self.pops]
            #migration pase


    #TODO: Set up evolute method
        #TODO: write in verbose reporting
    #TODO: Set up migration method with 3 phases and markov matrix calculation

    #TODO: Autodetect initial populations
    #TODO: Incorporate ngtonevals into method autodetection




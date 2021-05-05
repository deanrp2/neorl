# -*- coding: utf-8 -*-
#"""
#Created on Mon Jun 15 19:37:04 2020
#
#@author: Majdi
#"""

import random
import numpy as np
from collections import defaultdict
import copy
import time

import multiprocessing
import multiprocessing.pool
from neorl.evolu.crossover import cxES2point, cxESBlend

class NoDaemonProcess(multiprocessing.Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class MyPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess

class ES:
    """
    Parallel Evolution Strategies
    
    :param mode: (str) problem type, either "min" for minimization problem or "max" for maximization
    :param bounds: (dict) input parameter type and lower/upper bounds in dictionary form. Example: ``bounds={'x1': ['int', 1, 4], 'x2': ['float', 0.1, 0.8], 'x3': ['float', 2.2, 6.2]}``
    :param lambda\_: (int) total number of individuals in the population
    :param mu: (int): number of individuals to survive to the next generation, mu < lambda\_
    :param cxmode: (str): the crossover mode, either 'cx2point' or 'blend'
    :param alpha: (float) Extent of the blending between [0,1], the blend crossover randomly selects a child in the range [x1-alpha(x2-x1), x2+alpha(x2-x1)] (Only used for cxmode='blend')
    :param cxpb: (float) population crossover probability between [0,1]
    :param mutpb: (float) population mutation probability between [0,1] 
    :param smin: (float): minimum bound for the strategy vector
    :param smax: (float): maximum bound for the strategy vector
    :param ncores: (int) number of parallel processors
    :param seed: (int) random seed for sampling
    """
    def __init__ (self, mode, bounds, fit, lambda_=60, mu=30, cxmode='cx2point', 
                  alpha=0.5, cxpb=0.6, mutpb=0.3, smin=0.01, smax=0.5, ncores=1, seed=None):  
        if seed:
            random.seed(seed)
        self.seed=seed
        self.bounds=bounds
        self.nx=len(bounds.keys())
        #--mir
        self.mode=mode
        if mode == 'max':
            self.fit=fit
        elif mode == 'min':
            def fitness_wrapper(*args, **kwargs):
                return -fit(*args, **kwargs) 
            self.fit=fitness_wrapper
        else:
            raise ValueError('--error: The mode entered by user is invalid, use either `min` or `max`')
            
        self.ncores=ncores
        self.smin=smin
        self.smax=smax
        self.cxpb=cxpb
        self.mutpb=mutpb
        self.alpha=alpha
        self.mu=mu
        self.lambda_=lambda_
        self.cxmode=cxmode
        if not self.cxmode in ['cx2point', 'blend']:
            raise ValueError('--error: the cxmode selected (`{}`) is not available in ES, either choose `cx2point` or `blend`'.format(self.cxmode))

        assert self.mu <= self.lambda_, "mu (selected population) must be less than lambda (full population)"
        assert (self.cxpb + self.mutpb) <= 1.0, "The sum of the cxpb and mutpb must be smaller or equal to 1.0"
        assert self.ncores >=1, "Number of cores must be more than or equal 1"
            
    def GenES(self, bounds):
        #"""
        #Individual generator
        #Inputs:
        #    -bounds (dict): input paramter lower/upper bounds in dictionary form
        #Returns 
        #    -ind (list): an individual vector with values sampled from bounds
        #    -strategy (list): the strategy vector with values between smin and smax
        #"""
        content=[]
        for key in bounds:
            if bounds[key][0] == 'int':
                content.append(random.randint(bounds[key][1], bounds[key][2]))
            elif bounds[key][0] == 'float':
                content.append(random.uniform(bounds[key][1], bounds[key][2]))
            elif bounds[key][0] == 'grid':
                content.append(random.sample(bounds[key][1],1)[0])
            else:
                raise Exception ('unknown data type is given, either int, float, or grid are allowed for parameter bounds')   
        ind=list(content)
        strategy = [random.uniform(self.smin,self.smax) for _ in range(self.nx)]
        return ind, strategy

    def init_pop(self, x0=None):
        #"""
        #Population intializer 
        #Inputs:
        #    -warmup (int): number of individuals to create and evaluate initially
        #Returns 
        #    -pop (dict): initial population in a dictionary form, looks like this
            
        #"""
        #initialize the population and strategy and run them in parallel (these samples will be used to initialize the memory)
        pop=defaultdict(list)
        # dict key runs from 0 to warmup-1
        # index 0: individual, index 1: strategy, index 2: fitness 
        # Example: 
        #"""
        #pop={key: [ind, strategy, fitness]}
        #pop={0: [[1,2,3,4,5], [0.1,0.2,0.3,0.4,0.5], 1.2], 
        #     ... 
        #     99: [[1.1,2.1,3.1,4.1,5.1], [0.1,0.2,0.3,0.4,0.5], 5.2]}
        #"""
        
        if x0:
            print('The first particle provided by the user:', x0[0])
            print('The last particle provided by the user:', x0[-1])
            for i in range(len(x0)):
                pop[i].append(x0[i])
                strategy = [random.uniform(self.smin,self.smax) for _ in range(self.nx)]
                pop[i].append(strategy)
        else:
            for i in range (self.lambda_):
                ind, strategy=self.GenES(self.bounds)
                pop[i].append(ind)
                pop[i].append(strategy)
                
        if self.ncores > 1:  #evaluate warmup in parallel
            core_list=[]
            for key in pop:
                core_list.append(pop[key][0])
           
            p=MyPool(self.ncores)
            fitness = p.map(self.gen_object, core_list)
            p.close(); p.join()
            
            [pop[ind].append(fitness[ind]) for ind in range(len(pop))]
        
        else: #evaluate warmup in series
            for key in pop:
                fitness=self.fit(pop[key][0])
                pop[key].append(fitness)
        
        return pop  #return final pop dictionary with ind, strategy, and fitness

    def gen_object(self, inp):
        #"""
        #This is a worker for multiprocess Pool
        #Inputs:
        #    inp (list of lists): contains data for each core [[ind1, caseid1], ...,  [indN, caseidN]]
        #Returns:
        #    fitness value (float)
        #"""
        return self.fit(inp)

    def select(self, pop, k=1):
        #"""
        #Select function sorts the population from max to min based on fitness and select k best
        #Inputs:
        #    pop (dict): population in dictionary structure
        #    k (int): top k individuals are selected
        #Returns:
        #    best_dict (dict): the new ordered dictionary with top k selected 
        #"""
        
        pop=list(pop.items())
        pop.sort(key=lambda e: e[1][2], reverse=True)
        sorted_dict=dict(pop[:k])
        
        #This block creates a new dict where keys are reset to 0 ... k in order to avoid unordered keys after sort
        best_dict=defaultdict(list)
        index=0
        for key in sorted_dict:
            best_dict[index].append(sorted_dict[key][0])
            best_dict[index].append(sorted_dict[key][1])
            best_dict[index].append(sorted_dict[key][2])
            index+=1
        
        sorted_dict.clear()
        return best_dict

    def mutES(self, ind, strat):
        #"""Mutate an evolution strategy according to mixed Discrete/Continuous mutation rules
        #attribute as described in [Li2013].
        #The function mutates discrete/float variables according to their type as indicated in self.bounds
        #.. Li, Rui, et al. "Mixed integer evolution strategies for parameter optimization." 
        #   Evolutionary computation 21.1 (2013): 29-64.
        #Inputs:
        #    -ind (list): individual to be mutated.
        #    -strat (list): individual strategy to be mutated.
        #Returns: 
        #    -ind (list): new individual after mutatation
        #    -strat (list): individual strategy after mutatation
        
        #"""
        # Infer the datatype, lower/upper bounds from self.bounds for flexible usage 
        lb=[]; ub=[]; datatype=[]
        for key in self.bounds:
            datatype.append(self.bounds[key][0])
            lb.append(self.bounds[key][1])
            ub.append(self.bounds[key][2])
            
        size = len(ind)
        tau=1/np.sqrt(2*size)
        tau_prime=1/np.sqrt(2*np.sqrt(size))
        
        for i in range(size):
            #--------------------------
            # Discrete ES Mutation 
            #--------------------------
            if datatype[i] == 'int':
                norm=random.gauss(0,1)
                # modify the ind strategy
                strat[i] = 1/(1+(1-strat[i])/strat[i]*np.exp(-tau*norm-tau_prime*random.gauss(0,1)))
                #make a transformation of strategy to ensure it is between smin,smax 
                y=(strat[i]-self.smin)/(self.smax-self.smin)
                if np.floor(y) % 2 == 0:
                    y_prime=np.abs(y-np.floor(y))
                else:
                    y_prime=1-np.abs(y-np.floor(y))
                strat[i] = self.smin + (self.smax-self.smin) * y_prime
                
                # check if this attribute is mutated based on the updated strategy
                if random.random() < strat[i]:
                    
                    if int(lb[i]) == int(ub[i]):
                        ind[i] = int(lb[i])
                    else:
                        # make a list of possiblities after excluding the current value to enforce mutation
                        choices=list(range(lb[i],ub[i]+1))
                        choices.remove(ind[i])
                        # randint is NOT used here since it could re-draw the same integer value, choice is used instead
                        ind[i] = random.choice(choices)
            
            #--------------------------
            # Continuous ES Mutation 
            #--------------------------
            elif datatype[i] == 'float':
                norm=random.gauss(0,1)
                strat[i] *= np.exp(tau*norm + tau_prime * random.gauss(0, 1)) #normal mutation of strategy
                ind[i] += strat[i] * random.gauss(0, 1) # update the individual position
                
                #check the new individual falls within lower/upper boundaries
                if ind[i] < lb[i]:
                    ind[i] = lb[i]
                if ind[i] > ub[i]:
                    ind[i] = ub[i]
            
            else:
                raise Exception ('ES mutation strategy works with either int/float datatypes, the type provided cannot be interpreted')
            
            
        return ind, strat

    def GenOffspring(self, pop):
        #"""
        # 
        #This function generates the offspring by applying crossover, mutation **or** reproduction. 
        #The sum of both probabilities self.cxpb and self.mutpb must be in [0,1]
        #The reproduction probability is 1 - cxpb - mutpb
        #The new offspring goes for fitness evaluation
        
        #Inputs:
        #    pop (dict): population in dictionary structure
        #Returns:
        #    offspring (dict): new modified population in dictionary structure    
        #"""
        
        
        pop_indices=list(range(0,len(pop)))
        offspring = defaultdict(list)
        for i in range(self.lambda_):
            rn = random.random()
            #------------------------------
            # Crossover
            #------------------------------
            if rn < self.cxpb:            
                index1, index2 = random.sample(pop_indices,2)
                if self.cxmode.strip() =='cx2point':
                    ind1, ind2, strat1, strat2 = cxES2point(ind1=list(pop[index1][0]),ind2=list(pop[index2][0]), 
                                                            strat1=list(pop[index1][1]),strat2=list(pop[index2][1]))
                elif self.cxmode.strip() == 'blend':
                    ind1, ind2, strat1, strat2=cxESBlend(ind1=list(pop[index1][0]), ind2=list(pop[index2][0]), 
                                                                         strat1=list(pop[index1][1]),strat2=list(pop[index2][1]),
                                                                         alpha=self.alpha)
                else:
                    raise ValueError('--error: the cxmode selected (`{}`) is not available in ES, either choose `cx2point` or `blend`'.format(self.cxmode))
                
                offspring[i].append(ind1)
                offspring[i].append(strat1)
                #print('crossover is done for sample {} between {} and {}'.format(i,index1,index2))
            #------------------------------
            # Mutation
            #------------------------------
            elif rn < self.cxpb + self.mutpb:  # Apply mutation
                index = random.choice(pop_indices)
                ind, strat=self.mutES(ind=list(pop[index][0]), strat=list(pop[index][1]))
                offspring[i].append(ind)
                offspring[i].append(strat)
                #print('mutation is done for sample {} based on {}'.format(i,index))
            #------------------------------
            # Reproduction from population
            #------------------------------
            else:                         
                index=random.choice(pop_indices)
                offspring[i].append(pop[index][0])
                offspring[i].append(pop[index][1])
                #print('reproduction is done for sample {} based on {}'.format(i,index))
    
        return offspring

    def evolute(self, ngen, x0=None, verbose=0):
        """
        This function evolutes the ES algorithm for number of generations.
        
        :param ngen: (int) number of generations to evolute
        :param x0: (list of lists) the initial position of the swarm particles
        :param verbose: (bool) print statistics to screen
        
        :return: (dict) dictionary containing major ES search results
        """
        self.y_opt=-np.inf
        self.best_scores=[]
        
        if x0:    
            assert len(x0) == self.lambda_, '--error: the length of x0 ({}) (initial population) must equal to the size of lambda ({})'.format(len(x0), self.lambda_)
            population=self.init_pop(x0=x0)
        else:
            population=self.init_pop()
            
        # Begin the evolution process
        for gen in range(1, ngen + 1):
            
            # Vary the population and generate new offspring
            offspring = self.GenOffspring(pop=population)
            
            # Evaluate the individuals with an invalid fitness with multiprocessign Pool
            # create and run the Pool
            if self.ncores > 1:
                core_list=[]
                for key in offspring:
                    core_list.append(offspring[key][0])
                #initialize a pool
                p=MyPool(self.ncores)
                fitness = p.map(self.gen_object, core_list)
                p.close(); p.join()
                
                [offspring[ind].append(fitness[ind]) for ind in range(len(offspring))]
                
            else: #serial calcs
                
                for ind in range(len(offspring)):
                    fitness=self.fit(offspring[ind][0])
                    offspring[ind].append(fitness)
        
                
            # Select the next generation population
            population = copy.deepcopy(self.select(pop=offspring, k=self.mu))
            inds, rwd=[population[i][0] for i in population], [population[i][2] for i in population]
            self.best_scores.append(np.max(rwd))
            arg_max=np.argmax(rwd)
            if rwd[arg_max] > self.y_opt:
                self.y_opt=rwd[arg_max]
                self.x_opt=copy.deepcopy(inds[arg_max])
            
            #--mir
            if self.mode=='min':
                self.y_opt_correct=-self.y_opt
            else:
                self.y_opt_correct=self.y_opt
                
            if verbose:
                mean_strategy=[np.mean(population[i][1]) for i in population]
                print('##############################################################################')
                print('ES step {}/{}, CX={}, MUT={}, MU={}, LAMBDA={}, Ncores={}'.format(gen*self.lambda_,ngen*self.lambda_, np.round(self.cxpb,2), np.round(self.mutpb,2), self.mu, self.lambda_, self.ncores))
                print('##############################################################################')
                print('Statistics for generation {}'.format(gen))
                print('Best Fitness:', np.round(np.max(rwd),6) if self.mode is 'max' else -np.round(np.max(rwd),6))
                print('Best Individual:', inds[0])
                print('Max Strategy:', np.round(np.max(mean_strategy),3))
                print('Min Strategy:', np.round(np.min(mean_strategy),3))
                print('Average Strategy:', np.round(np.mean(mean_strategy),3))
                print('##############################################################################')
        
        if verbose:
            print('------------------------ ES Summary --------------------------')
            print('Best fitness (y) found:', self.y_opt_correct)
            print('Best individual (x) found:', self.x_opt)
            print('--------------------------------------------------------------') 

        #--mir
        if self.mode=='min':
            self.best_scores=[-item for item in self.best_scores]
            
        return self.x_opt, self.y_opt_correct, self.best_scores
    
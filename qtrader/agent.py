#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Implement and run an agent to learn in reinforcement learning framework

@author: ucaiado

Created on 08/18/2016
"""
import random
from environment import Agent, Environment
from simulator import Simulator
import translators
import logging
import sys
import time
from bintrees import FastRBTree
from collections import defaultdict
import pandas as pd
import pprint

# Log finle enabled. global variable
DEBUG = True


# setup logging messages
if DEBUG:
    s_format = '%(asctime)s;%(message)s'
    s_now = time.strftime('%c')
    s_now = s_now.replace('/', '').replace(' ', '_').replace(':', '')
    s_file = 'log/sim_{}.log'.format(s_now)
    logging.basicConfig(filename=s_file, format=s_format)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter(s_format)
    ch.setFormatter(formatter)
    root.addHandler(ch)


'''
Begin help functions
'''


def save_q_table(e):
    '''
    Log the final Q-table of the algorithm
    :param e: Environment object. The grid-like world
    '''
    agent = e.primary_agent
    try:
        q_table = agent.q_table
        pd.DataFrame(q_table).T.to_csv('log/qtable.log', sep='\t')
    except:
        print 'No Q-table to be printed'

'''
End help functions
'''


class BasicAgent(Agent):
    '''
    A Basic agent representation that learns to drive in the smartcab world.
    '''
    def __init__(self, env, i_id, f_min_time=3600.):
        '''
        Initiate a BasicAgent object. save all parameters as attributes
        :param env: Environment Object. The Environment where the agent acts
        :param i_id: integer. Agent id
        :param f_min_time: float. Minimum time in seconds to the agent react
        '''
        # sets self.env = env
        super(BasicAgent, self).__init__(env, i_id)
        # Initialize any additional variables here
        self.f_min_time = f_min_time
        self.next_time = 0.
        self.max_pos = 100.

    def reset(self):
        '''
        Reset the state and the agent's memory about its positions
        '''
        self.state = None
        self.position = {'qAsk': 0, 'Ask': 0., 'qBid': 0, 'Bid': 0.}
        self.d_order_tree = {'BID': FastRBTree(), 'ASK': FastRBTree()}
        self.d_order_map = {}
        # Reset any variables here, if required
        self.next_time = 0.

    def should_update(self):
        '''
        Return a boolean informing if it is time to update the agent
        '''
        if self.env.i_nrow < 5:
            return False
        return self.env.order_matching.last_date >= self.next_time
        # return False

    def update(self, msg_env):
        '''
        Update the state of the agent
        :param msg_env: dict. A message generated by the order matching
        '''
        # check if should update, if it is not a trade
        if not msg_env:
            if not self.should_update():
                return None
        # else:
        #     print '============= begin env trade ==========='
        #     print msg_env
        #     print '============= end env trade ===========\n'
        # recover basic infos
        inputs = self.env.sense(self)
        state = self.env.agent_states[self]

        # Update state (position ,volume and if has an order in bid or ask)
        self.state = self._get_intern_state(inputs, state)

        # Select action according to the agent's policy
        l_msg = self._take_action(self.state, msg_env)

        # # Execute action and get reward
        # print '\ncurrent action: {}\n'.format(action)
        reward = 0.
        # pprint.pprint(l_msg)
        self.env.update_order_book(l_msg)
        s_action = None
        s_action2 = s_action
        l_prices_to_print = []
        # if len(l_msg) == 0:
        #     reward += self.env.act(self, msg)
        for msg in l_msg:
            if msg['agent_id'] == self.i_id:
                s_action = msg['action']
                s_action2 = s_action
                s_indic = msg['agressor_indicator']
                l_prices_to_print.append('{:0.2f}'.format(msg['order_price']))
                if s_indic == 'Agressive' and s_action == 'SELL':
                    s_action2 = 'HIT'  # hit the bid
                elif s_indic == 'Agressive' and s_action == 'BUY':
                    s_action2 = 'TAKE'  # take the offer
                reward += self.env.act(self, msg)

        # Learn policy based on state, action, reward
        self._apply_policy(self.state, s_action, reward)
        # calculate the next time that the agent will react
        self.next_time = self.env.order_matching.last_date
        self.next_time += self.f_min_time

        # print agent inputs
        s_date = self.env.order_matching.row['Date']
        s_rtn = 'BasicAgent.update(): position = {}, inputs = {}, action'
        s_rtn += ' = {}, price_action = {}, reward = {}, time = {}'
        inputs['midPrice'] = '{:0.2f}'.format(inputs['midPrice'])
        inputs['deltaMid'] = '{:0.3f}'.format(inputs['deltaMid'])
        if DEBUG:
            root.debug(s_rtn.format(state['Position'],
                                    inputs,
                                    s_action2,
                                    l_prices_to_print,
                                    reward,
                                    s_date))
        else:
            print s_rtn.format(state['Position'],
                               inputs,
                               s_action2,
                               l_prices_to_print,
                               reward,
                               s_date)

    def _get_intern_state(self, inputs, position):
        '''
        Return a tuple representing the intern state of the agent
        :param inputs: dictionary. traffic light and presence of cars
        :param position: dictionary. the current position of the agent
        '''
        pass

    def _take_action(self, t_state, msg_env):
        '''
        Return a list of messages according to the agent policy
        :param t_state: tuple. The inputs to be considered by the agent
        :param msg_env: dict. Order matching message
        '''
        # check if have occured a trade
        if msg_env:
            if msg_env['order_status'] in ['Filled', 'Partialy Filled']:
                return [msg_env]
        # select a randon action, but not trade more than the maximum position
        valid_actions = [None, 'BEST_BID', 'BEST_OFFER', 'BEST_BOTH',
                         'SELL', 'BUY']
        # valid_actions = [None, 'SELL', 'BUY']
        f_pos = self.position['qBid'] - self.position['qAsk']
        if abs(f_pos) >= self.max_pos:
            valid_actions = [None, 'BEST_OFFER', 'SELL']
            # valid_actions = [None, 'SELL']
        elif abs(f_pos) >= self.max_pos:
            valid_actions = [None,
                             'BEST_BID',
                             'BUY']
            # valid_actions = [None, 'BUY']
        # NOTE: I should change just this row when implementing
        # the learning agent
        s_action = self._choose_an_action(t_state, valid_actions)
        # build a list of messages based on the action taken
        l_msg = self._translate_action(t_state, s_action)
        return l_msg

    def _choose_an_action(self, t_state, valid_actions):
        '''
        Return an action from a list of allowed actions according to the
        agent policy
        :param valid_actions: list. List of the allowed actions
        :param t_state: tuple. The inputs to be considered by the agent
        '''
        return random.choice(valid_actions)

    def _translate_action(self, t_state, s_action):
        '''
        Translate the action taken into messaged to environment
        :param t_state: tuple. The inputs to be considered by the agent
        :param s_action: string. The action taken
        '''
        my_ordmatch = self.env.order_matching
        row = my_ordmatch.row.copy()
        idx = self.env.i_nrow
        i_id = self.i_id
        row['Size'] = 100.
        # generate trade
        if s_action == 'BUY':
            row['Type'] = 'TRADE'
            row['Price'] = self.env.best_bid[0]
            return translators.translate_trades(idx,
                                                row,
                                                my_ordmatch,
                                                'BID',
                                                i_id)
        elif s_action == 'SELL':
            row['Type'] = 'TRADE'
            row['Price'] = self.env.best_ask[0]
            return translators.translate_trades(idx,
                                                row,
                                                my_ordmatch,
                                                'ASK',
                                                i_id)
        # generate limit order or cancel everything
        else:
            return translators.translate_to_agent(self,
                                                  s_action,
                                                  my_ordmatch)
        return []

    def _apply_policy(self, state, action, reward):
        '''
        Learn policy based on state, action, reward
        :param state: dictionary. The current state of the agent
        :param action: string. the action selected at this time
        :param reward: integer. the rewards received due to the action
        '''
        pass


class BasicLearningAgent(BasicAgent):
    '''
    A representation of an agent that learns using a basic implementation of
    Q-learning that is suited for deterministic Markov decision processes
    '''
    def __init__(self, env, i_id, f_min_time=3600., f_gamma=0.5):
        '''
        Initialize a BasicLearningAgent. Save all parameters as attributes
        :param env: Environment object. The grid-like world
        :*param f_gamma: float. weight of delayed versus immediate rewards
        '''
        # sets self.env = env, state = None, next_waypoint = None
        super(BasicLearningAgent, self).__init__(env, i_id)
        # Initialize any additional variables here
        self.max_pos = 100.
        self.q_table = defaultdict(lambda: defaultdict(float))
        self.f_gamma = f_gamma
        self.old_state = None
        self.last_action = None
        self.last_reward = None

    def _choose_an_action(self, t_state, valid_actions):
        '''
        Return an action from a list of allowed actions according to the
        agent policy
        :param valid_actions: list. List of the allowed actions
        :param t_state: tuple. The inputs to be considered by the agent
        '''
        # set a random action in case of exploring world
        max_val = 0
        best_Action = random.choice(valid_actions)
        # arg max Q-value choosing a action better than zero
        for action, val in self.q_table[str(t_state)].iteritems():
            if val > max_val:
                max_val = val
                best_Action = action
        return best_Action

    def _apply_policy(self, state, action, reward):
        '''
        Learn policy based on state, action, reward
        :param state: dictionary. The current state of the agent
        :param action: string. the action selected at this time
        :param reward: integer. the rewards received due to the action
        '''
        # check if there is some state in cache
        if self.old_state:
            # apply: Q <- r + y max_a' Q(s', a')
            # note that s' is the result of apply a in s. a' is the action that
            # would maximize the Q-value for the state s'
            s_state = str(state)
            max_Q = 0.
            l_aux = self.q_table[s_state].values()
            if len(l_aux) > 0:
                max_Q = max(l_aux)
            gamma_f_max_Q_a_prime = self.f_gamma * max_Q
            f_new = self.last_reward + gamma_f_max_Q_a_prime
            self.q_table[str(self.old_state)][self.last_action] = f_new
        # save current state, action and reward to use in the next run
        # apply s <- s'
        self.old_state = state
        self.last_action = action
        self.last_reward = reward
        # make sure that the current state has at least the current reward
        # notice that old_state and last_action is related to the current (s,a)
        # at this point, and not to (s', a'), as previously used
        if not self.q_table[str(self.old_state)][self.last_action]:
            s_aux = str(self.old_state)
            self.q_table[s_aux][self.last_action] = self.last_reward


def run():
    """
    Run the agent for a finite number of trials.
    """
    # Set up environment and agent
    e = Environment(i_idx=1)  # create environment
    a = e.create_agent(BasicAgent, f_min_time=1800.)  # create agent
    e.set_primary_agent(a)  # specify agent to track

    # Now simulate it
    sim = Simulator(e, update_delay=1.00, display=False)
    sim.run(n_trials=2)  # run for a specified number of trials

    # save the Q table of the primary agent
    # save_q_table(e)


if __name__ == '__main__':
    # run the code
    run()

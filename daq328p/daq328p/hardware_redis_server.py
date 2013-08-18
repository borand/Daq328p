"""hardware.py - 

Simple module for communicating with Daq328p firmware written for AVR328p.

Usage:
  hardware.py test [--dev=DEV]
  hardware.py [--dev=DEV | --submit_to=SUBMIT_TO | --test | --twitter]
  hardware.py (-h | --help)

Options:
  -h, --help
  --dev=DEV              [default: /dev/ttyS0]
  --twitter=TWITTER      [default: 1]
  --submit_to=SUBMIT_TO  [default: sensoredweb.heroku.com]

"""

import serial
import struct
import time
import re
import simplejson as sjson
import redis
import random

from datetime import datetime
from logbook import Logger
from docopt import docopt
from requests import get
import threading

version = '2013.08.17:2139'

##########################################################################################
class InterfaceTemplate(object):
    last_cmd = ''
    """docstring for InterfaceTemplate"""
    def __init__(self):
        self.Log = Logger('InterfaceTemplate')
        self.idn = 'InterfaceTemplate %d' % id(self)

    def __unicode__(self):
        return str(self)

    def send(self, cmd, **kwargs):
        self.Log.debug('send(cmd=%s, kwargs=%s)' %(cmd, str(kwargs)))
        self.last_cmd = cmd
        return True

    def read(self, **kwargs):
        self.Log.debug('read(kwargs=%s)' %str (kwargs))
        return (0,'InterfaceTemplate resposne to %s' % self.last_cmd)

    def query(self, cmd, **kwargs):
        self.send(cmd, **kwargs)
        return self.read()

##########################################################################################
class HwRedisInterface(threading.Thread):

    def __init__(self, interface=InterfaceTemplate(), channel=''):
        threading.Thread.__init__(self)
        self.timeout   = 1
        self.interface = interface
        self.redis     = redis.Redis()
        self.msg_count = 0
        self.busy = 0;
        if channel=='':
            self.channel   = str(interface)
        else:
            self.channel   = channel

        self.pubsub    = self.redis.pubsub()
        self.Log       = Logger('HwRedisInterface')
        self.Log.debug('__init__(channel=%s)' % self.channel)

        self.pubsub.subscribe(self.channel)
        self.start()
        self.setName('HwRedisInterface-Thread')

    def __del__(self):        
        self.Log.info('__del__()')
        self.stop()

    def stop(self):
        self.Log.info('stop()')
        self.busy = False
        self.redis.publish(self.channel,'KILL')
        time.sleep(1)        
        self.Log.info('  stopped')

    def send(self, cmd, **kwargs):
        self.Log.debug("send(%s,%s)" % (cmd,str(kwargs)))
        to = time.time()
        try:
            self.interface.send(cmd, kwargs)
            self.Log.debug("    send  = %.3f" % (time.time() - to))
            self.redis.set('%s_send_last' % self.channel, cmd)            
            return True
        except Exception as E:            
            self.Log.error(E.message)
            return False

    def read(self, **kwargs):
        self.Log.debug("read(%s)" % str(kwargs))
        to = time.time()
        try:
            out = self.interface.read(**kwargs)            
            self.Log.debug("    interface.read() time = %.3f" % (time.time() - to))
            self.redis.set('%s_read_last' % self.channel, out[1])                
            return out[1]
        except Exception as E:
            self.Log.error(E.message)
            return None

    def query(self, cmd, **kwargs):
        self.Log.debug("query(%s,%s)" % (cmd,str(kwargs)))
        to = time.time()
        self.Log.debug("    query(%s, %s)" % (cmd, str(kwargs)))
        try:
            out = self.interface.query(cmd, **kwargs)
            self.Log.debug("    interface.query() time = %.3f" % (time.time() - to))            
            return out
        except Exception as E:
            self.Log.error(E.message)
            return E

    def run(self):
        self.Log.debug('run()')
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                self.Log.info("unsubscribed and finished")
                break
            else:                
                # self.Log.debug('run() - incoming message')
                if not self.busy:
                    self.process_message(item)
        self.Log.debug('end of run()')

    def process_message(self, item):
        self.Log.debug('process_message(type=%s)' % item['type'])
        to = time.time()
        self.busy = True

        self.msg_count = self.msg_count + 1
        if item['type'] == 'message':
            try:
                msg = sjson.loads(item['data'])
                self.Log.debug('    msg=%s, from=%s' % (msg['cmd'], msg['from']))
                
                if isinstance(msg['cmd'],list):
                    cmd      = msg['cmd'][0]
                    kwargs   = msg['cmd'][1]
                    is_query = msg['cmd'][2]
                else:
                    cmd      = msg['cmd']                    
                    is_query = True
                    
            except Exception as E:
                self.Log.error(E.message)                
            
            self.Log.debug('    is_query=%d' % is_query)
            
            if is_query:
                out = self.query(cmd,**kwargs)
                self.redis.publish('res', out[1])
                timeout = msg['timeout']
                timeout = self.timeout
                self.redis.set(msg['from'],out[1])
                self.redis.expire(msg['from'], timeout)
                self.Log.debug('    query(cmd=%s) = %s' % (cmd, out[1]))
            else:
                self.Log.debug('    send(cmd)')
                out = self.interface.send(cmd)
            self.busy = False
            return out
        else:
            self.busy = False
            return None

##########################################################################################
class Client():

    def __init__(self, channel="test"):
        self.redis = redis.Redis()
        self.channel = channel  
        self.timeout = 1
        self.query_delay = 0.1
        self.idn = 'Client %d' % id(self)
        self.Log = Logger('Client')

    def __del__(self):
        self.Log.debug('__del__()')
        self.redis.delete(self.idn)

    def str(self):
        print self.__unicode__()

    def __unicode__(self):
        msg =  'Client:'
        msg += '\n idn         : %s' % str(self.idn)
        msg += '\n channel     : %s' % str(self.channel)
        msg += '\n imeout      : %s' % str(self.timeout)
        msg += '\n query_delay : %s' % str(self.query_delay)
        return msg

    def read(self):
        self.Log.debug('read()')
        data_read = self.redis.get(self.idn)     
        self.Log.debug('    data_read=%s' % data_read)
        if data_read is not None:
            self.redis.delete(self.idn)
        return data_read

    def send(self, cmd="\n", **kwargs):
        self.Log.debug('send(cmd=%s)' % cmd)
        timeout = kwargs.pop('timeout',0)
        query   = kwargs.pop('query',1)

        try:
            if timeout == 0:
                timeout = self.timeout
            msg = sjson.dumps({'from': self.idn, 'cmd': [cmd, kwargs, query], 'timeout': timeout , 'timestamp': str(datetime.now())})
            self.Log.debug('    full msg=%s)' % msg)
            self.redis.publish(self.channel, msg)
        except Exception as E:
            self.Log.error(E.message)

    def query(self, cmd, **kwargs):
        self.Log.debug('query(cmd=%s, kwargs=%s)' % (cmd, str(kwargs)))
        self.send(cmd, **kwargs)
        
        to = time.clock()        
        while time.clock() - to < self.timeout and (not self.redis.exists(self.idn)):
            time.sleep(0.1)

        return self.read()

if __name__ == "__main__":
    r = redis.Redis()
    Server = SerialRedis()
    Server.start()    
    
    r.publish('serialserver', 'this will reach the listener')
    r.publish('serialserver', 'KILL')
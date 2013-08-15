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

##########################################################################################
class InterfaceTemplate(object):
    last_cmd = ''
    """docstring for InterfaceTemplate"""
    def __init__(self):
        self.idn = str(self)

    def __unicode__(self):
        return str(self)

    def send(self, cmd, *kwargs):
        self.last_cmd = cmd
        return True

    def read(self, *kwargs):
        return 'InterfaceTemplate resposne to %s' % self.last_cmd

    def query(self, cmd, *kwargs):
        self.send(cmd, kwargs)
        return self.read()

##########################################################################################
class HwRedisInterface(threading.Thread):

    def __init__(self, interface=InterfaceTemplate(), channel=''):
        threading.Thread.__init__(self)
        self.timeout   = 1
        self.interface = interface
        self.redis     = redis.Redis()
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
        self.Log.debug('__del__()')
        self.stop()

    def send(self, cmd, *kwargs):
        to = time.time()
        try:
            self.interface.send(cmd, kwargs)
            self.Log.debug("    send  = %.3f" % (time.time() - to))
            self.redis.set('%s_send_last' % self.channel, cmd)
            self.Log.debug("    send-redis  = %.3f" % (time.time() - to))
            return True
        except Exception as E:
            self.Log.error(E.message)
            return False

    def read(self, *kwargs):
        return "def read()"

    def query(self, cmd, *kwargs):
        return cmd

    def run(self):
        self.Log.debug('run()')
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                self.Log.info("unsubscribed and finished")
                break
            else:
                self.process_message(item)
        self.Log.debug('end of run()')

    def process_message(self, item):
        self.Log.debug('process_message(type=%s)' % item['type'])
        if item['type'] == 'message':
            try:
                msg = sjson.loads(item['data'])
                self.Log.debug('    msg=%s, from=%s' % (msg['cmd'], msg['from']))
                cmd = msg['cmd']
                if isinstance(cmd,list):
                    is_query = cmd[1]
                    cmd      = cmd[0]
                else:
                    is_query = True
                    
            except Exception as E:
                self.Log.error(E.message)
                return
            
            if is_query:
                self.Log.debug('    query(cmd)')
                out = self.interface.query(cmd)
                self.redis.set(msg['from'],out)
                self.redis.publish('res', out)
                timeout = msg['timeout']
                timeout = self.timeout
                self.redis.expire(msg['from'], timeout)
            else:
                self.Log.debug('    send(cmd)')
                out = self.interface.send(cmd)

##########################################################################################
class SerialRedis(threading.Thread):

    def __init__(self, port='/dev/ttyUSB0'):
        threading.Thread.__init__(self)
        self.TIMEOUT = 1
        self.redis   = redis.Redis()
        self.channel = str(port)
        self.pubsub  = self.redis.pubsub()
        self.Log     = Logger('SerialRedis')        
        self.Log.info('__init__(channel=%s)' % self.channel)

        self.pubsub.subscribe(self.channel)
        try:
            self.serial = serial.Serial(port,115200)
            out = self.read()
            # out = self.query('I', expected_text='</json>', tag='json',json=1, delay=0)            
        except Exception as E:
            self.Log.error("Exception occured: %s" % E.message)

        self.start()
        self.setName('SerialRedis-Thread')

    def __del__(self):
        self.Log.info('__del__()')
        self.stop()
        if self.serial.isOpen():
            self.Log.info('  closing serial connection')
            self.serial.close()

    def __valid_timeout(self, timeout):
        #self.Log.debug('__valid_timeout(timeout=%s)' % str(timeout))
        if timeout < 0:
            timeout = 1
        return timeout

    def stop(self):
        self.Log.info('stop()')
        self.redis.publish(self.channel,'KILL')
        time.sleep(1)

    def work(self, item):
        self.Log.debug('work(type=%s)' % item['type'])
        if item['type'] == 'message':
            try:
                msg = sjson.loads(item['data'])
                self.Log.debug('    msg=%s, from=%s' % (msg['cmd'], msg['from']))
                cmd = msg['cmd']
            except Exception as E:
                self.Log.error(E.message)
                return          
            
            out = self.query(msg['cmd'])
            
            if out[0] == 0:
                self.redis.set(msg['from'],out[1])
                self.redis.publish('res', out[1])
                timeout = msg['timeout']
                self.redis.expire(msg['from'], self.__valid_timeout(timeout))
            else:
                self.Log.error('    Serial error: %d' % out[0])

    def run(self):
        self.Log.info('run()')
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                self.Log.info("unsubscribed and finished")
                break
            else:
                self.work(item)
        self.Log.info('end of run()')

    def open(self):
        if not self.serial.isOpen():
            self.serial.open()
        return self.serial.isOpen()

    def send(self, data='\n'):
        '''Send command to the serial port
        '''
        to = time.time()
        if len(data) == 0:               
            return
            
        if self.open():
            try:
                self.serial.write(data)
                serial_error = 0
            except:
                serial_error = 1
        else:
            serial_error = 2

        self.Log.debug("    send  = %.3f" % (time.time() - to))
        self.redis.set('%s_send_last' % self.channel, data)
        self.Log.debug("    send-redis  = %.3f" % (time.time() - to))
        return serial_error
    
    def read(self, expected_text=''):
        '''
        read data in the serial port buffer
        - check if the serial port is open 
        - attempt to read all data availiable in the buffer
        - pack the serial data and the serial errors
        '''
        tstart = time.time()
        serial_data = ''
        if self.open():
            try:
                to = time.clock()                
                done = False
                while time.clock() - to < self.TIMEOUT and (not done):
                    n = self.serial.inWaiting()
                    if n > 0:
                        serial_data += self.serial.read(n)
                    if expected_text in serial_data:
                        done = True
                        self.Log.debug("    found expected text")

                serial_error = 0
            except Exception as E:
                self.Log.error("Exception occured: %s" % E.message)
                serial_error = 1
        else:
            serial_error = 2
        self.Log.debug("    read  = %.3f" % (time.time() - tstart))
        self.redis.set('%s_read_last' % self.channel, serial_data)
        self.Log.debug("    read->redis  = %.3f" % (time.time() - tstart))
        return (serial_error, serial_data)
    
    def query(self,cmd, expected_text='</json>', tag='', json=0, delay=0):
        """
        sends cmd to the controller and watis until expected_text is found in the buffer.
        """
        to = time.time()
        query_data = ''
        self.send(cmd)
        
        time.sleep(delay)
        out = self.read(expected_text)      
        query_error = out[0]
        if tag:
            pattern = re.compile(r'(?:<{0}>)(.*)(?:</{0}>)'.format(tag), re.DOTALL)
            temp = pattern.findall(out[1])
            if len(temp)>0:
                query_data = temp[0]
                query_error = 0
            else:
                query_data  = ''
            query_error = 0
        else:
            query_data = out[1]
        if json:
            query_data = sjson.loads(query_data)
        self.Log.debug("    query  = %.3f" % (time.time() - to))
        return (query_error, query_data)

##########################################################################################
class Client():

    def __init__(self, channel="/dev/ttyUSB0"):
        self.redis = redis.Redis()
        self.channel = channel  
        self.timeout = 1
        self.instance_signature = str(self)
        self.Log = Logger('Client')

    def __del__(self):
        self.Log.debug('__del__()')
        self.redis.delete(self.instance_signature)

    def read(self):
        self.Log.debug('read()')
        data_read = self.redis.get(self.instance_signature)     
        self.Log.debug('    data_read=%s' % data_read)
        if data_read is not None:
            self.redis.delete(self.instance_signature)
        return data_read

    def send(self, cmd="\n", timeout=0, query=0):
        try:
            if timeout == 0:
                timeout = self.timeout
            msg = sjson.dumps({'from': self.instance_signature, 'cmd': [cmd, query], 'timeout': timeout , 'timestamp': str(datetime.now())})
            self.Log.debug('send(cmd=%s)' % cmd)
            self.Log.debug('    full msg=%s)' % msg)
            self.redis.publish(self.channel, msg)
        except Exception as E:
            self.Log.error(E.message)

    def query(self, cmd):
        self.Log.debug('query(cmd=%s)' % cmd)       
        self.send(cmd, query=1)
        
        to = time.clock()
        done = 0
        while time.clock() - to < self.timeout and (not done):
            if self.redis.exists(self.instance_signature):
                done = 1

        return self.read()

if __name__ == "__main__":
    r = redis.Redis()
    Server = SerialRedis()
    Server.start()    
    
    r.publish('serialserver', 'this will reach the listener')
    r.publish('serialserver', 'KILL')
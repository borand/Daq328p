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

from datetime import datetime
from logbook import Logger
from docopt import docopt
from requests import get
import threading

class SerialRedis(threading.Thread):

    def __init__(self, channel="serialserver", port='/dev/ttyUSB0'):
        threading.Thread.__init__(self)
        self.TIMEOUT = 3
        self.redis  = redis.Redis()
        self.channel = channel
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channel)
        self.Log = Logger('SerialRedis')
        self.Log.info('__init__(channel=%s)' % self.channel)
        try:
        	self.serial = serial.Serial(port,115200)        	
        	out = self.query('I', expected_text='</json>', tag='json',json=1, delay=0)
        	# print out

        except Exception as E:
        	self.Log.error("Exception occured: %s" % E.message)

    def __del__(self):
    	self.Log.info('__del__()')
    	if self.serial.isOpen():
    		self.Log.info('  closing serial connection')
    		self.serial.close()
    
    def work(self, item):
    	self.Log.info('item=' + str(item))
    	if item['type'] == 'message':
        	self.Log.info('  cmd=' + str(item['data']))
        	self.Log.info('  res=' + str(item['data']))
        	out = self.query(item['data'])        	
        	self.redis.publish('res', out[1])
        	self.redis.set('res',out[1])

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
        if len(data) == 0:               
            return
        
        if (data[-1] == "\n"):
            pass            
        else:
            data += "\n"
            
        if self.open():
            try:
                self.serial.write(data)
                serial_error = 0
            except:
                serial_error = 1
        else:
            serial_error = 2
        self.redis.set('send_last',data)
        return serial_error
    
    def read(self, expected_text=''):
        '''
        read data in the serial port buffer
        - check if the serial port is open 
        - attempt to read all data availiable in the buffer
        - pack the serial data and the serial errors
        '''
       
        serial_data = ''
        if self.open():
            try:
                to = time.clock()                
                done = 0
                while time.clock() - to < self.TIMEOUT and not done:
                    n = self.serial.inWaiting()
                    if n > 0:
                        serial_data += self.serial.read(n)
                    if expected_text in serial_data:
                        done = 1
                serial_error = 0
            except Exception as E:
            	self.Log.error("Exception occured: %s" % E.message)
                serial_error = 1
        else:
            serial_error = 2
        self.redis.set('read_last',serial_data)
        return (serial_error, serial_data)
    
    def query(self,cmd, expected_text='cmd>', tag='', json=0, delay=0):
        """
        sends cmd to the controller and watis until expected_text is found in the buffer.
        """
        
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
        return (query_error, query_data)


if __name__ == "__main__":
    r = redis.Redis()
    Server = SerialRedis()
    Server.start()
    
    
    r.publish('serialserver', 'this will reach the listener')
    r.publish('serialserver', 'KILL')
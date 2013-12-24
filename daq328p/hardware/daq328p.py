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
  --submit_to=SUBMIT_TO  [default: 192.168.1.133]

"""

import serial
import struct
import time
import re
import simplejson as sjson

from threading import Thread,Event
from Queue import Queue, Empty
from warnings import *
from datetime import datetime
from logbook import Logger
from docopt import docopt
from requests import get
from redis import Redis

PARITY_NONE, PARITY_EVEN, PARITY_ODD = 'N', 'E', 'O'
STOPBITS_ONE, STOPBITS_TWO = (1, 2)
FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS = (5,6,7,8)
TIMEOUT = 3

log = Logger('daq328p')
log.info("2013.12.15 20:23")

class Daq328p(Thread):
    read_all_data = False
    submit_to     = 'sensoredweb.heroku.com'
    submit        = True
    redis         = Redis()
    re_data       = re.compile(r'(?:<json>)(.*)(?:</json>)', re.DOTALL)
    json_q        = Queue()
    read_q        = Queue()
    
    def __init__(self,
                 port = 8,
                 packet_timeout=2,
                 baudrate=115200,       
                 bytesize=EIGHTBITS,    
                 parity=PARITY_NONE,    
                 stopbits=STOPBITS_ONE, 
                 xonxoff=0,             
                 rtscts=0,              
                 writeTimeout=None,     
                 dsrdtr=None            
                 ):

        '''
        Initialise the asynchronous serial object
        '''
        
        Thread.__init__(self)
        self.serial = serial.Serial(port, baudrate, bytesize, parity, stopbits, packet_timeout, xonxoff, rtscts, writeTimeout, dsrdtr)
        
        self.running = Event()
        self.buffer  = ''
        self.log = Logger('Daq328p')
        log.info('Daq328p(is_alive=%d, serial_port_open=%d)' % (self.is_alive(), not self.serial.closed))
        out = self.query('I')

        if not out[0]:
            log.info(out[1])

    def __del__(self):
        log.debug("About to delete the object")
        self.close()
        log.debug("Closing serial interface")
        self.serial.close()
        if self.serial.closed:
            log.error("The serial connection still appears to be open")
        else:
            log.debug("The serial connection is closed")
        log.debug("Object deleted")
        
    def start_thread(self):
        '''
        Open the serial serial bus to be read. This starts the listening
        thread.
        '''
        log.debug('start_thread()')
        self.serial.flushInput()
        self.running.set()
        self.start()
        
    def open(self):
        if not self.serial.isOpen():
            self.serial.open()
        return self.serial.isOpen()
    
    def send(self, data, CR=True):
        '''Send command to the serial port
        '''
        if len(data) == 0:               
            return
        
        # Automatically append \n by default, but allow the user to send raw characters as well
        if CR:
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
        self.redis.set('daq328p-send',data)
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
                while time.clock() - to < TIMEOUT and not done:
                    if self.is_alive():
                        if not self.read_q.empty():
                            tmp = self.read_q.get_nowait()
                            serial_data += tmp[1]
                    else:                        
                        n = self.serial.inWaiting()
                        if n > 0:
                            serial_data += self.serial.read(n)
                    if expected_text in serial_data:
                        done = 1
                serial_error = 0
            except:
                serial_error = 1
        else:
            serial_error = 2
        
        self.redis.set('daq328p-read',serial_data)
        return (serial_error, serial_data)
    
    def query(self,cmd, **kwargs):
        """
        sends cmd to the controller and watis until expected_text is found in the buffer.
        """
        
        expected_text = kwargs.get('expected_text','\r\n')
        tag           = kwargs.get('tag','')
        json          = kwargs.get('json',0)
        delay         = kwargs.get('delay',0)

        self.log.debug('query(cmd=%s, expected_text=%s, tag=%s,json=%d, delay=%d):' % \
            (cmd, expected_text, tag, json, delay))

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

    def close(self):
        '''
        Close the listening thread.
        '''
        log.debug('close() - closing the worker thread')
        self.running.clear()

    def run(self):
        '''
        Run is the function that runs in the new thread and is called by
        start(), inherited from the Thread class
        '''
        
        try:
            log.debug('Starting the listner thread')
            while(self.running.isSet()):
                bytes_in_waiting = self.serial.inWaiting()
                if bytes_in_waiting:
                    new_data = self.serial.read(bytes_in_waiting)            
                    self.buffer = self.buffer + new_data
                    
                    crlf_index = self.buffer.find('\r\n')
                    if crlf_index > 0:
                        line = self.buffer[0:crlf_index+2]                        
                        
                        # Put the unpacked data onto the read queue                    
                        timestamp = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')                        
                        
                        if '</json>' in line:
                            log.debug('Found json data in the buffer: %s' % line)
                            temp = self.re_data.findall(line)
                            try:
                                final_data = [timestamp, sjson.loads(temp[0])]
                                #self.json_q.put(final_data)
                                self.redis.publish('irq',sjson.dumps(final_data))
                            except Exception as E:
                                log.error(E.message)
                                log.error("line %s" % line)
                                final_data = [timestamp, "json loads error"] 
                                self.redis.publish('irq',line)
                                #self.read_q.put([timestamp, line])
                        else:
                            final_data = [timestamp, line]
                            self.redis.publish('dac328p',sjson.dumps(final_data))
                            #self.read_q.put([timestamp, line])

                        self.buffer = self.buffer[crlf_index+2:]

        except Exception as E:
            log.error("Exception occured, within the run function: %s" % E.message)
        
        log.debug('Exiting run() function')

############################################################################################
    def process_q(self):
        """
        """
        if not self.json_q.empty():
            q_data = self.json_q.get(1,1)
            log.debug('q_data = %s' % str(q_data[1]))
            if self.submit:
                try:
                    for data in q_data[1]:
                        url = 'http://%s:8000/sensordata/api/submit/datavalue/now/sn/%s/val/%s' % (self.submit_to, data[0], data[-1])
                        log.debug('submitting to: %s' % url)
                        
                        res = get(url)
                        if res.ok:
                            log.info(res.content)
                        else:
                            log.info(res)
                except Exception as E:
                    log.error("Exception occured, within the process_q() function: %s" % E.message)
                    log.error('q_data = %s' % str(q_data[1]))
            else:
                pass
        else    :
            log.debug('json_q is empty')
    
    def process_q_all(self):
        pass

if __name__ == '__main__':
    opt = docopt(__doc__)
    
    D = DaqInterface(opt['--dev']);
    if opt['test']:
        print "Test Mode"        
        resp = D.query('I',expected_text="cmd>")
        if not resp[0]:
            print resp[1]
        else:
            print "query command returned error code: ", resp[0]
            print "Full response: ", resp
    else:        
        D.submit_to = opt['--submit_to']
        D.start_thread()
        log.level = 2
        to = time.time()
        try:
            while True:
                if not D.json_q.empty():
                    log.debug('Found items in Q')
                    D.process_q()
                if time.time() - to > 30:
                    D.send('A', CR=False)
                    to = time.time()
                
        except KeyboardInterrupt:            
            log.debug('Key pressed.')
    D.close()
    del(D)
    log.info('All Done.')
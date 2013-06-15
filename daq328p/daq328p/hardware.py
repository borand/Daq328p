"""hardware.py - 

Simple module for communicating with Daq328p firmware written for AVR328p.

Usage:
  hardware.py test [--dev=DEV]
  hardware.py [--dev=DEV | --submit_to=SUBMIT_TO | --test]
  hardware.py (-h | --help)

Options:
  -h, --help
  --dev=DEV              [default: /dev/ttyS0]
  --submit_to=SUBMIT_TO  [default: 192.168.1.150]

"""

import serial
import struct
from threading import Thread,Event
from Queue import Queue, Empty
from warnings import *
import time
import re
import simplejson as sjson
import requests
from docopt import docopt

PARITY_NONE, PARITY_EVEN, PARITY_ODD = 'N', 'E', 'O'
STOPBITS_ONE, STOPBITS_TWO = (1, 2)
FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS = (5,6,7,8)
TIMEOUT = 3

class DaqInterface(Thread):
    read_all_data = False
    submit_to = '192.168.1.111:8000'
    submit = True
    
    def __init__(self,
                 port = 8,           #Number of device, numbering starts at
                                        # zero.                 
                 read_q = None,         #The queue on which to place the packets
                                        # as they are read in. No argument implies
                                        # that we need to initialise a new queue
                 packet_timeout=1,      #Timeout waiting for packets to arrive.
                                        # This is so we don't block permanently 
                                        # while nothing ever arrives.
                 baudrate=115200,       #baudrate
                 bytesize=EIGHTBITS,    #number of databits
                 parity=PARITY_NONE,    #enable parity checking
                 stopbits=STOPBITS_ONE, #number of stopbits
                 xonxoff=0,             #enable software flow control
                 rtscts=0,              #enable RTS/CTS flow control
                 writeTimeout=None,     #set a timeout for writes
                 dsrdtr=None            #None: use rtscts setting, dsrdtr override if true or false
                 ):

        '''Initialise the asynchronous serial object
        '''
        
        Thread.__init__(self)
        self.serial = serial.Serial( port,
                                baudrate,
                                bytesize,
                                parity,
                                stopbits,
                                packet_timeout,
                                xonxoff,
                                rtscts,
                                writeTimeout,
                                dsrdtr)
        
        self.running = Event()

        self.buffer = ''
        
#        try:
#            self.struct = struct.Struct(data_block_format)
#        except:
#            raise StandardError('Problem encountered loading struct with ' +data_block_format)        
#        self.packet_size = self.struct.size
        
        if read_q == None:
            self.read_q = Queue()
        else:
            self.read_q = read_q
    def __del__(self):
        print "Deleting async_serial, stopping thread and closeing serial port"
        self.running.clear()
        self.serial.close()
        
    def start_thread(self):
        '''Open the serial serial bus to be read. This starts the listening
        thread.
        '''
        self.serial.flushInput()
        self.running.set()
        self.start()
        
    def open(self):
        if not self.serial.isOpen():
            self.serial.open()
        return self.serial.isOpen()
    
    def send(self, data):
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
        return serial_error
    
    def read(self, expected_text=''):
        '''read data in the serial port buffer
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
                            serial_data += self.read_q.get_nowait()                            
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
            
        return (serial_error, serial_data)
    
    def query(self,cmd, expected_text='', tag='',json=0, delay=0):
        
        #if tag:
        #    expected_text = '</' + tag + '>'
        
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
        '''Close the listening thread.
        '''
        self.running.clear()
    
    def process_q(self):
        final_data = ''
        if self.read_q.qsize() > 0:            
            q_data = self.read_q.get(1,1)
            if 'json>' in q_data:
                re_data = re.compile(r'(?:<json>)(.*)(?:</json>)', re.DOTALL)
                temp = re_data.findall(q_data)
                try:
                    final_data = sjson.loads(temp[0])
                except:
                    final_data = "json loads error"
            else:
                if self.read_all_data:
                    final_data = q_data
        return final_data

    def run(self):
        '''Run is the function that runs in the new thread and is called by
        start(), inherited from the Thread class
        '''
        print "Executing run() function"
        try:
            print "\tEntering while loop"
            while 1:
                while(self.running.isSet()):
                    if self.serial.inWaiting():
                        new_data = self.serial.read(1)                
                        self.buffer = self.buffer + new_data                
                        if self.buffer[-2:] == '\r\n':
                            # Put the unpacked data onto the read queue                    
                            self.read_q.put(self.buffer)
                            print self.buffer
                            if self.submit:
                                if 'json>' in self.buffer:
                                     re_data = re.compile(r'(?:<json>)(.*)(?:</json>)', re.DOTALL)
                                     temp = re_data.findall(self.buffer)
                                     try:
                                         final_data = sjson.loads(temp[0])
                                         res = requests.get('http://%s/sensordata/api/submit/datavalue/now/sn/%s/val/%s' % (self.submit_to, final_data[0], final_data[1]))
                                         if res.ok:
                                             print res.content
                                         else:
                                             print res
                                                  
                                     except:
                                         final_data = "json loads error"
                            
                            # Clear the buffer
                            self.buffer = ''
                            #self.process_q()

        except KeyboardInterrupt:
            print "\tException occured"
            self.interrupt_main()
            self.close()
            return None
        print "Endof run() function"

if __name__ == '__main__':
    opt = docopt(__doc__)
    
    if opt['test']:
        print "Test Mode"
        D = DaqInterface(opt['--dev']);
        resp = D.query('I',expected_text="cmd>")
        if not resp[0]:
            print resp[1]
        else:
            print "query command returned error code: ", resp[0]
            print "Full response: ", resp
    else:
        D.submit_to = opt['--submit_to']

    # from PyDaq.Sandbox.aserial import *    
#    A = async_serial(13)    
#    print A.query("adc", "</a>", "a", json=0)
    

    
'''
'''

import time
import re
import socket
import binascii
import os

from logbook import Logger

CMDS = {0x50: ['Standard Message Received', 0, 11,],
        96  : ['GetImInfo',                 2, 9, ],
        98  : ['SendMessage',               8, 9, ],
        103 : ['Factory reset',             2, 3, ],
        109 : ['LedOn',                     2, 3, ],
        110 : ['LedOff',                    2, 3, ],        
        107 : ['SetIMConfiguration',        3, 4, ],
        115 : ['GetIMConfiguration',        2, 6, ],
        }
                #cmd1,  meaning          cmd2, meaning,  response 
STANDARD_CMDS = {
                 0x17: [ 'ON',           0,    'Level',                                 0x50],
                 0x0f: [ 'PING',         0,    'Level',                                 0x50],
                 0x19: [ 'GetStatus',    0,    'Request on-level status from a unit.',  0x50],
                 }

dining_room = [0x18, 0x1d, 0x04]
living_room = [0x09, 0x8E, 0x94]
ikea_lamp1  = [0x18, 0x98, 0xAA]
ikea_lamp2  = [0x16, 0x83, 0x87]
outdoor     = [0x14, 0xa1, 0x28]
light       = [0x20, 0x1f, 0x11]

all_devices = [dining_room, living_room, ikea_lamp1, ikea_lamp2, outdoor, light]


def GetDecAddress(address):
    '''
    Convert hex address to decimal vector.  If address is in decimal format the command has no effect
    '''
    return [int(h) for h in address] 

def SplitStr(s, size=2):
    return [s[i:i+size] for i in xrange(0, len(s), size)]

def str2hex(address):
    return [int(i,16) for i in address.split('.')]

def hex2str(address):
    return '%02x.%02x.%02x' % (address[0],address[1],address[2])

def hex2dec(address):
    return [int(h) for h in address] 

def str2dec(s):
    return [int(i,16) for i in SplitStr(s)]

class InsteonPLM(object):
    '''
    Class used to connect to Insteon serial power line modem (PLM) 
    '''

    def __init__(self, port=('192.168.1.200', 9761)):
        '''
        Constructor
        '''
        self.log = Logger('InsteonPLM')
        try:
            self.log.info('InsteonPLM(%s)' % str(port))
            self.interface = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.interface.settimeout(2)
            self.interface.connect(port)
        
        except Exception as EX:
            self.interface = None
            self.log.error('    ERROR: %s' % EX.message)
    
    def __del__(self):
        pass
    
    def __unicode__(self):
        if self.interface is not None:
            name = "PLM(%s)" %  str(self.interface)
        else:
            name = "PLM(None)"            
        return name

    def stop(self):
        self.log.debug("def stop()")
        self.interface.shutdown(socket.SHUT_RDWR)
        self.interface.close()

    ############################################################################################
    #
    #
    def send(self, cmd, get_confirmation=True):
        self.log.debug("def send(self, cmd=%s):" % str(cmd))
        
        if not CMDS.has_key(cmd[0]):
            dbg_msg =  "Command %d does not exist in the dictionary" % cmd[0]
            self.log.debug(dbg_msg)
            return False
        else:
            cmd_details = CMDS.get(cmd[0])
            dbg_msg = "Sending: " + cmd_details[0] + " : " + str(cmd)
            self.log.debug(dbg_msg)
        
        cmd.insert(0,0x2)
        hex_cmd = ''.join(chr(x) for x in cmd)        
        dbg_msg = "Full command: " + str(cmd)
        self.log.debug(dbg_msg)        
        self.interface.send(hex_cmd)

        if get_confirmation:            
            return_data = self.read_response([cmd[1]])
        else:
            return_data = cmd
            
        return return_data
        
    def read(self):
        self.log.debug("def read(self):")
        data = ''
        try:
            data = self.interface.recv(128)            
        except socket.error, ex:                
            pass
        except Exception, ex:
            print "Exception:", type(ex) 
            pass

        return binascii.hexlify(data)
    
    def query(self, hex_address, cmd1, cmd2):
        self.log.debug("query(self, hex_address, cmd1, cmd2):")
        cmd      = [98, 0, 0, 0, 15, 17, 255]
        cmd[1:4] = GetDecAddress(hex_address)
        cmd[5]   = cmd1
        cmd[6]   = cmd2
        sent_cmd = self.send(cmd)
        cmd.append(6)
        expected_response_str = ''.join('%02x' % byte for byte in cmd)
        read_res = self.read_response([0x50])
        if expected_response_str == sent_cmd and read_res:
            success = 1
        else:
            success = 0
            self.log.debug('    empty response:')

        return (success, read_res, sent_cmd)

    def send_standard_cmd(self, hex_address, cmd1, cmd2):
        self.log.debug("send_standard_cmd(self, hex_address, cmd1, cmd2):")
        cmd      = [98, 0, 0, 0, 15, 17, 255]
        cmd[1:4] = GetDecAddress(hex_address)
        cmd[5]   = cmd1
        cmd[6]   = cmd2
        sent_cmd = self.send(cmd)
        read_res = self.read_response([0x50])                
        return [sent_cmd, read_res]
    
    def read_response(self, cmd):
        self.log.debug("def read_response(self, cmd%s):" % str(cmd))
        if not CMDS.has_key(cmd[0]):
            dbg_msg =  "Command %d does not exist in the dictionary" % cmd[0]
            self.log.debug(dbg_msg)
            return []
        else:
            cmd_details = CMDS.get(cmd[0])
            dbg_msg = "Waiting for response to: " + cmd_details[0] + " : " + str(cmd)
            self.log.debug(dbg_msg)
        
        cmd_details = CMDS.get(cmd[0])
        to = time.time()
        tn = time.time()
        return_data = ''
        try:
            return_data = self.interface.recv(128)
        except socket.error, ex:                
            pass
        except Exception, ex:
            print "Exception:", type(ex) 
            pass        
        return binascii.hexlify(return_data)
    # Methods for specific modules
    
    def SetSwitchON(self, hex_address):
        self.log.debug("def SetSwitchON(self, hex_address=%s):" % str(hex_address))
        cmd         = [98, 0, 0, 0, 15, 17, 255]
        dec_address = [int(h) for h in hex_address]
        cmd[1:4]    = dec_address
        self.send(cmd)        
        return self.read_response([80])
    
    def SetSwitchOFF(self, hex_address):
        self.log.debug("def SetSwitchOFF(self, hex_address=%s):" % str(hex_address))
        cmd         = [98, 0, 0, 0, 15, 19, 255]
        dec_address = [int(h) for h in hex_address]
        cmd[1:4]    = dec_address        
        sent_status = self.send(cmd)
        read_status = self.read_response([80])
        return 
    
    # def GetSwitchStatus(self, hex_address):
    #     cmd         = [98, 0, 0, 0, 15, 25, 255]
    #     dec_address = [int(h) for h in hex_address]
    #     cmd[1:4]    = dec_address        
    #     self.send(cmd)
        
    #     time.sleep(0.5)
    #     res = self.read()
    #     if res[-1] == 255:
    #         print "Switch is ON"
    #     elif res[-1] == 0:
    #         print "Switch is OFF"
    #     else:
    #         print "Switch status value: ", res[-1]
    #     return res
    
    def SetLevel(self, hex_address, level):
        return self.query(hex_address,17,level)

    def GetIdn(self):
        self.log.debug("def GetIdn():")
        data = self.send([96])
        return data

    def GetPlmAddress(self):
        self.log.debug("def GetPlmAddress():")
        data = self.send([96])
        return data

    def GetSwitchStatus(self, hex_address):
        self.log.debug("def GetSwitchStatus():")
        out = self.query(hex_address,25,0)
        if out[0]:
            val = int(out[1][-2:],16)
            self.log.debug("    val = %d" % val)
        else:
            val = None
            self.log.debug("    val = unknown")
        return val

def parse_flag(flag):
    bit_765 = flag >> 5
    bit_765_dict = {
     0 : 'Direct Message',
     1 : 'ACK of Direct Message',
     2 : 'Group Cleanup Direct Message',
     3 : 'ACK of Group Cleanup Direct Message',
     4 : 'Broadcast Message',
     5 : 'NAK of Direct Message',    
     6 : 'Group Broadcast Message',     
     7 : 'NAK of Group Cleanup Direct Message'
    }
    extended_message = flag & 8 == 8
    hops_left = (flag >> 2) & 3
    max_hops = flag & 3
    return [bit_765_dict.get(bit_765), extended_message,hops_left,max_hops] 

def parse_configuration_flags(flag):
    return [['automatic linking disabled', flag & 128 == 128],
            ['Monitor Mode enabled', flag & 64 == 64],
            ['Disables automatic LED', flag & 32 == 32],
            ]
    
def parse_buffer(buff):
    cmd = []
    unparsed = []
    for byte in buff:
        if byte == 2:
            cmd.append(byte)
        
if __name__ == '__main__':
    print "================================"
    print "PLM module test function"
    plm = InsteonPLM()
    plm.log.level = 50

    for device in all_devices:
        val  = plm.GetSwitchStatus(device)
            # submit([[hex2str(device), val]])
    plm.stop()
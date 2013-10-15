import simplejson
import datetime

from django.http import HttpResponse
from django.core import serializers
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.log import getLogger

import daq328p.hardware.redisbridge as RB

logger = getLogger("app")

def home(request):
    time_stamp = (datetime.datetime.now())    
    Daq = RB.Client(channel='test',host='192.168.1.127')
    #res = Daq.query('I')
    msg = str(time_stamp) + '\n' + res[1]
    logger.info(msg)
#    return HttpResponse(msg)
    page_context = {'page_title': 'Daq328p', 'datetime':msg}
    return render_to_response('daq328p.html',page_context, context_instance=RequestContext(request))    

def query(request, **kwargs):  
    cmd = kwargs['cmd']
    logger.info('cmd = ' + cmd)
    time_stamp = (datetime.datetime.now())
    #res = Daq.read()
    #res = Daq.query(cmd,expected_text='cmd>')
    Daq = Client()
    res = Daq.query(cmd)
    
    # if errors:
    #     msg = "Loaded at: %s errors in reading H" % time_stamp
    # else:
    msg = str('query : ') + res
#    logger.info(res[1])    
#    print simplejson.dumps(str(res[1]))
    return HttpResponse(simplejson.dumps(str(res)),mimetype='text/json')

def cmd(request):    
    logger.debug("cmd()")
    cmd = request.GET.get('cmd')
    val = request.GET.get('val')
        
    logger.debug("api_control(cmd = %s, val = %s)" % (cmd, str(val)))
    if "ping" in cmd:
        logger.debug("\trespondng to ping")
        response = '"pong"' 
    elif "options_threading" in cmd:        
        response = '"thread started"'
    else:
        response = '"none"'
        
    #response = '"main_io cmd=%s, val=%s time=%s"' %  (cmd,val,datetime.datetime.now())    
    logger.debug('response = %s' % response)    
    return HttpResponse(response, content_type="text/json")

from django.core import serializers
from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response

from django.utils.log import getLogger
from . settings import Daq
import datetime
logger = getLogger("app")

def home(request):
    time_stamp = (datetime.datetime.now())
    Daq.send('I')
    res = Daq.read()
    errors = res[0]
    if errors:
        msg = "Loaded at: %s errors in reading H" % time_stamp
    else:
        msg = str(time_stamp) + '\n' + res[1]
        
    logger.info(msg)
    return HttpResponse(msg)
#    return render_to_response('index.html',{'datetime':msg}, context_instance=RequestContext(request))    
    
def query(request, cmd):
    time_stamp = (datetime.datetime.now())
    res = Daq.query(cmd,expected_text='cmd>')
    errors = res[0]
    if errors:
        msg = "Loaded at: %s errors in reading H" % time_stamp
    else:
        msg = str('query : ') + res[1]
    logger.info(msg)
    return HttpResponse(msg)
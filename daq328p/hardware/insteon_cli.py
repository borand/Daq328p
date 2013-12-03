import insteon
from logbook import Logger

##########################################################################################
class InsteonCli(object):
    last_cmd = ''
    """docstring for InsteonCli"""
    def __init__(self):
        self.Log = Logger('InsteonCli')
        self.idn = 'InsteonCli %d' % id(self)
        self.plm = insteon.InsteonPLM()

    def __unicode__(self):
        return str(self)

    def query(self, cmd, *args, **kwargs):
    	try:
        	insteon_method = getattr(self.plm, cmd)
        	result = [0, insteon_method(**kwargs)]
        except Exception as e:
        	result = [1, e.message]
        return result
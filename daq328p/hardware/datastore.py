from logbook import Logger
from requests import get

log = Logger('datastore')

def submit(data_set, submit_to='sensoredweb.heroku.com'):    
    try:
        for data in data_set:
            url = 'http://%s/sensordata/api/submit/datavalue/now/sn/%s/val/%s' % (submit_to, data[0], data[-1])
            log.debug('submitting to: %s' % url)                      
            res = get(url)
            if res.ok:
                log.info(res.content)
            else:
                log.info(res)
    except Exception as E:
        log.error("Exception occured, within the submit function: %s" % E.message)
        log.error('q_data = %s' % str(data_set[1]))


if __name__ == "__main__":
	submit([['0', '0']])

#!/usr/bin/python

import getopt
import sys
import httplib
from pprint import pprint
from pprint import pformat
import json
import re
import time
import datetime

from cloudservers import CloudServers
from cloudservers import exceptions

DEBUG = 0
PROGRAM_NAME="performance-single-cs.py"

def log(message):
    print message 

def debug(message):
    if DEBUG>0:
        log("debug[%2d]: " % DEBUG + message)


class TestRackspaceCloudServerPerformance:
    (user, key) = (None, None)
    cs=None
    
    def __init__ (self, user, key):
        (self.user, self.key) = (user, key)


    # timeout in minutes

    def check_cs_status2(self, cs_record, sample, cs_count):
        sm=self.cs.servers
               
        _server=cs_record['cs']
        _status=cs_record['status']
        _date_start=_status['date_start']
        
        if True == _status['is_build'] :
            return 
        
        is_build=False
 
        try:
            checking_now= datetime.datetime.now()
            server=sm.find( name=_server.name )
            debug( "checking status " + _server.name + " " +  str(checking_now) + "\n" + pformat(vars(_server)))

        except exceptions.NotFound:
                debug("can't find server id " + _server.name + " / " + str(_server.id) + " continue checking" )
                return is_build

        if server.status== 'ACTIVE' :
            is_build=True
            _status['is_build']=is_build
            _status['date_end']=checking_now
            self.log_status(_status, server, sample, cs_count)

        return is_build
        
        
    def check_all_cs_status(self, cs_records, max_time, sample):
        debug('func check_all_cs_status start')
        
        is_build=False
        is_timeout=False
        
        while not is_build and not is_timeout :
            build_finished=0
            for cs_nr in range(0, len(cs_records)):
                if self.check_cs_status2(cs_records[cs_nr], sample, cs_nr):
                    build_finished+=1
            
            if build_finished == len(cs_records):
                is_build=True
                break
                
            now=datetime.datetime.now()
            if now > max_time:
                is_timeout=True
                
                for cs_nr in range(0, len(cs_records)):
                    _status=cs_records[cs_nr]['status']
                    _status['date_end']=now
                    if not _status['is_build']: 
                        self.log_status(_status, server, sample, cs_nr)
                
                break
            
            time.sleep(60)
        
        return is_build
    
    def log_status(self, status, server, sample, cs_count):
        s="[%2d][%2d] cloud server build [" % (sample+1, cs_count+1 )+ server.name + '] '
        
        status['delta'] = status['date_end'] - status['date_start']
        status['timeout'] = status['delta'].total_seconds()
        
        if status['is_build']:
            s=s+"created in " + str(status['delta'].total_seconds()) + ' seconds / ' + \
              str(status['timeout']/60.0) + ' minutes'
        
        else:
            s=s+"ERROR, can't find server or timeout after " + \
              str(status['timeout']) + ' seconds / ' + \
              str(status['timeout']/60.0) + ' minutes'
            
        log(s)

    def cs_delete(self, server):
        sm=self.cs.servers
        server=sm.delete(server)

    def cs_delete_all(self, cs_records):
        debug("func cs_delete_all start")
        
        for rec in cs_records:
            #cs=cs_records[cs_nr]['cs']
            self.cs_delete( rec['cs'] )         
        
    def cs_create(self, count, sample_nr):
        name='csperform' + str(int(time.time()))
        image=112
        flavor=1
        
        sm=self.cs.servers
        server=sm.create(name, image, flavor)
        
        log("[%2d][%2d] created image: " % (sample_nr, count) + pformat( {'name': name, 'image' : image, 'flavor' : flavor } ) )
        debug(pformat(vars(server)))
        
        return server

    """
        status = { 
                         'date_start': date_start,
                         'date_end' : date_end,
                         'is_build' : is_build,
        }
        cs_record={ 
                'cs' : server,
                'status' : status, ,
        }
        
        cs_records = [ cs_record ]
    """    
    def cs_create_all(self, cs_count, sample_nr):
        log("[%2d][  ] starting test nr %d, creating %d cloud server, please wait ..." % (sample_nr, sample_nr, cs_count) )
        
        api_time_limit=60
        hard_limit=10
        
        
        cs_records = []

        build_nr=1
        delayed_10s=False
        
        while build_nr <= cs_count :
            if 0==build_nr % 11 and not delayed_10s:
                debug("created %d servers, introducing delay" % build_nr)
                time.sleep(60+10)
                
            try:
                date_start = datetime.datetime.now() 
                server = self.cs_create(build_nr, sample_nr)
                delayed_10s=False
                
            except exceptions.OverLimit:
                hit_time= datetime.datetime.now()
                debug("warning, hit the API limit at " + str(hit_time) + ", imposing delay")
                time.sleep(10)
                delayed_10s=True
                
                continue 
    
            status     = {
                'date_start': date_start,
                'date_end' : None,
                'is_build' : False,
            }
            
            cs_record  = {
                'cs' : server,
                'status' : status,
            }
        
            cs_records.append(cs_record)
            
            build_nr+=1
        
        return cs_records
                    
    def test_multi_cs_perf(self, sample=1, cs_count=1, timeout=10):
        debug('func test_multi_cs_perf start')
        
        if not self.cs : 
            self.cs=CloudServers(self.user, self.key)
            self.cs.authenticate()

        for i in range(0, sample): 
            cs_records=self.cs_create_all(cs_count, i+1)
            
            debug("servers created " +  str(type(cs_records)) + " : \n" + pformat(cs_records))
            
            last_data_start=cs_records[cs_count-1]['status']['date_start']
            now=datetime.datetime.now()
            
            delta=datetime.timedelta(minutes=timeout)
            max_time=now + delta
            
            time.sleep(30)
            self.check_all_cs_status(cs_records, max_time, i)
            debug("servers checked; " +  str(type(cs_records)) + " : \n" + pformat(cs_records))
            
            self.cs_delete_all(cs_records)
            debug("servers deleted; " +  str(type(cs_records)) + " : \n" + pformat(cs_records))

class Main:
    
    def usage(self, message=None):
        if message is not None: 
            print message
        
        print """
    usage: %s [-v] [-h] [ -t # ] [ -s # ] [ -i # ] -u user -k key run | help
      -h - usage help 
      -v - verbose/debug output
      -u 
      -k
      -i - ignore timeout (wait forever otherwise wait only 10 min and abandon the function ) 
      -t - how many repetitive tests to execute   
      -s - a test sample size; how many cloud servers to create in a single test run
      
      args:
        help - displays info about this program
        run - run this program
        
      example:
        1. Run a 2 test sessions and create and measure the API performance of creating one cloud sever     
          $ %s -u user -k key -t 2 -s 1
        
""" % (PROGRAM_NAME, PROGRAM_NAME)
    
    def test_performance(self, user,key, sample, cs_count, timeout):
        debug('func test_performance start')
        
        t=TestRackspaceCloudServerPerformance(user,key)
        #t.test_perf_single_cs(sample)
        t.test_multi_cs_perf(sample, cs_count, timeout)
    
    def run(self): 
        debug("main start")
        debug(sys.argv[0])
        
        optlist, args = getopt.getopt(sys.argv[1:], 'vu:k:t:s:i:')
    
        user, key = None, None
        sample=1
        timeout=10
        cs_count=1
        
        for o, val in optlist:
            if o == "-v":
                global DEBUG 
                DEBUG = 1
            elif o == "-h":
                self.usage()
                sys.exit()
            elif o =="-u":
                user=val
            elif o =="-k":
                key=val
            elif o =="-t":
                sample=int(val)
            elif o =="-s":
                cs_count=int(val)
            elif o =="-i":
                timeout=int(val)
            else:
                assert False, "unhandled option"

        debug("options: " + ', '.join( map(str,optlist) ) ) 
        debug("arguments: " + ", ".join(args ))
                        
        debug("user: <" + str(user) + "> key: <" + str(key) + ">")
    
        if len(args) == 0: 
            self.usage("missing arguments")
            sys.exit()    
        if args[0] == "help":
            self.usage("displaying help")
            sys.exit()    
        elif args[0] is None: 
            self.usage("missing argument")
            sys.exit()
        elif args[0] == "run" and user is not None and key is not None:
            self.test_performance(user,key, sample, cs_count, timeout)

if __name__ == '__main__': 
    Main().run()
        

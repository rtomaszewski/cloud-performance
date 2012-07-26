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
    def check_cs_status(self, _server, _timeout, _date_start):
        sm=self.cs.servers
       
        is_build=False
        is_timeout = False
        
        date_start=_date_start
        date_end=None
        
        timeout=_timeout*60
        time.sleep(30)
        
        while not is_build and not is_timeout : 
            try:
                server=sm.find( name=_server.name )
                debug( "checking status " + str(date_end) + "\n" + pformat(vars(_server)))

                date_end=datetime.datetime.now()
                delta=date_end - date_start

                if server.status== 'ACTIVE' :
                    is_build = True
                    break
                
                else: 
                    if  delta.total_seconds() > timeout :
                        is_timeout = True
                        break
                
            except exceptions.NotFound:
                debug("can't find server id " + _server.name + " / " + str(_server.id) + " continue checking" )
                
                if  delta.total_seconds() > timeout :
                    is_timeout = True
                    debug("timeout ERROR, can't find server id " + _server.name + " / " + str(_server.id) )
            
            time.sleep(60)
        
        return { 'date_start': date_start,
                 'date_end' : date_end,
                 'delta' : delta , 
                 'is_build' : is_build,
                 'timeout' : delta.total_seconds()
                }
        
    def check_all_cs_status(self, _servers, _timeout, _date_start):
        #all_status=[(server1, status1), (server1, status1) ]
        TODO; 
        
        return all_status
    
    def log_status(self, status, server, count):
        s="[%2d] cloud server build [" % count + server.name + '] '
         
        if status['is_build']:
            s=s+"created in " + str(status['delta'].total_seconds()) + ' seconds / ' + \
              str(status['timeout']/60.0) + ' minutes'
        
        else:
            s=s+"ERROR, can't find server or timeout after " + \
              str(status['timeout']) + ' seconds / ' + \
              str(status['timeout']/60.0) + ' minutes'
            
        log(s)
        
    def cs_create(self, count):
        name='csperform' + str(int(time.time()))
        image=112
        flavor=1
        
        log("[%2d] creating image: " % count + pformat( {'name': name, 'image' : image, 'flavor' : flavor } ) )
        
        sm=self.cs.servers
        server=sm.create(name, image, flavor)
        
        debug(pformat(vars(server)))
        
        return server
        
    def cs_delete(self, server):
        sm=self.cs.servers
        server=sm.delete(server)
        
    def test_perf_single_cs(self, sample=1):
        if not self.cs : 
            self.cs=CloudServers(self.user, self.key)
            self.cs.authenticate()
        
        i=0;
        while i<sample:
            date_start=datetime.datetime.now()
            server=self.cs_create(i)
            
            timeout=10
            status=self.check_cs_status(server, timeout, date_start)
        
            self.log_status(status, server, i)
            self.cs_delete(server)
            
            i+=1
            
    def test_multi_cs_perf(self, cs_count=1, sample=1):
        if not self.cs : 
            self.cs=CloudServers(self.user, self.key)
            self.cs.authenticate()
        
        i=0;
        while i<sample:
            servers=[]
            date_start=datetime.datetime.now()
            
            k=0
            while k < cs_count : 
                server=self.cs_create(i)
                servers.append(server)
            
            timeout=10
            all_status=self.check_all_cs_status(servers, timeout, date_start)
        
            for server, status in all_status :
                self.log_status(status, server, i)
                self.cs_delete(server)
            
            i+=1
    

class Main:
    
    def usage(self, message=None):
        if message is not None: 
            print message
        
        print """
    usage: %s [-v] [-h] [ -s # ] -u user -k key run | help
      -h - usage help 
      -v - verbose/debug output
      -u 
      -k
      -s - a number describing the test sample size; number of tests to execute  
      
      args:
        help - displays info about this program
        run - run this program
        
      example:
        1. Run 10 times the test and report the API performance results    
          $ %s -u user -k key -s 10
        
""" % (PROGRAM_NAME, PROGRAM_NAME)
    
    def test_performance(self, user, key, sample):
        t=TestRackspaceCloudServerPerformance(user,key)
        t.test_perf_single_cs(sample)
    
    def run(self): 
        debug("main start")
        debug(sys.argv[0])
        
        optlist, args = getopt.getopt(sys.argv[1:], 'vu:k:')
    
        debug("options: " + ', '.join( map(str,optlist) ) ) 
        debug("arguments: " + ", ".join(args ))
        
        user, key = None, None
        sample=1
        
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
            elif o =="-s":
                sample=int(val)
            else:
                assert False, "unhandled option"
                
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
            self.test_performance(user,key, sample)

if __name__ == '__main__': 
    Main().run()
        

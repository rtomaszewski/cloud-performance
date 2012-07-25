#! /usr/bin/python

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

DEBUG = 1
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
        
    def check_cs_status(self, _server):
        sm=self.cs.servers
       
        is_build=False
        is_timeout = False
        
        date_start=datetime.datetime.now()
        date_end=None
        
        timeout=60*10
        
        while not is_build and not is_timeout : 
            server=sm.find( name=_server.name )
            date_end=datetime.datetime.now()
            
            debug( "checking status " + str(date_end) + "\n" + pformat(vars(server)))

            delta=date_end - date_start
            
            if server.status== 'ACTIVE' :
                is_build = True
                break
            
            else: 
                if  delta.total_seconds() > timeout :
                    is_timeout = True
                    break
                
            time.sleep(60)
        
        return { 'date_start': date_start,
                 'date_end' : date_end,
                 'delta' : delta , 
                 'is_build' : is_build,
                 'timeout' : timeout
                }
        
    def log_status(self, status, server):
        s="cloud server build [" + server.name + '] ' 
        if status['is_build']:
            s=s+"created in " + str(status['delta'].total_seconds()) + ' seconds'
        
        else:
            s=s+"timeout after " + str(status['timeout']) + ' seconds'
            
        log(s)
        
    def cs_create(self):
        name='csperform' + str(int(time.time()))
        image=112
        flavor=1
        
        log("creating image: " + pformat( {'name': name, 'image' : image, 'flavor' : flavor } ) )
        
        sm=self.cs.servers
        server=sm.create(name, image, flavor)
        
        debug(pformat(vars(server)))
        
        return server
        
    def cs_delete(self, server):
        sm=self.cs.servers
        server=sm.delete(server)
        
    def test_perf_single_cs(self, nr):
        if not self.cs : 
            self.cs=CloudServers(self.user, self.key)
            self.cs.authenticate()
           
        server=self.cs_create()
        time.sleep(60)
        status=self.check_cs_status(server)
        
        self.log_status(status, server)
        
        self.cs_delete(server)
        
    

class Main:
    
    def usage(self, message=None):
        if message is not None: 
            print message
        
        print """
    usage: %s [-v] [-h] -u user -k key run | help
      -h - usage help 
      -v - verbose/debug output
      -c - specify the file name with the json specification what cloud server should be created
      -u 
      -k 
      
      args:
        help - displays info about this program
        run - run this program 
""" % PROGRAM_NAME       
    
    def test_performance(self, user, key):
        t=TestRackspaceCloudServerPerformance(user,key)
        t.test_perf_single_cs(1)
    
    def run(self): 
        debug("main start")
        debug(sys.argv[0])
        
        optlist, args = getopt.getopt(sys.argv[1:], 'vu:k:')
    
        debug("options: " + ', '.join( map(str,optlist) ) ) 
        debug("arguments: " + ", ".join(args ))
        
        user, key = None, None
        
        for o, val in optlist:
            if o == "-v":
                DEBUG = 1
            elif o == "-h":
                self.usage()
                sys.exit()
            elif o =="-u":
                user=val
            elif o =="-k":
                key=val
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
            self.test_performance(user,key)

if __name__ == '__main__': 
    Main().run()
        

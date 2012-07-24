#! /usr/bin/python

import getopt
import sys
import httplib
from pprint import pprint
from pprint import pformat
import json
import re
import time

from cloudservers import CloudServers

class Main:
    DEBUG = 1
    PROGRAM_NAME="performance-single-cs.py"
    
    def log(self, message):
        print message 

    def debug(self, message):
        if self.DEBUG>0:
            self.log("debug[%2d]: " % self.DEBUG + message)


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
""" % self.PROGRAM_NAME       
    
    def run(self): 
        self.debug("main start")
        self.debug(sys.argv[0])
        
        optlist, args = getopt.getopt(sys.argv[1:], 'vu:k:')
    
        self.debug("options: " + ', '.join( map(str,optlist) ) ) 
        self.debug("arguments: " + ", ".join(args ))
        
        user, key = None, None
        
        for o, val in optlist:
            if o == "-v":
                self.DEBUG = 1
            elif o == "-h":
                self.usage()
                sys.exit()
            elif o =="-u":
                user=val
            elif o =="-k":
                key=val
            else:
                assert False, "unhandled option"
                
        self.debug("user: <" + str(user) + "> key: <" + str(key) + ">")
    
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
            cs=CloudServers(user, key)
            cs.authenticate()
            
            sm=cs.servers()
            sm.list()


if __name__ == '__main__': 
    Main().run()
        

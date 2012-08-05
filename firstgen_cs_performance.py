#!/usr/bin/env python

import getopt
import sys
import httplib
from pprint import pprint
from pprint import pformat
import json
import re
import time
import datetime
import threading
import Queue 
import thread

from cloudservers import CloudServers
from cloudservers import exceptions

DEBUG = 0
PROGRAM_NAME="performance-single-cs.py"

L_LOCK = thread.allocate_lock()

def log(message):
    L_LOCK.acquire()
    print message 
    L_LOCK.release()

def debug(message):
    if DEBUG>0:
        log("debug[%2d]: " % DEBUG + message)



"""
    status     = {
        'date_start': date_start,
        'date_end' : None,
        'is_build' : False,
    }
    
    cs_record  = {
        'cs' : server,
        'status' : status,
    }
    
    cs_records=[]
"""
class CServers:
    sample_cs_count=None
    current_cs_count=None
    
    cs_records=[]
    max_time=None
    timeout=None
    
    l_build=thread.allocate_lock()
    
    def __init__(self, timeout, cs_count):
        self.timeout=timeout
        self.sample_cs_count=cs_count
        self.current_cs_count=0
        self._aux_index = -1
        
        now=datetime.datetime.now()
        delta=datetime.timedelta(minutes=self.timeout)
        self.max_time=now + delta
    
    def add_server(self, s):
        self.l_build.acquire()
        
        if self.current_cs_count + 1 > self.sample_cs_count:
            log("[%d][%d] error, trying to add too many cloud servers" % (self.sample_cs_count , self.current_cs_count +1))
            sys.exit()
                     
        self.cs_records.append(s)
        self.current_cs_count+=1
        self.set_max_time()
        
        self.l_build.release()

    def is_create_complete(self):
        ret=False
        
        self.l_build.acquire()
        if self.current_cs_count == self.sample_cs_count:
            ret=True
        self.l_build.release()
        
        return ret
    
    def is_build_complete(self):
        if self.is_create_complete():
            for rec in self.cs_records:
                if not rec['status']['is_build'] :
                    return False 
                
        else:
            return False
        
        return True
    
#    def get_server(self):
#        pass
    
    def get_server_to_check_index(self):
        return self._aux_index
    
    def get_all_servers(self):
        i=0
        while i < len(self.cs_records) :
            rec=self.cs_records[i]
            yield (i, rec['cs'] )
            i+=1
        
    def get_all_failed_servers(self):
        i=0
        while i < len(self.cs_records) :
            s=self.cs_records[i]
            if not s['status']['is_build'] :
                yield (i , s)
            i+=1
    
    def get_servers_to_check(self):
        if -1 == self._aux_index: 
            i=0
        else:
            i=self._aux_index + 1
        
        while i < len(self.cs_records) :
            #i=self._aux_index
            s=self.cs_records[i]
            if not s['status']['is_build'] :
                debug('checking server cs_records[%d] with name %s' % (i, s['cs'].name ))
                self._aux_index=i
                yield s
            i+=1
        
        self._aux_index=-1
    
    def get_max_time(self):
        return self.max_time
    
    def set_max_time(self):
        
        last_data_start= self.cs_records[self.current_cs_count-1]['status']['date_start']
        now=datetime.datetime.now()
        
        delta=datetime.timedelta(minutes=self.timeout)
        self.max_time=now + delta
        
        return self.max_time

    def get_count(self):
        return self.current_cs_count

class FirstGenCloud:
    l_cloud=thread.allocate_lock()
    
    def __init__ (self, user, key):
        self.user = user
        self.key = key

        self.cs=CloudServers(self.user, self.key)
        self.cs.authenticate()
        self.sm=self.cs.servers
    
    def create(self, *args , **kwargs):
        try:
            self.l_cloud.acquire()
            ret=self.sm.create(*args, **kwargs)
            self.l_cloud.release()
        
        except Exception:
            self.l_cloud.release()
            raise
        
        return ret
    
    def find(self, *args , **kwargs):
        try:
            self.l_cloud.acquire()
            ret=self.sm.find(*args, **kwargs)
            self.l_cloud.release()
        
        except Exception:
             self.l_cloud.release()
             raise
             
        return ret

    def delete(self, *args , **kwargs):
        try:
            self.l_cloud.acquire()
            ret=self.sm.delete(*args, **kwargs)
            self.l_cloud.release()
        
        except Exception:
            self.l_cloud.release()
            raise
                    
        return ret

class TestRackspaceCloudServerPerformance:
    mycservers=None
    
    def __init__ (self, cloud_manager, sample=1, cs_count=1, timeout=10 ):
        self.cloud_manager = cloud_manager
        self.sample=sample
        self.cs_count= cs_count
        self.timeout=timeout
        
        l_is_check_done=thread.allocate_lock()
        

    def check_cs_status(self, cs_record, cs_index): 
        _server=cs_record['cs']
        _status=cs_record['status']
        _date_start=_status['date_start']
        
        is_build=False
 
        try:
            checking_now= datetime.datetime.now()
            server=self.cloud_manager.find( name=_server.name )
            debug( "checking status of cs index " + str(cs_index) + "->" + _server.name + " " +  str(checking_now) + "\n" + pformat(vars(_server)))

        except exceptions.NotFound:
                debug("can't find server name " + _server.name + " / id " + str(_server.id) + " / time " + str(checking_now)  + " continue checking" )
                return is_build

        if server.status== 'ACTIVE' :
            is_build=True
            _status['is_build']=is_build
            _status['date_end']=checking_now

        return is_build
        
    #9def check_all_cs_status(self, cs_records, max_time, sample):
    
    def check_all_cs_status(self, sample_nr): 
        debug('func check_all_cs_status start')
         
        is_build=False
        is_timeout=False
        
        while not is_build and not is_timeout :
            for s in self.mycservers.get_servers_to_check():
                if self.check_cs_status(s, self.mycservers.get_server_to_check_index()):
                    self.log_status2(s, sample_nr, self.mycservers.get_server_to_check_index())
                    self.cs_delete(s['cs'])
            
            if self.mycservers.is_build_complete():
                is_build=True
                break
                
            now=datetime.datetime.now()
            if now > self.mycservers.get_max_time():
                is_timeout=True
                
                for cs_nr, cs_record in self.mycservers.get_all_failed_servers():
                    _status=cs_record['status']
                    _status['date_end']=now
                    self.log_status2(cs_record, sample_nr, cs_nr)
                
                break
            
            time.sleep(60)
        
        return is_build
    
    def log_status2(self, cs_record, sample_nr, cs_count):
        _server=cs_record['cs']
        _status=cs_record['status']
        
        self.log_status(_status, _server, sample_nr, cs_count)
    
    def log_status(self, status, server, sample, cs_count):
        s="[%2d][%2d] cloud server build [" % (sample, cs_count+1 )+ server.name + '] '
        
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
        debug("deleting server %s" % server.name)
        self.cloud_manager.delete(server)

    def cs_delete_all(self):
        debug("func cs_delete_all start")
        
        for i, s in self.mycservers.get_all_servers():
            self.cs_delete( s )         
        
    def cs_create(self, count, sample_nr):
        name='csperform' + str(int(time.time()))
        image=112
        flavor=1
        
        server=self.cloud_manager.create(name, image, flavor)
        
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
    def cs_create_all(self, sample_nr):
        self.mycservers=CServers(self.timeout, self.cs_count)
        
        log("[%2d][  ] starting test nr %d, creating %d cloud server, please wait ..." % (sample_nr, sample_nr, self.cs_count) )
        
        api_time_limit=60
        hard_limit=10
        
        build_nr=1
        delayed_10s=False
        
        while build_nr <= self.cs_count :
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
        
            #cs_records.append(cs_record)
            self.mycservers.add_server(cs_record)
            
            build_nr+=1
        
        return self.mycservers
    
    def start_test(self, test_nr):
        log('thread %s started' %  threading.current_thread().getName() )
        
        self.cs_create_all(test_nr)
        debug("all %d cloud servers created" % self.mycservers.get_count())
    
    def evaluate_test(self, test_nr):
        
        log('thread %s started' %  threading.current_thread().getName() )
        time.sleep(30)
        self.check_all_cs_status(test_nr)
        debug("%d cloud servers checked " % self.mycservers.get_count())
    
    def finish_test(self):
        self.cs_delete_all()
        debug("%d cloud servers deleted" % self.mycservers.get_count())
                
    def test_multi_cs_perf(self):
        debug('func test_multi_cs_perf start')
        
        for i in range(0, self.sample):
            log("[ ][ ] starting test nr %d" % (i+1) )
            t=threading.Thread( target=self.start_test, name="start_test", args=(i+1,))
            t.start()
            
            t=threading.Thread( target=self.evaluate_test, name="eval_test", args=(i+1,))
            t.start()
            
            main_thread = threading.currentThread()
            for t in threading.enumerate():
                if t is main_thread:
                    continue
                t.join()
            
            debug("all threads finished, destroying remaining servers")
            self.finish_test()
            

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
        
        cloud_manager=FirstGenCloud(user, key)
        t=TestRackspaceCloudServerPerformance(cloud_manager, sample, cs_count, timeout )
        t.test_multi_cs_perf()
    
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
        


















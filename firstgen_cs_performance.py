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
import paramiko
import traceback

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

class RcConnectionTestException(Exception):
    def __init__(self, value):
         self.value = value
         
    def __str__(self):
         return repr(self.value)

class RackConnect:
        
    def __init__(self, password, cs_ip):
        self.rcbastion_ip = cs_ip
        self.rcbastion_pass = password
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy( paramiko.AutoAddPolicy() )
        self.ssh.connect(self.rcbastion_ip, username='root', password=self.rcbastion_pass)
        debug("established connection to bastion host %s" % self.rcbastion_ip)
        
        self.rc_test_script_path="/root/"
        self.rc_test_script_name="check_rackconnect.sh"
        self.rc_test_script= self.rc_test_script_path + self.rc_test_script_name
        
        self.test_servers = []
        self.keep_alive_thread = None
        self.is_stop_keep_alive = False
        self.test_cmd = 'id -u'
        
        self.l_ssh_access=thread.allocate_lock()
    
    def exec_debug_logs(self, cmd, stdout, stderr  ):
        if DEBUG :  
            debug('exec cmd              : %s' % cmd)
            
            if 0 == len(stdout):
                pass
            if 1 == len(stdout):
                debug('exec logs for stdout  : ' + str(stdout))
            else: 
                debug('exec logs for stdout : \n' + str(stdout))
                
            if 0 == len(stderr):
                pass
            elif 1 == len(stderr):
                debug('exec logs for stderror: ' + str(stderr))
            else:
                debug('exec logs for stderror: \n' + str(stderr))
    
#    def exec_command(self, cmd, passw=None):
#        self.l_ssh_access.acquire()
#        
#        out, err = self.ssh.exec_command(cmd)
#        
#        stdout = list(out)
#        stderr = list(err) 
#        
#        self.l_ssh_access.release()
#        
#        self.exec_debug_logs(cmd, stdout, stderr)
#
#        return (stdout, stderr)
    
    def _scp_rc_test_script_cs(self, priv_ip, passw):
        if DEBUG: 
            scp_opt="-v"
        
        cmd='scp -q ' + scp_opt + ' -o NumberOfPasswordPrompts=1 -o StrictHostKeyChecking=no %s root@%s:~/; echo $? done.' % \
             ( self.rc_test_script, priv_ip )
        
        debug(cmd)
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy( paramiko.AutoAddPolicy() )
        ssh.connect(self.rcbastion_ip, username='root', password=self.rcbastion_pass)
        debug("trying scp a file from bastion %s to cloud server %s" % (self.rcbastion_ip, priv_ip ))
        
        chan = ssh.invoke_shell()
        
        # Ssh and wait for the password prompt.
        chan.send(cmd + '\n')
        buff = ''
        while not buff.endswith('\'s password: '):
            resp = chan.recv(9999)
            buff += resp
            debug(resp)
            
        # Send the password and wait for a prompt.
        time.sleep(3)
        debug("sending pass for scp: <%s> " % passw)
        chan.send(passw + '\n')
        
        buff = ''
        while buff.find(' done.') < 0 :
            resp = chan.recv(9999)
            buff += resp
            debug(resp)
            
        ret=re.search('(\d) done.', buff).group(1)
        ssh.close()
        
        return ret==0 # successfully scp a file  
    
    def _run_rc_test_script_on_cs(self, priv_ip, passw):
        if DEBUG: 
            scp_opt="-v"
        
        cmd='ssh -t ' + ssh_opt + ' -o NumberOfPasswordPrompts=1 -o StrictHostKeyChecking=no root@%s %s ; echo $? done.' % \
             ( priv_ip, self.rc_test_script )
        
        debug(cmd)
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy( paramiko.AutoAddPolicy() )
        ssh.connect(self.rcbastion_ip, username='root', password=self.rcbastion_pass)
        debug("running rc test script from bastion %s to the cloud server %s" % (self.rcbastion_ip, priv_ip ))
        
        chan = ssh.invoke_shell()
        
        # Ssh and wait for the password prompt.
        chan.send(cmd + '\n')
        buff = ''
        while not buff.endswith('\'s password: '):
            resp = chan.recv(9999)
            buff += resp
            debug(resp)
            
        # Send the password and wait for a prompt.
        time.sleep(3)
        debug("sending pass for ssh: <%s> " % passw)
        chan.send(passw + '\n')
        
        buff = ''
        while buff.find(' done.') < 0 :
            resp = chan.recv(9999)
            buff += resp
            debug(resp)
            
        ret=re.search( '(\w+)\n(\d) done.', buff).group(1)
        ssh.close()
        
        return ret=='yes' # successfully scp a file  
    
    def exec_command(self, cmd, passwd=None):
        self.l_ssh_access.acquire()
        
        input, out, err = self.ssh.exec_command(cmd)
        
        stdout = list(out)
        stderr = list(err) 
        
        self.l_ssh_access.release()
        self.exec_debug_logs(cmd, stdout, stderr)
        
        return (stdout, stderr)
        
    def _keep_connection_alive(self):
        delay=0
        delta=3
        while not self.is_stop_keep_alive:
            if 0 == delay % 30  :
                self._test()

            delay+=delta
            time.sleep(delta)
    
    def _keep_connection_alive_thread(self):
        self.keep_alive_thread=threading.Thread( target=self._keep_connection_alive, name="bastion_keep_alive")
        self.keep_alive_thread.start()
        
    def _stop_keep_alive_thread(self):
        debug("stopping keep alive thread")
        self.is_stop_keep_alive=True
        self.keep_alive_thread.join()

    def _test(self):
        cmd=self.test_cmd
        stdout, stderr = self.exec_command(cmd)
        
        id=int(stdout[0].strip())
        if 0 != id:
            log("rc test failed, id=%d" % id)
            raise RcConnectionTestException('connection test failed')
        
        return True

    def start(self):
        debug("doing initial testing if connection is alive")
        self._test()

        log("[ ][ ] starting thread to keep the connection to bastion alive %s" % str(datetime.datetime.now()) )
        self._keep_connection_alive_thread()
        
    def close(self):
        self._stop_keep_alive_thread() 
    
    def check_server(self, server):
        priv_ip=server.addresses['private'][0]
        passw=server.adminPass
        
        if not priv_ip in self.test_servers:
            if self._scp_rc_test_script_cs(priv_ip, passw):
                log("ERROR, can't copy a file to cloud server %s" % priv_ip)
            else:
                self.test_servers.append(priv_ip)
                return False

        return self._run_rc_test_script_on_cs(priv_ip, passw)
        
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
    def __init__(self, timeout, cs_count):
        self.timeout=timeout
        self.sample_cs_count=cs_count
        self.current_cs_count=0
        self._aux_index = -1
        
        now=datetime.datetime.now()
        delta=datetime.timedelta(minutes=self.timeout)
        self.max_time=now + delta
        
        self.cs_records=[]
        
        self.l_build=thread.allocate_lock()        
    
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
    
    def is_rc_build_complete(self):
        if self.is_build_complete():
            for rec in self.cs_records:
                if not rec['rackconnect']['is_build'] :
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

    def get_all_failed_rc_servers(self):
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
    
    def get_all_built_servers(self):
       i=0
       while i < len(self.cs_records) :
            s=self.cs_records[i]
            if s['status']['is_build'] :
                yield (i , s)
            i+=1
    
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
            debug("ERROR, creation problem")
            self.l_cloud.release()
            raise
        
        return ret
    
    def find(self, *args, **kwargs):
        try:
            self.l_cloud.acquire()
            ret=self.sm.find(*args, **kwargs)
            self.l_cloud.release()
        
        except Exception as inst:
            debug("ERROR, finding problem")
#            print type(inst)     # the exception instance
#            print inst.args      # arguments stored in .args
#            print inst           # __str__ allows args to printed directly

            self.l_cloud.release()
            raise
            
        return ret
    
    def get(self, *args, **kwargs):
        try:
            self.l_cloud.acquire()
            ret=self.sm.get(*args, **kwargs)
            self.l_cloud.release()
        
        except Exception as inst:
            debug("ERROR, get problem")
#            print type(inst)     # the exception instance
#            print inst.args      # arguments stored in .args
#            print inst           # __str__ allows args to printed directly

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
            debug("ERROR, delete return exception")
            raise
                    
        return ret

class TestRackspaceCloudServerPerformance:
    
    def __init__ (self, cloud_manager, sample=1, cs_count=1, timeout=10 ):
        self.cloud_manager = cloud_manager
        self.sample=sample
        self.cs_count= cs_count
        self.timeout=timeout
        
        l_is_check_done=thread.allocate_lock()
        self.mycservers=None
        self.rc_manager = None

    def check_cs_status(self, cs_record, cs_index): 
        _server=cs_record['cs']
        _status=cs_record['status']
        _date_start=_status['date_start']
        
        is_build=False
 
        try:
            checking_now= datetime.datetime.now()
            #server=self.cloud_manager.find( name=_server.name )
            server=self.cloud_manager.get( _server.id )
            debug( "checking status of cs index " + str(cs_index) + "->" + server.name + " " +  str(checking_now) + "\n" + pformat(vars(server)))

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
#                    self.cs_delete(s['cs'])
            
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
    
    def log_status3(self, cs_record, sample, cs_count):
        server=cs_record['cs']
        status=cs_record['status']
        rc_status=cs_record['rackconnect']
        
        s="[%2d][%2d] rackconnect build [" % (sample, cs_count+1 )+ server.name + '] '

        rc_status['delta'] = rc_status['date_end'] - status['date_end']
        rc_status['timeout'] = rc_status['delta'].total_seconds()
        
        if rc_status['is_build']:
            s=s+"finished in " + str(rc_status['delta'].total_seconds()) + ' seconds / ' + \
              str(rc_status['timeout']/60.0) + ' minutes'
        
        else:
            s=s+"ERROR, couldn't find server or timeout after " + \
              str(rc_status['timeout']) + ' seconds / ' + \
              str(rc_status['timeout']/60.0) + ' minutes'
            
        log(s)
    
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
            try:
                self.cs_delete( s )         
            except Exception as e:
                debug("error when deleting server %s, continue" % s.name)
        
    def cs_create(self, count, sample_nr):
        name='csperform' + str(int(time.time()))
        image=112
        flavor=1
        
        server=self.cloud_manager.create(name, image, flavor)
        
        log("[%2d][%2d] created image: " % (sample_nr, count) + pformat( {'name': name, 'image' : image, 'flavor' : flavor } ) )
        debug(pformat(vars(server)))
        
        return server

#    def cs_create(self, _name):
#        name=_name + str(int(time.time()))
#        image=112
#        flavor=1
#        
#        server=self.cloud_manager.create(name, image, flavor)
#        
#        log("[  ][  ] created cs "  + pformat( {'name': name, 'image' : image, 'flavor' : flavor } ) )
#        debug(pformat(vars(server)))
#        
#        return server

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
        exception_delay=60
        #hard_limit=10
        
        build_nr=1
        delayed_10s=False
        
        while build_nr <= self.cs_count :
            if 0==build_nr % 11 and not delayed_10s:
                debug("created %d servers, introducing delay" % build_nr)
                time.sleep(api_time_limit+10)
                
            try:
                date_start = datetime.datetime.now() 
                server = self.cs_create(build_nr, sample_nr)
                delayed_10s=False
                
            except exceptions.OverLimit:
                hit_time= datetime.datetime.now()
                log("ERROR, hit the API limit at " + str(hit_time) + ", imposing delay of %s" % api_time_limit)
                #time.sleep(api_time_limit)
                #delayed_10s=True
                
                return self.mycservers
            
            except exceptions.BadRequest:
                hit_time= datetime.datetime.now()
                log("warning, bad request sent or bad response at " + str(hit_time) + ", imposing delay of %s" % exception_delay)
                time.sleep(exception_delay)
                delayed_10s=True
                
                continue
            
            except Exception, e :
                hit_time= datetime.datetime.now()
                log("warning, exception [ " + str(e) +" ]when creating cs at " + str(hit_time) + ", imposing delay of %s" % exception_delay)
                debug(traceback.format_exc())
                time.sleep(exception_delay)
                delayed_10s=True
                
                continue
    
            status     = {
                'date_start': date_start,
                'date_end' : None,
                'is_build' : False,
            }
            
            rc_status = {
#                'date_start': date_start,
                'date_end' : None,
                'is_build' : False,
            }
            
            cs_record  = {
                'cs' : server,
                'status' : status,
                'rackconnect' : rc_status
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
#        time.sleep(5)
        self.check_all_cs_status(test_nr)
        debug("%d cloud servers checked " % self.mycservers.get_count())
    
    def finish_test(self):
        self.cs_delete_all()
        debug("%d cloud servers deleted" % self.mycservers.get_count())

    def check_single_cs_rc_build(self, cs_record, cs_index):
        _server=cs_record['cs']
        _status=cs_record['status']
        _rc_status=cs_record['rackconnect']
        
        _rc_status['is_build']=True
        _rc_status['date_end']=None
        
        is_build=False
 
        try:
            checking_now= datetime.datetime.now()
            status=self.rc_manager.check_server(_server)
            debug( "checking rc status of cs index " + str(cs_index) + "->" + _server.name + " " +  str(checking_now) + "\n" + pformat(vars(_server)))

        except Exception, e: 
                debug("exception when checking rc status, server name " + _server.name + " / id " + str(_server.id) + " / time " + str(checking_now)  + " continue checking" )
                debug(traceback.format_exc())
                return is_build

        if True == status:
            is_build=True
            _rc_status['is_build']=is_build
            _rc_status['date_end']=checking_now

        return is_build
    
    def evaluate_rackconnect_status(self, test_nr):
        log('thread %s started' %  threading.current_thread().getName() )
        #time.sleep(120)
        time.sleep(7)

        try:
            self.rc_manager=RackConnect( *self.rcbastion.split('@') )
            self.rc_manager.start()
        except :
            log('ERROR, please check provided password and ip for the bastion server')
            raise

        is_build=False
        is_timeout=False
        delta=datetime.timedelta(minutes=self.timeout)
        
        debug("delta for rc is " + str(delta))
        
        while not is_build and not is_timeout :
            for i, s in self.mycservers.get_all_built_servers():
                if self.check_single_cs_rc_build(s, i):
                    self.log_status3(s, sample_nr, i)
                    self.cs_delete(s['cs'])

            if self.mycservers.is_rc_build_complete():
                is_build=True
                break

            cs_build_max_time=self.mycservers.get_max_time()
            rc_max_time=cs_build_max_time + delta
            
            now=datetime.datetime.now()

            debug("now is %s and rc_max_time for rc is %s" % (now, str(rc_max_time)) )
            
            if now > rc_max_time:
                is_timeout=True
                log('rackconnect evaluation is running too long, timeout has been reached')
                
                for cs_nr, cs_record in self.mycservers.get_all_failed_rc_servers():
                    rc_status=cs_record['rackconnect']
                    rc_status['date_end']=now
                    self.log_status3(cs_record, test_nr, cs_nr)
                break
            
            time.sleep(60)
        
        self.rc_manager.close()
        
        debug("rackconnect checked %d cloud servers" % self.mycservers.get_count())
                    
    def test_multi_cs_perf(self):
        debug('func test_multi_cs_perf start')
        log("[ ][ ] Preparing to start all %d tests" % (self.sample) )
        
        for i in range(0, self.sample):
            log("[ ][ ] test nr %d started at %s" % (i+1, datetime.datetime.now() ) )
            t=threading.Thread( target=self.start_test, name="start_test", args=(i+1,))
            t.start()
            
            t=threading.Thread( target=self.evaluate_test, name="eval_test", args=(i+1,))
            t.start()
            
            t=threading.Thread( target=self.evaluate_rackconnect_status, name="eval_rackconnect", args=(i+1,))
            t.start()
            
            main_thread = threading.currentThread()
            for t in threading.enumerate():
                if t is main_thread:
                    continue
                t.join()
            
            debug("all threads finished, destroying remaining servers")
            self.finish_test()
            log("[ ][ ] test nr %d finished at %s" % (i+1, datetime.datetime.now() ) )
            
            self.generate_report(i+1)

    def generate_report(self, test_nr):
        self.mycservers
        
        debug("report %d start" % test_nr)
        
        debug(pformat(vars(self.mycservers)))
        

    def set_bastion(self, rcbastion):
        self.rcbastion = rcbastion
    
class Main:
    
    def usage(self, message=None):
        if message is not None: 
            print message
        
        print """
    usage: %s [-v] [-h] [ -t # ] [ -s # ] [ -i # ] -b password@IP -u user -k key run | help
      -h - usage help 
      -v - verbose/debug output
      -u 
      -k
      -i - wait # minutes for the cloud server to be created  
      -t - how many repetitive tests to execute   
      -s - a test sample size; how many cloud servers to create in a single test run
      -b - public IP of an existing bastion server and root password 
      
      args:
        help - displays info about this program
        run - run this program
        
      example:
        1. Run a 2 test sessions and create and measure the API performance of creating one cloud sever     
          $ %s -u user -k key -t 2 -s 1
        
""" % (PROGRAM_NAME, PROGRAM_NAME)
    
    def test_performance(self, user,key, sample, cs_count, timeout, rcbastion):
        debug('func test_performance start')
        
        cloud_manager=FirstGenCloud(user, key)
        t=TestRackspaceCloudServerPerformance(cloud_manager, sample, cs_count, timeout )
        t.set_bastion(rcbastion)
        t.test_multi_cs_perf()
    
    def run(self): 
        debug("main start")
        debug(sys.argv[0])
        
        optlist, args = getopt.getopt(sys.argv[1:], 'vu:k:t:s:i:b:')
    
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
            elif o =="-b":
                rcbastion=val
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
            self.test_performance(user,key, sample, cs_count, timeout, rcbastion)

if __name__ == '__main__': 
    Main().run()
        


















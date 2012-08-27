#!/bin/bash

set -v -x 

delay=7
result="/tmp/rc.log"
result_done="$result.done"
background_job="$result.backgroud"
log="$result.$(date +%s)"
log_tmp="$log.inprogress"

debug=$1
if [ $# -gt 1 ]; then
   background=yes
else 
   background=no
fi

function ip_route {
  arg=${1:-no}

  if [ $arg = 'debug' ] ; then
    set -x
    /sbin/ip a 1>&2
    /sbin/ip r 1>&2
  fi
  set +x 
}

function rc_check {
  arg=${1:-no}

  if [ $arg = 'debug' ] ; then
    set -x
    #echo rrr
  fi

  iptables=$(/sbin/iptables -nL)
  #iptables=$(cat /root/aaa)

  set +x
  ret=no

  if echo $iptables | grep -q 'Chain INPUT .policy DROP.'    ; then
    if echo $iptables | grep -q 'Chain FORWARD .policy DROP.'  ; then
      if echo $iptables | grep -q 'Chain OUTPUT .policy ACCEPT.' ; then 
        if echo $iptables | grep -q 'Chain RS-RackConnect-INBOUND' ; then
          ret=yes
          
        fi
      fi
    fi 
  fi
}

function run {
  ip_route $1
  rc_check $1
  echo "($(date +%s) is rackconnected=$ret)"
}

function run_and_log {
  run $debug &> $log_tmp
  
  if [ $ret = 'yes' ] ; then
    touch $result_done
    echo "created $result_done file" >> $log_tmp 
  fi

  echo "finished execution: $(date )" >> $log_tmp

  mv $log_tmp $result
}

function background_task {
  touch  $background_job
  
  if [ $background = 'no' ]; then
    sleep 1
    nohup "./$0" $debug background yes &
    sleep 1
  fi
  
  run_and_log
}

function main {
  [[ ! -f $background_job ]] && background_task

  if [ $background = 'yes' ]; then

    while [ ! -f $result_done ] ; do
      sleep $delay
      run_and_log
    done

  else 
    cat $result
    exit 0 
  fi 
}

main 


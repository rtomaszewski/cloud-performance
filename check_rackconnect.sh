#!/bin/bash

iptables=$(cat tmp)
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

echo $ret

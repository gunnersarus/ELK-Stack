#!/bin/bash

IP=$1


if ! iptables -C DOCKER-USER -s "$IP" -j DROP 2>/dev/null; then

   
   iptables -I DOCKER-USER -s "$IP" -j DROP
   echo "Da them rule block IP"
else
   echo "Rule da ton tai"
fi

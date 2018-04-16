#!/bin/bash

export WORKSPACE=/home/git/repositories
#export DPDK_DIR=$WORKSPACE/dpdk
export DPDK_STABLE_DIR=$WORKSPACE/dpdk-stable
export OVS_DIR=$WORKSPACE/ovs

cd $DPDK_STABLE_DIR
git pull
cd $OVS_DIR
git pull

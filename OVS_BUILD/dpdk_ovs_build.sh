#!/bin/bash

DPDK_ORG_URL="http://dpdk.org/git/dpdk"
export WORKSPACE=/home/fangfang
export DPDK_DIR=$WORKSPACE/dpdk
export DPDK_GCC_TARGET=x86_64-native-linuxapp-gcc
export DPDK_CLANG_TARGET=x86_64-native-linuxapp-clang
export DPDK_ICC_TARGET=x86_64-native-linuxapp-icc
export DPDK_BUILD=$DPDK_DIR/$DPDK_GCC_TARGET
export OVS_DIR=$WORKSPACE/ovs
export LOG_DIR=$WORKSPACE/log

KernelVersion="`uname -r | sed 's/\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\)-\([0-9]*\)\(.*\)/\1\.\2\.\3-\4/g'`"
GCCVersion="`gcc --version | head -n 1 | grep -i 'gcc' | sed 's/[^0-9]*\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\).*/\1\.\2\.\3/g'`"
#ICCVersion="14.0.0"
ICCVersion="`/opt/intel/bin/icc --version | head -n 1 | grep -i 'icc' | sed 's/[^0-9]*\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\).*/\1\.\2\.\3/g'`"
if command -v clang >/dev/null 2&>1; then 
    CLANGVersion="`clang --version | head -n 1 | grep -i 'clang' | sed 's/^.*version\s\?//g' | sed 's/\s\?(.*$//g'`"
else 
    CLANGVersion="unknown"
fi

#########
## GCC ##
#########
OS_INFO="{[KERNEL: ${KernelVersion}],[GCC: ${GCCVersion}],[ICC: ${ICCVersion}],[CLANG: ${CLANGVersion}]}"

echo "${OS_INFO}" | tee ${LOG_DIR}/ovs-build-fc23_64-gcc.log
echo ">>>x86_64-native-linuxapp-gcc<<<" | tee -a ${LOG_DIR}/ovs-build-fc23_64-gcc.log

cd $WORKSPACE
rm -rf dpdk
rm -rf ovs
#scp -r root@10.240.176.139:/home/git/repositories/dpdk .
scp -r root@10.240.176.139:/home/git/repositories/dpdk-stable ./dpdk
scp -r root@10.240.176.139:/home/git/repositories/ovs .
#git clone ${DPDK_ORG_URL}
if ! [ -d "dpdk" ]; then
	echo "Clone dpdk source failed" | tee -a ${LOG_DIR}/ovs-build-fc23_64-gcc.log ;
fi
cd $DPDK_DIR
git pull
#sed -i 's/CONFIG_RTE_BUILD_SHARED_LIB=.*/CONFIG_RTE_BUILD_SHARED_LIB=y/' ./config/common_base
#echo ">>>CONFIG_RTE_BUILD_SHARED_LIB=y<<<" |tee -a $LOG_DIR/ovs-build-fc23_64-gcc.log
make install -j T=$DPDK_GCC_TARGET

cd $WORKSPACE
#git clone https://github.com/openvswitch/ovs.git
if ! [ -d "ovs" ] ; then
	echo "Clone ovs source failed" | tee -a ${LOG_DIR}/ovs-build-fc23_64-gcc.log ;
fi
#if ! [ -d "ovs" ] ; then
#	git clone https://github.com/openvswitch/ovs.git ;
#fi

cd $OVS_DIR
#echo ">>>uninstall previous ovs<<<" |tee -a ${LOG_DIR}/buildovs.log
#make uninstall
git pull
./boot.sh 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-gcc.log
./configure --with-dpdk=$DPDK_BUILD 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-gcc.log
echo "make install ovs" |tee -a ${LOG_DIR}/ovs-build-fc23_64-gcc.log
make install -j 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-gcc.log

###########
## CLANG ##
###########
cd $DPDK_DIR
rm -rf x86_64-native-linuxapp-gcc
echo "${OS_INFO}" | tee ${LOG_DIR}/ovs-build-fc23_64-clang.log
echo ">>>x86_64-native-linuxapp-clang<<<" | tee -a ${LOG_DIR}/ovs-build-fc23_64-clang.log
#echo ">>>CONFIG_RTE_BUILD_SHARED_LIB=y<<<" |tee -a $LOG_DIR/ovs-build-fc23_64-clang.log
make install -j T=$DPDK_CLANG_TARGET

cd $OVS_DIR
echo "uninstall previous ovs"
make uninstall
./boot.sh 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-clang.log
./configure --with-dpdk=$DPDK_DIR/$DPDK_CLANG_TARGET 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-clang.log
echo "make install ovs" |tee -a ${LOG_DIR}/ovs-build-fc23_64-clang.log
make install -j 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-clang.log

##########
## ICC  ##
##########
#source /opt/intel/bin/iccvars.sh intel64
#cd $DPDK_DIR
#rm -rf x86_64-native-linuxapp-clang
#echo "${OS_INFO}" | tee ${LOG_DIR}/ovs-build-fc23_64-icc.log
#echo ">>>x86_64-native-linuxapp-icc<<<" | tee -a ${LOG_DIR}/ovs-build-fc23_64-icc.log
#echo ">>>CONFIG_RTE_BUILD_SHARED_LIB=y<<<" | tee -a ${LOG_DIR}/ovs-build-fc23_64-icc.log
#make install -j T=$DPDK_ICC_TARGET

#cd $OVS_DIR
#echo "uninstall previous ovs"
#make uninstall
#./boot.sh 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-icc.log
#./configure --with-dpdk=$DPDK_DIR/$DPDK_ICC_TARGET 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-icc.log
#echo "make install ovs" | tee -a ${LOG_DIR}/ovs-build-fc23_64-icc.log
#make install -j 2>&1 |tee -a $LOG_DIR/ovs-build-fc23_64-icc.log

python $WORKSPACE/dpdk_ovs_build_report.py /home/fangfang/log
cd $LOG_DIR
STRING=`date +%Y%m%d-%H:%M:%S`
mkdir output$STRING
mv ovs-build* output$STRING
mv $WORKSPACE/initiator.log output$STRING
mv output$STRING $WORKSPACE/backup

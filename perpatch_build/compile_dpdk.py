# -*- coding:utf-8 -*-
#######################################################################
import os
import shutil
import sys
import re
import time
import requests
import pexpect
import subprocess
#import mailReport
from sgmllib import SGMLParser
import logging
import argparse
import commands

os.sys.path.append( os.path.dirname(__file__) + os.sep + "..") 

reload(sys)
sys.setdefaultencoding('utf-8')

share_folder = "/home/DPDK"
reports_folder = share_folder + os.sep + "patch_build_result"

#os_name = sys.argv[1]
parser = argparse.ArgumentParser(description="Per patch build test")
parser.add_argument("-o", "--os",help="The os which this test run on")
parser.add_argument("-t", "--targets",action="append",help="the target which will be builded")
args=parser.parse_args()
print "os is %s."%args.os

debugMode = 1
#################################################################################
#################################################################################
def printLog(inputStr=''):
    global debugMode
    if debugMode == 0:
        return
    
    if inputStr != '' :
        if debugMode == 2:
            logging.info(inputStr)
        else:
            print inputStr

#################################################################################
#################################################################################
def initLog():
    filename = r"/home/patchWorkOrg/reports/runningLog.log"
    filemode = 'a'
    formater = '%(asctime)s %(levelname)s:%(message)s'
    datefmt = '%m/%d/%Y %H:%M:%S'
    level = logging.INFO
    logging.basicConfig(filename=filename, 
        filemode=filemode,
        datefmt=datefmt, 
        level=level,
        format=formater)

#################################################################################
#################################################################################
def sendPexpect(cmdStr,expectStr=list(),answerStr=list()):    
    p = pexpect.spawn(cmdStr)
    time.sleep(1)
    try:
        expectLength = len(expectStr)
        cnt = 0
        while cnt < expectLength:
            idx = p.expect(expectStr)
            print idx
            if idx < expectLength:
                p.sendline(answerStr[idx])
            cnt = cnt + 1

    except pexpect.TIMEOUT:
        print >>sys.stderr, 'timeout'
    except pexpect.EOF:
        print p.before
        print >>sys.stderr, '<the end>'

def get_version(cmd):
    rt,output = commands.getstatusoutput(cmd)
    if rt == 0:
        version = output
        print "&&&&&&&&&&&&&&&&&&&version is %s"%version
    else:
        version = "NA"
    return version

def get_sys_config(log_path):
    config = []
    kernel_info = subprocess.check_output("uname -r", shell=True)
    kernel_info = kernel_info.strip()
    config.append("Kernel Version:"+kernel_info +"\n")
    if "FreeBSD" in args.os:
        cpu_info = os.popen("grep -i CPU: /var/run/dmesg.boot")
        cpu_info = cpu_info.read().split("\n")[0]
        config.append("CPU info:"+cpu_info.lstrip("CPU:") +"\n")
        #gcc_info = subprocess.check_output("gcc48 --version", shell=True)
        #gcc_info = get_version("gcc48 --version")
        #config.append("GCC Version:%s" %gcc_info.split('\n')[0].strip())
    else:
        cpu_info = subprocess.check_output("cat /proc/cpuinfo |grep 'model name'|uniq|awk -F: '{print $2}'", shell=True)
        cpu_info = cpu_info.strip()
        config.append("CPU info:"+cpu_info)
    gcc_info = get_version("gcc --version")
    config.append("GCC Version:%s" % gcc_info.split('\n')[0].strip())
    #clang_version = subprocess.check_output("clang --version | head -n 1 | grep -i 'clang' | sed 's/^.*version\s\?//g' | sed 's/\s\?(.*$//g'", shell=True)
    clang_info = get_version("clang --version")
    if clang_info is not "NA":
        m = re.search("clang version\s+(\d+\.\d+\.\d+).*\n", clang_info)
        if m:
            clang_info = m.group(1)
            print "********************************clang info is %s."%clang_info
    print "&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&clang info is %s."%clang_info
    config.append("Clang Version:%s" % clang_info)
    #icc_version = subprocess.check_output("/opt/intel/bin/icc --version | head -n 1", shell=True)
    icc_info = get_version("/opt/intel/bin/icc --version")
    if icc_info != "NA":
        m = re.search("icc\s+\(ICC\)\s+(\d+\.\d+\.\d+).*\n", icc_info)
        if m:
            icc_info = m.group(1)
    config.append("ICC Version:%s" % icc_info)
    with open(log_path+ os.sep +"system.conf", "wb") as code:
        code.write(str(config))
    print config


################################################################################################
#
################################################################################################
class Compilation():
    '''
    '''
    #################################################################################
    def __init__(self, basePath):
        # compilation
        self.branchName = ""
        self.logsPath = ""
        
        self.basePath = basePath
        self.compilePath = basePath + os.sep + "compilation"
        self.compileTargets = ["x86_64-native-linuxapp-gcc","i686-native-linuxapp-gcc","x86_64-native-linuxapp-gcc-debug","x86_64-native-linuxapp-gcc-shared","x86_64-native-linuxapp-gcc-combined","x86_64-native-linuxapp-clang","x86_64-native-linuxapp-icc","i686-native-linuxapp-icc"]
        self.base_config = ["sed -i -e 's/PMD_PCAP=n$/PMD_PCAP=y/' config/common_base","sed -i -e 's/IGB_UIO=y$/IGB_UIO=n/' config/common_base","sed -i -e 's/KNI_KMOD=y$/KNI_KMOD=n/' config/common_base"]
        self.debug_config = "sed -i -e 's/DEBUG=n$/DEBUG=y/' config/common_base"
        self.shared_config = "sed -i -e 's/SHARED_LIB=n$/SHARED_LIB=y/' config/common_base"
        self.combine_config = "sed -i -e 's/COMBINE_LIBS=n$/COMBINE_LIBS=y/' config/common_base"
        self.icc_64_config = "source /opt/intel/bin/iccvars.sh intel64"
        self.icc_32_config = "source /opt/intel/bin/iccvars.sh ia32" 
        self.compileLog = dict()


    #################################################################################
    def setLogsPath(self):
        path_info = open(share_folder+ os.sep +"info.txt")
        path = path_info.read()
        path_info.close()
        path = self.basePath + os.sep +"reports/patch_" + path.strip()
        if not os.path.exists(path):
            os.mkdir(path)
        return path
        #self.logsPath = path

    def compile_target(self,target_list):
        for target in target_list:
            target_name = target
            os.system("export RTE_SDK=`pwd`")
            if target.startswith("x86_64-native-linuxapp-gcc"):
                target = "x86_64-native-linuxapp-gcc"
            os.system("rm -rf " + target)
            os.system("export RTE_TARGET=%s" %target)
            printLog("make %s compiling....."%target_name)
            if target != "i686-native-linuxapp-gcc":
                for _ in self.base_config:
                    os.system(_)
            if "debug" in target_name:
                os.system(self.debug_config)
            if "shared" in target_name:
                os.system(self.shared_config)
            if "combined" in target_name:
                os.system(self.combine_config)
            if target_name == "x86_64-native-linuxapp-icc":
                os.system(self.icc_64_config)
            if target_name == "i686-native-linuxapp-icc":
                printLog("start to execute command: %s" % self.icc_32_config)
                os.system(self.icc_32_config)

            if "FreeBSD" in args.os:
                self.make = "gmake"
            else:
                self.make = "make" 
            os.system("%s -j1 install T=" % self.make + target + " > " + self.dtsReportFolder + "/compile_" + target_name + ".log 2>&1")
            #os.system("echo KG,kernal:3.11.10,gcc:4.8.3"  + " > " + self.dtsReportFolder + "/system.log")
            os.system("rm -fr " + "%s"%target)

        # record compile log
        for target in target_list:
            logPath = self.dtsReportFolder + os.sep +"compile_" + target + ".log"
            if os.path.exists(logPath) == False:
                printLog("[%s] is not exist"%logPath)
                self.compileLog[target] = "error"
                continue

            fp = open(logPath,'r')
            content = "".join(fp.readlines())
            pattern = "Build complete"

            m = re.findall(pattern, content,re.MULTILINE)
            if len(m)>0:
                self.compileLog[target] = "success"
            else:
                self.compileLog[target] = "error"


    #################################################################################
    def compileDpdk(self):
        '''
        make a full compilation
        '''
        printLog("enter compilation checking.....")
        """
        base_config = ["sed -i -e 's/PMD_PCAP=n$/PMD_PCAP=y/' config/common_base","sed -i -e 's/IGB_UIO=y$/IGB_UIO=n/' config/common_base","sed -i -e 's/KNI_KMOD=y$/KNI_KMOD=n/' config/common_base"]
        debug_config = "sed -i -e 's/DEBUG=n$/DEBUG=y/' config/common_base"
        shared_config = "sed -i -e 's/SHARED_LIB=n$/SHARED_LIB=y/' config/common_base"
        combine_config = "sed -i -e 's/COMBINE_LIBS=n$/COMBINE_LIBS=y/' config/common_base"
        icc_64_config = "source /opt/intel/bin/iccvars.sh intel64"
        icc_32_config = "source /opt/intel/bin/iccvars.sh ia32"
        """
        self.dtsReportFolder = self.setLogsPath()
        
        # compile source code
        os.chdir("/home/patchWorkOrg/compilation")
        if args.targets is not None:
            self.compile_target(args.targets)
        else:
            self.compile_target(self.compileTargets)

        # copy dpdk source code to dts/dep foldera
        os.system("rm -rf *")
        os.chdir(self.basePath)
        
        return True
        

#################################################################################
if __name__ == "__main__":
    for dpdk_file in os.listdir(share_folder):
        if dpdk_file.startswith("dpdk"):
            if not os.path.exists("/home/patchWorkOrg/compilation"):
                os.makedirs("/home/patchWorkOrg/compilation")
            os.system("rm -rf /home/patchWorkOrg/compilation/*")
            tar_cmd = "tar zxvf %s/%s -C /home/patchWorkOrg/compilation" % (share_folder, dpdk_file)
            os.system(tar_cmd)
            if not os.path.exists("/home/patchWorkOrg/compilation/.git"):
                os.makedirs("/home/patchWorkOrg/compilation/.git")
            compiler = Compilation("/home/patchWorkOrg")
            print "#########Compiling %s ################" %dpdk_file
            compiler.compileDpdk() 

            logFile = open(share_folder+ os.sep +"info.txt")
            patch = logFile.read().strip()
            logFile.close()
            patch_result_file = "patch_" + patch
            dpdk_result_file = dpdk_file.split(".")[0]
            os_result_folder = "/home/DPDK/patch_build_result/%s/%s/%s" %(patch_result_file, dpdk_result_file, args.os)
            src_path = "/home/patchWorkOrg/reports/" + patch_result_file
            if os.path.exists(os_result_folder) == False:
                os.makedirs(os_result_folder)
            mv_cmd = "mv %s/* %s" %(src_path, os_result_folder)
            get_sys_config(src_path)
            os.system(mv_cmd)

    

 

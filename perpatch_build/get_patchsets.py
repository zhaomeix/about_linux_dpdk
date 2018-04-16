# -*- coding:utf-8 -*-
#######################################################################
import os
import shutil
import sys
import re
import time
import requests
import pexpect
#import mailReport
import queryCase
from sgmllib import SGMLParser
import logging

os.sys.path.append( os.path.dirname(__file__) + os.sep + "..") 
from parseError import *
from baseReporter import *

reload(sys)
sys.setdefaultencoding('utf-8')

debugMode = 0
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

#################################################################################
#################################################################################
# do html format text filter
class GetIdList(SGMLParser):
    def reset(self):
        self.IDlist = []
        self.flag = False
        self.getdata = False
        self.tr = 0
        self.td = 0
        self.th = 0
        self.keyWd = ""
        SGMLParser.reset(self)
        
    def start_tr(self, attrs):
        self.tr = 1
    
    def end_tr(self):
        self.tr = 0
    
    def start_td(self, attrs):
        self.td = 1        
            
    def end_td(self):
        self.td = 0

    def start_th(self, attrs):
        self.th = 1
               
    def end_th(self):
        self.th = 0

    def handle_data(self, text):
        if self.tr == 1 and self.th == 1 and self.td == 0 :
            if text == "State": 
                self.keyWd = 1
        
        if self.td == 1 and self.keyWd == 1:
            self.IDlist.append(text)
            self.keyWd = 0
                    
    def printID(self):
        for i in self.IDlist:
            printLog(i)

#################################################################################
#################################################################################
#################################################################################
class Patchwork():
    '''
    
    '''

    #################################################################################
    def __init__(self, basePath):
        # patches folder
        self.basePath = basePath
        self.patchesPath = basePath + os.sep + "patches" 
        self.patchListDict = {}

    #################################################################################
    def setMessageID(self, messageID):
        retMessageID = messageID
        patNo = r'(\d+-\d+-)(\d+)'
        foundResult = re.findall( patNo, messageID)
        if len(foundResult) > 0:
            retMessageID = foundResult[0][0] + "%03d"%int(foundResult[0][1])
            
        return retMessageID
    
    #################################################################################
    def getPatchPath(self):
        return self.patchesPath

    #################################################################################
    '''
    fetch out the newest patchwork id
    '''
    def getNewPatchWorkID(self):
        '''
        get the git server newest commit id
        '''
        
        patternNewCommitID = "patch_row:(\d+)"
        url='http://www.dpdk.org/dev/patchwork/project/dpdk/list/?page=1'
        for i in range(10):
            try:
                r = requests.get(url)
                time.sleep(1)
                break
            except Exception,e:
                print "error: %s" % str(e)
                if i <= 9:
                    time.sleep(10)
                    continue
                else:
                    print "Retry {} times, but still can't access the url, can't get the git server newest commit id. please check it.".format(i)
                    return 0
        
        patchWorkID = re.findall( patternNewCommitID, r.content, re.MULTILINE)
        if len(patchWorkID) > 0:
            sorted_patchWorkID = sorted(map(eval,patchWorkID), reverse=True)
            #printLog(patchWorkID[0])
            print "patchWorkID is {}".format(patchWorkID)
            if int(patchWorkID[0]) > sorted_patchWorkID[0]:
                newest_ID = patchWorkID[0]
            else:
                newest_ID = str(sorted_patchWorkID[0])
            print "Get the newest patch id in dpdk.org is {}".format(newest_ID)
            printLog(newest_ID)
            #rePatchWorkID = int(patchWorkID[0])
            rePatchWorkID = int(newest_ID)
        else:
            rePatchWorkID = 0

        # check if the id is the newest one
        cnt = 0
        while cnt < 100:
            url = "http://dpdk.org/dev/patchwork/patch/" + str(cnt+rePatchWorkID) + "/mbox/"
            try:
                r = requests.get(url)
                if r.status_code != 200:# if return code is not success flag, quit loop 
                    rePatchWorkID += ( cnt - 1)
                    break
                cnt += 1
            except Exception,e:
                print "error: %s" % str(e)
                rePatchWorkID = 0
                break

        return rePatchWorkID

    #################################################################################
    def getSubmitState(self,patchID):
        '''
        get submit patch's state
        '''
        url='http://dpdk.org/dev/patchwork/patch/'+str(patchID) + '/'
        try:
            r = requests.get(url)
            time.sleep(1)
        except Exception,e:
            print "error: %s" % str(e)
            return ""
    
        lister = GetIdList()
        lister.feed(r.content)
        state = "".join(lister.IDlist)
        printLog(state)
        
        return state
    
    #################################################################################
    def checkBeginPatchID(self,beginID,endID):
        printLog("")
        patMessageID  = r'Message-Id: <([0-9-]+)-git-send-email-.*@.*>'
        patSubject    = r'(?<=Subject:).+?(?=From:)'
        patPatchset   = r'.*\[.*\/(\d+)\].*'
        
        retBeginID = beginID
        # check latest effective id
        url='http://dpdk.org/dev/patchwork/patch/'+str(beginID) + '/mbox/'
        for i in range(5):
            try:
                r = requests.get(url)
                time.sleep(1)
                break
            except Exception,e:
                print "error: %s" % str(e)
                if i <= 4:
                    time.sleep(10)
                    continue
                else:
                    print "Retry {} times, but still can't access the url, please check it.".format(i)
                    return retBeginID
        # if patchwork is empty
        if 'content-disposition' not in r.headers:
            return retBeginID
        # get patch message id
        foundResult = re.findall( patMessageID, r.content, re.MULTILINE)
        # if it is not matched
        if len(foundResult) == 0:
            return retBeginID
        messageID = "".join(foundResult)

        # mail subject
        subject = re.sub("\n","","".join(re.findall(patSubject, r.content, re.S)))
        #subject = re.sub( "\[dpdk-dev.*\]", "", subject)
        # get patch set count
        foundResult = re.findall(patPatchset, subject, re.MULTILINE)
        if len(foundResult)>0:
            patchset    = int("".join(foundResult))
            patchsetKey = "-".join(messageID.split("-")[:2])
            for cnt in reversed(range( beginID + 1 - patchset, beginID + 1)):
                url='http://dpdk.org/dev/patchwork/patch/'+str(cnt) + '/mbox/'
                try:
                    r = requests.get(url)
                    time.sleep(1)
                except Exception,e:
                    print "error: %s" % str(e)
                    continue
                # if patchwork is empty
                if 'content-disposition' not in r.headers:
                    break
                # get patch message id
                foundResult = re.findall(patMessageID, r.content,re.MULTILINE)
                if len(foundResult) == 0:
                    break
                patchsetKeyTmp = "-".join("".join(foundResult).split("-")[:2])
                if patchsetKeyTmp != patchsetKey:
                    break
                retBeginID = cnt
        
        printLog("reset begin ID: %d"%retBeginID)
        return retBeginID 
    
    #################################################################################
    def checkEndPatchID(self,beginID,endID):
        '''
        search first integrated patchset
        '''
        printLog("")
        patMessageID  = r'Message-Id: <([0-9-]+)-git-send-email-.*@.*>'
        patSubject    = r'(?<=Subject:).+?(?=From:)'
        patPatchset   = r'.*\[.*\/(\d+)\].*'
        retEndID = endID
        for cnt in reversed(range(beginID,endID+1)):
            url='http://dpdk.org/dev/patchwork/patch/'+str(cnt) + '/mbox/'
            printLog(url)
            try:
                r = requests.get(url)
                time.sleep(1)
            except Exception,e:
                print "error: %s" % str(e)
                continue
            # if patchwork is empty
            if 'content-disposition' not in r.headers:
                continue
            # get patch message id
            foundResult = re.findall(patMessageID, r.content,re.MULTILINE)
            # if it is not matched, give up left
            if len(foundResult) == 0:
                retEndID = cnt
                break
            messageID = "".join(foundResult)        
            
            # mail subject
            subject = re.sub("\n","","".join(re.findall(patSubject, r.content, re.S)))
            # get patch set count
            foundResult = re.findall(patPatchset, subject, re.MULTILINE)
            if len(foundResult)<=0:
                retEndID = cnt
                break
            else:
                patchset = int("".join(foundResult))
                patchsetCnt = 0
                patchsetKey = "-".join(messageID.split("-")[:2])
                for cnt2 in reversed(range( cnt + 1 - patchset, cnt + 1)):
                    url='http://dpdk.org/dev/patchwork/patch/'+str(cnt2) + '/mbox/'
                    try:
                        r = requests.get(url)
                        time.sleep(1)
                    except Exception,e:
                        print "error: %s" % str(e)
                        continue
                    # if patchwork is empty
                    if 'content-disposition' not in r.headers:
                        break
                    # get patch message id
                    foundResult = re.findall(patMessageID, r.content,re.MULTILINE)
                    # if it is not matched, give up this patch
                    retEndID = cnt2
                    if len(foundResult) == 0:
                        break
                    patchsetKeyTmp = "-".join("".join(foundResult).split("-")[:2])
                    if patchsetKeyTmp == patchsetKey:
                        patchsetCnt += 1
                    else:
                        break
    
                if patchsetCnt == patchset:
                    retEndID = cnt
                break
        
        printLog("reset end ID: %d"%retEndID)
        return retEndID 
    
    #################################################################################
    def prePatching(self, inBeginID, inEndID, codeServer):
        '''
        pull down patch info and patch file
        '''
        printLog("")
        patSubmitterMail = "From: (.*)"
        patSubmitTime = "Date: (.*)"
        patSubmitComment = r'(?<=Date:).+?(?=[-]{3})'
        patMessageIDExd = r'([0-9-]+)-git-send-email-.*'
        patMessageID = r'Message-Id: <(.*)@.*>'
        patSubject = r'(?<=Subject:).+?(?=From:)'
        patPatchset = r'.*\[.*\/(\d+)\,?.*\].*'
        messgeIdPattern1 = r'(.*-.*)-\d+-git-send-email-(.*)'
        messgeIdPattern2 = r'.*\.(.*)\.git.(.*)'
        messgeIdPattern3 = r'(.*\..*)-\d+-(.*)'

        self.beginID = self.checkBeginPatchID(inBeginID, inEndID)
        self.endID   = self.checkEndPatchID(inBeginID, inEndID)
        printLog("reset %d -- %d"%(self.beginID, self.endID))
        
        if self.beginID > self.endID:
            return False
        patchesDict = dict()
        for cnt in range(self.beginID, self.endID+1):
            url='http://dpdk.org/dev/patchwork/patch/{}/mbox/'.format(str(cnt))
            printLog("url:  %s"%url)
            try:
                r = requests.get(url)
                time.sleep(1)
            except Exception,e:
                print "can't access patch {}, error: {}".format(str(cnt), str(e))
                continue
                    
            # if patchwork is empty
            if 'content-disposition' not in r.headers:
                continue
            # get patch message id
            findMessageID = re.findall(patMessageID, r.content,re.MULTILINE)
            # if it is not matched, give up this patch
            if len(findMessageID) == 0:
                continue
            else:
                # mail subject
                subject = re.sub("\n","","".join(re.findall(patSubject, r.content, re.S)))
                # message id
                messageID = "".join(findMessageID)
                # get patch set count
                findPatchset = re.findall(patPatchset, subject, re.MULTILINE)
                if len(findPatchset)==0:
                    patchset = "1"
                else:        
                    patchset = "".join(findPatchset)
            findMail = re.findall(patSubmitterMail, r.content,re.MULTILINE)
            if len(findMail) == 0:
                continue
            submitterMail = "".join(findMail[0])

            findTime= re.findall(patSubmitTime, r.content,re.MULTILINE)
            if len(findTime) == 0:
                continue
            submitTime = "".join(findTime)
            
            patchID = str(cnt)

            findComment = re.findall(patSubmitComment, r.content, re.S)
            if len(findComment) == 0:
                continue       

            submitComment = "".join(findComment).replace(submitTime,"")
            # make commit message format
            # PatchWork ID: <9999>
            patchWorkID = "PatchWork ID: {}".format(patchID)
            # comment to update
            gitComment = os.linesep.join([patchWorkID,submitComment])
            
            # fetch out the submitter's commit patch, store it as a git patch file
            #url='http://dpdk.org/dev/patchwork/patch/'+str(cnt)+'/raw/'
            #url='http://dpdk.org/dev/patchwork/patch/{}/mbox/'.format(str(cnt))
            url='http://dpdk.org/dev/patchwork/patch/{}/raw/'.format(str(cnt))
            try:
                raw_content = requests.get(url)
                time.sleep(1)
            except Exception,e:
                print "error: %s" % str(e)
                continue
            
            # if patchwork is empty
            if 'content-disposition' not in raw_content.headers:
                continue

            patchName= raw_content.headers['content-disposition'].split('=')[1]
            patchID = str(cnt)

            patchesDict[patchName] = raw_content.content
            
            #with open(self.patchesPath  + os.sep + patchName, "wb") as code:
            #    code.write(r.content)

            self.patchListDict.setdefault(messageID,[]).append(patchset)
            self.patchListDict.setdefault(messageID,[]).append(patchID)
            self.patchListDict.setdefault(messageID,[]).append(patchName)
            self.patchListDict.setdefault(messageID,[]).append(submitterMail)
            self.patchListDict.setdefault(messageID,[]).append(submitTime)
            self.patchListDict.setdefault(messageID,[]).append(gitComment)
            self.patchListDict.setdefault(messageID,[]).append(subject)

        patchsetGrp = dict()
        patchKeyList = sorted(self.patchListDict.keys())
        patchCount = len(patchKeyList) 
        firstPatchID = 0
        lastPatchID  = 0
        
        patchset = dict()
        for cnt in range(0, patchCount):
            messageID = patchKeyList[cnt]
            printLog( "*"*100)
            printLog("$$$$$$$$$$$$$$$ patching %s"%messageID)
            patchSet = int(self.patchListDict[messageID][0])
            printLog("%d"%patchSet)
            patchID = int(self.patchListDict[messageID][1])
            printLog("%s"%patchID)
            patchName = self.patchListDict[messageID][2]
            printLog(patchName)
            submitterMail = self.patchListDict[messageID][3]
            printLog(submitterMail)
            submitTime = self.patchListDict[messageID][4]
            printLog(submitTime)
            submitComment = self.patchListDict[messageID][5]
            printLog(submitComment)
            subject = self.patchListDict[messageID][6]
            printLog(subject)
            
            if patchName != "" and submitterMail != "" and submitTime != "" and submitComment != "":
                patchset[patchName] = self.patchListDict[messageID]
                if firstPatchID == 0 and lastPatchID == 0: 
                    firstPatchID = patchID
                    lastPatchID  = patchID
                else:
                    firstPatchID = min(firstPatchID, patchID)
                    lastPatchID  = max(lastPatchID, patchID)
    
                if patchSet > 1:
                    for pattern in [messgeIdPattern1, messgeIdPattern2, messgeIdPattern3]:
                        foundResult = re.findall(pattern, messageID)
                        if len(foundResult) != 0:
                            break
                    if len(foundResult) > 0 and cnt < patchCount-1:
                        nextMessageID = "".join(patchKeyList[cnt+1])
                        if nextMessageID.find(foundResult[0][0]) != -1 and nextMessageID.find(foundResult[0][0]) != -1:
                            continue
                
                patchsetGrp["%d-%d"%(firstPatchID, lastPatchID)] = patchset
                patchset = dict()
                firstPatchID = 0
                lastPatchID  = 0 
   
        for patchSetID in sorted(patchsetGrp.keys()):
            if os.path.exists(self.patchesPath + os.sep + patchSetID) == False:
                os.makedirs(self.patchesPath + os.sep + patchSetID)
            with open(self.patchesPath + os.sep +patchSetID + os.sep + "patchsetInfo.txt", "wb") as pi:
                pi.write(str(patchsetGrp[patchSetID]))
            for patch in patchesDict.keys():
                if patch in patchsetGrp[patchSetID].keys():
                    with open(self.patchesPath + os.sep + patchSetID + os.sep + patch, "wb") as code:
                        code.write(patchesDict[patch])
            codeServer.makeGitPatchWorkBranch(patchSetID)
            codeServer.switchGitMasterBranch()
            codeServer.recordExecutionLog(patchSetID)
            codeServer.getMasterCommitID()


        printLog(sorted(self.patchListDict.keys()))
        return True


################################################################################################
#
################################################################################################
class codeServer():
    '''
    '''
    
    #################################################################################
    def __init__(self, basePath):
        # dpdk source code
        self.basePath = basePath
        self.dpdkPath = basePath + os.sep + "dpdk" 
        self.curMasterCID = ""
        self.beginID = 0
        self.endID = 0
        self.switchGitMasterBranch()

    #################################################################################
    def getGitFirstPatchWorkID(self):
        patPatchWorkID = "patchworkID:(\d+)-+(\d+).*"
        os.chdir(self.dpdkPath)
        handle = os.popen("git log -1 --pretty=short")
        gitLog = handle.read()
        handle.close()
        
        patchWorkID = re.findall(patPatchWorkID, gitLog, re.MULTILINE)
        printLog("%s"%patchWorkID)
        if len(patchWorkID) > 0:
            patchWorkNo = int(patchWorkID[0][1])
        else:
            patchWorkNo = 0

        return  patchWorkNo
    
    #################################################################################
    def getLastValidationId(self):
        # check current branch, switch to master branch
        self.switchGitMasterBranch()
        # get the last time update patchwork ID to do next job,
        gitPatchID = self.getGitFirstPatchWorkID()
        
        return gitPatchID
    

    #################################################################################
    def recordExecutionLog(self, patchset):    
        '''
        After running full validation, record patching info
        '''
        os.chdir(self.dpdkPath)
        curTime = time.localtime()
        curTimeStr = " %04d%02d%02d-%02d:%02d"%(curTime.tm_year,curTime.tm_mon,curTime.tm_mday,curTime.tm_hour,curTime.tm_min)
        comments = "patchworkID:%s"%(patchset)
        os.system("echo "  + comments + curTimeStr + ">> " + self.dpdkPath + os.sep + "branches.log")
        # update commit
        os.system("git add branches.log")
        os.system("git commit -m  \""  + comments + "\"")
        # user setting
        sendPexpect("git push  git@10.240.176.250:" + self.dpdkPath,
                    ["Are you sure you want to continue connecting","git@10.240.176.250's password:"],
                    ["yes","tester"])

    #################################################################################
    def getCommitID(self):
        # get commit ID
        handle = os.popen("git  log -1")
        firstLog = handle.read()
        handle.close()
        commitIdPat    = r'(?<=commit ).+?(?=Author:)'
        commitID = re.findall(commitIdPat, firstLog,re.S)
        
        return "".join(commitID)[:-1]

    #################################################################################
    def getMasterCommitID(self):    
        '''
        before running full validation, record last time commit ID
        '''
        os.chdir(self.dpdkPath)
        
        # remember old commit ID
        self.switchGitMasterBranch()
        self.curMasterCID = self.getCommitID()
    
    #################################################################################
    def updateDdpkBranch(self):
        os.chdir(self.dpdkPath)
        lockFile = self.dpdkPath + os.sep + ".git" + os.sep + "index.lock"
        if os.path.exists(lockFile):
            os.remove(lockFile)
        os.system("git checkout -f dpdk")
        os.system("git clean -fd")
        os.system("git checkout -B dpdk dpdk/master")
        os.system("git pull")
        commitID = self.getCommitID()
        printLog("commitID = %s"%commitID)
        
        return "".join(commitID)

    #################################################################################
    def updateNextBranch(self):
        os.chdir(self.dpdkPath)
        lockFile = self.dpdkPath + os.sep + ".git" + os.sep + "index.lock"
        if os.path.exists(lockFile):
            os.remove(lockFile)
        os.system("git checkout -f rel_16_07")
        os.system("git clean -fd")
        os.system("git checkout -B rel_16_07 dpdk-next-net/rel_16_07")
        os.system("git pull")
        commitID = self.getCommitID()
        printLog("commitID = %s"%commitID)

        return "".join(commitID)

    #################################################################################

    #################################################################################
    def makeTempBranch(self):
        os.chdir(self.dpdkPath)
        os.system("git clean -fd")
        os.system("git checkout -f dpdk")
        os.system("git branch -D" + " temp")
        os.system("git checkout -B " + " temp")
    
    #################################################################################
    def makeTempBranch2(self):
        os.chdir(self.dpdkPath)
        os.system("git clean -fd")
        os.system("git checkout -f rel_16_07")
        os.system("git branch -D" + " temp")
        os.system("git checkout -B " + " temp")
    
    #################################################################################
    def makeGitPatchWorkBranch(self, patchset):
        os.chdir(self.dpdkPath)
        os.system("git branch -m temp " + " patchwork-%s"%patchset)

    #################################################################################
    def makeBaselineBranch(self, branch):
        os.chdir(self.dpdkPath)
        os.system("git branch -m temp " + " %s"%branch)

    #################################################################################
    def switchGitMasterBranch(self):
        printLog("switchGitMasterBranch......")
        os.chdir(self.dpdkPath)
        pattern = "^\* master"
        handle = os.popen("git branch") 
        out = handle.read()
        handle.close()
        printLog("%s"%out)
        matchGr = re.findall(pattern, out,re.MULTILINE)
        if len(matchGr) == 0:
            handle = os.popen("git checkout -f master")
            handle.close()
            if self.curMasterCID != "":
                os.system("git reset --hard " + "%s"%self.curMasterCID)
        else:
            printLog(matchGr)

    #################################################################################
    def switchToBranch(self, patchset):
        branchName = patchset#"patchwork-%s"%patchset
        printLog("switch to branch patchwork-%s ......"%branchName)
        os.chdir(self.dpdkPath)
        pattern = "^\* %s"%branchName
        handle = os.popen("git branch") 
        out = handle.read()
        handle.close()
        printLog("%s"%out)
        matchGr = re.findall(pattern, out,re.MULTILINE)
        if len(matchGr) == 0:
            handle = os.popen("git checkout -f %s"%branchName)
            handle.close()
        else:
            printLog(matchGr)

    #################################################################################
    def download_dpdk(self, compilePath):
        '''
        git clone patched source
        '''
        printLog("enter dpdk source downloading.....")
        # check if pack branch is on patchwork branch
        os.chdir(self.dpdkPath)
        handle = os.popen("git branch") 
        out = handle.read()
        handle.close()
        if len(re.findall("\* master", out, re.M)) > 0:
            printLog("Current on master branch, quit the following process")
            return False

        # prepare dpdk source code
        os.chdir(self.basePath)
        os.system("rm -fr " + compilePath  + os.sep + "*")
        os.system("rm -fr " + compilePath  + os.sep + ".git*")
        handle = os.popen("git clone " + self.dpdkPath + " " + compilePath) 
        out = handle.read()
        handle.close()
        if out != "":
            print "git clone failed"
            return False

        printLog("compilation source code ready!")

        return True    

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
        
        self.compileLog = dict()

    #################################################################################
    def getCompilePath(self):
        return self.compilePath

    #################################################################################
    def setLogsPath(self, path):
        self.logsPath = path

    #################################################################################
    def getCommitID(self):
        # get commit ID
        handle = os.popen("git  log -1")
        firstLog = handle.read()
        handle.close()
        commitIdPat    = r'(?<=commit ).+?(?=Author:)'
        commitID = re.findall(commitIdPat, firstLog,re.S)
        
        return "".join(commitID)[:-1]

    #################################################################################
    def compileDpdkDoc(self, baseline):
        '''
        make a full doc compilation
        '''
        printLog("enter making doc compilation.....")
        dtsReportFolder = self.logsPath

        # compile doc
        os.chdir(self.compilePath)
        
        result = queryCase.get_required_cases(branch=self.branchName, commit=baseline)
        
        if 'doc' in result:
            curCommitID = self.getCommitID()
            
            handle = os.popen("make doc" + " > " + dtsReportFolder + "/doc_compile" + ".log 2>&1")
            out = handle.read()
            if handle.close() != None:
                makeDocStatus = "FAILED"
            else:
                makeDocStatus = "SUCCESS"

            os.system("git reset --hard " + "%s"%curCommitID)
            os.system("git clean -fd")
            
            self.compileLog["doc"] = makeDocStatus
        else:
            self.compileLog["doc"] = "unknown"

        return True

    #################################################################################
    def compileDpdk(self):
        '''
        make a full compilation
        '''
        printLog("enter compilation checking.....")
        base_config = ["sed -i -e 's/PMD_PCAP=n$/PMD_PCAP=y/' config/common_base","sed -i -e 's/IGB_UIO=y$/IGB_UIO=n/' config/common_base","sed -i -e 's/KNI_KMOD=y$/KNI_KMOD=n/' config/common_base"]
        debug_config = "sed -i -e 's/DEBUG=n$/DEBUG=y/' config/common_base"
        shared_config = "sed -i -e 's/SHARED_LIB=n$/SHARED_LIB=y/' config/common_base"
        combine_config = "sed -i -e 's/COMBINE_LIBS=n$/COMBINE_LIBS=y/' config/base"
        icc_64_config = "source /opt/intel/bin/iccvars.sh intel64"
        icc_32_config = "source /opt/intel/bin/iccvars.sh ia32"

        dtsReportFolder = self.logsPath
        
        # compile source code
        os.chdir(self.compilePath)
        curCommitID = self.getCommitID()
        for target in self.compileTargets:
            target_name = target
            os.system("export RTE_SDK=`pwd`")
            if target.startswith("x86_64-native-linuxapp-gcc"):
                target = "x86_64-native-linuxapp-gcc"
            os.system("rm -rf " + target)
            os.system("export RTE_TARGET=%s" %target)
            printLog("make %s compiling....."%target_name)
            if target != "i686-native-linuxapp-gcc":
                for _ in base_config:
                    os.system(_)
            if "debug" in target_name:
                os.system(debug_config)
            if "shared" in target_name:
                os.system(shared_config)
            if "combine" in target_name:
                os.system(combine_config)
            if target_name == "x86_64-native-linuxapp-icc":
                os.system(icc_64_config)
            if target_name == "i686-native-linuxapp-icc":
                os.system(icc_32_config)

            os.system("make -j install T=" + target + " > " + dtsReportFolder + "/compile_" + target_name + ".log 2>&1")
            os.system("echo KG,kernal:3.11.10,gcc:4.8.3"  + " > " + dtsReportFolder + "/system.log")
            os.system("git reset --hard " + "%s"%curCommitID)
            os.system("git clean -fd")
            os.system("rm -fr " + "%s"%target)
        
        # record compile log
        for target in self.compileTargets:
            logPath = dtsReportFolder + os.sep +"compile_" + target + ".log"
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

        # copy dpdk source code to dts/dep folder
        os.chdir(self.basePath)
        
        return True
        
################################################################################################
#
################################################################################################
class Tester():
    '''
    '''
    
    #################################################################################
    def __init__(self, basePath):
        self.basePath = basePath
        # DTS folder
        self.dtsPath = basePath + os.sep + "dts"

    #################################################################################
    def getDtsPath(self):
        return self.dtsPath

    #################################################################################
    def copyDpdkTar(self):
        os.chdir(self.basePath)
        os.system("tar -czvf " + self.dtsPath  + os.sep + "dep" + os.sep + "dpdk.tar.gz  dpdk  --exclude=*.git > /dev/null")

    #################################################################################
    def saveDtsResults(self, dstPath):
        printLog("make a result copy")
        dstPath = dstPath + os.sep + "output"
        if os.path.exists(dstPath):
            shutil.rmtree(dstPath)
        shutil.copytree(self.dtsPath + os.sep + "output", dstPath)

    #################################################################################
    def runDTS(self):
        printLog("")
        os.chdir(self.dtsPath)
        os.system("rm -fr " + self.dtsPath + os.sep + "output/*")
        handle = os.popen(self.dtsPath + os.sep + "dts") 
        out = handle.read()
        handle.close()
        dtsLogPath = self.dtsPath + os.sep + "output/dts.log" 
        if os.path.exists(dtsLogPath) == False:
            printLog("[%s] is not exist"%dtsLogPath)
            return False
        
        fp = open(dtsLogPath,'r')
        content = "".join(fp.readlines())
        pattern= "DTS ended"
        foundResult = re.findall(pattern, content, re.MULTILINE)
        if len(foundResult) == 0:
            print "not found!"
            #return False

    #################################################################################
    def runSingleTestcases(self, testcaseList):
        printLog("")
        os.chdir(self.dtsPath)
        os.system("rm -fr " + self.dtsPath + os.sep + "output/*")
        
        test = ""
        for testcase in testcaseList:
            test += " -t test_%s"%testcase
        cmd = self.dtsPath + os.sep + "dts " + test
        print cmd
        handle = os.popen(cmd)
        out = handle.read()
        handle.close()
        dtsLogPath = self.dtsPath + os.sep + "output/dts.log" 
        if os.path.exists(dtsLogPath) == False:
            printLog("[%s] is not exist"%dtsLogPath)
            return False
        
        fp = open(dtsLogPath,'r')
        content = "".join(fp.readlines())
        pattern= "DTS ended"
        foundResult = re.findall(pattern, content, re.MULTILINE)
        if len(foundResult) == 0:
            print "not found!"
            #return False

################################################################################################
#
################################################################################################
class PatchworkReport():
    '''
    '''
    #################################################################################
    def __init__(self, basePath):
        self.basePath = basePath
        # report history folder
        self.reportsPath = basePath + os.sep + "reports"
        self.reportsForSendPath = basePath + os.sep + "reportsForSend"
        self.curReportFolder = ""
        self.curReportFolderName = ""
        self.mailSubject = ""

    #################################################################################
    def logStatus(self):
        handle = os.popen("date")
        out = handle.read()
        handle.close()
        logPath = self.reportsPath + os.sep +"runningLog.log"
        if os.path.exists(logPath):
            fp = open(logPath,'r')
            out = "".join(["".join(fp.readlines()),out])
            fp.close()

        fp = open(logPath,'w')
        fp.writelines(out)
        fp.close()

    #################################################################################
    def getReportsPath(self):
        return self.reportsPath

    #################################################################################
    def setReportPath(self, folder):
        self.curReportFolder = folder

    #################################################################################
    def copyToReadyDst(self):
        printLog("copy to ready reports folder")
        if os.path.exists(self.reportsForSendPath) == False:
            os.makedirs(self.reportsForSendPath)

        if self.curReportFolder.startswith("baseline"):
            dirName = self.curReportFolder
        else:
            dirName = "_".join(self.curReportFolder.split("_")[:-1])

        patchDirs = os.listdir(self.reportsForSendPath)
        for item in patchDirs:
            if item.startswith(dirName):
                dstPath = self.reportsForSendPath + os.sep + item
                shutil.rmtree(dstPath)
            
        dstPath = self.reportsForSendPath + os.sep + self.curReportFolder
        if os.path.exists(dstPath):
            shutil.rmtree(dstPath)
        shutil.copytree(self.reportsPath + os.sep + self.curReportFolder, dstPath)

    #################################################################################
    def setCurSubmitInfo(self, submitInfo):
        pattern = "<(.*)>"
        if debugMode == 1:
            submitInfo["mail"] = ["yongjiex.gu@intel.com"]
        else:
            submitInfo["mail"] = "".join(re.findall(pattern, submitInfo["submitter"]))

        self.submitInfo = submitInfo

    #################################################################################
    def getSubmitInfo(self):
        return self.submitInfo

    #################################################################################
    def sendReport(self):
        printLog("sending report......")
        report = PatchWorkReport()
        report.setDir(self.reportsPath + os.sep + self.curReportFolder)
        #report.set_submitter_info(self.getSubmitInfo())
        #envInfo = {"kernel": "3.11.10-301.fc20.x86_64", 
        #            "gcc" : "gcc_x86-64", 
        #            "os": "fedora",
        #            "nic": "niantic", 
        #            "testType": "auto"}
        #report.set_environment_info(envInfo)
        report.send_report()

################################################################################################
#
################################################################################################
class PatchWorkValidation():
    '''
    '''
    #################################################################################
    def __init__(self, workPath, **kwargs):
        # basic folder
        self.basePath = workPath 
        self.basePath + os.sep + "patches"
        self.curPatchworkPath = ""
        self.curPatchPath = ""
        self.baselinePath = ""
        
        self.patchId =  kwargs["patchId"]
        self.patchwork = Patchwork(self.basePath)
        self.codeServer = codeServer(self.basePath)
        self.compiler = Compilation(self.basePath)
        self.tester = Tester(self.basePath)
        self.reporter = PatchworkReport(self.basePath)
        self.reportsPath = self.reporter.getReportsPath()

        self.dtsExecCntFile = self.reportsPath + os.sep + "dtsExecCntFile.log"
        
        self.reboot = False

    #################################################################################
    def makePatchworkReportsFolder(self, name, baseCommitID):
        printLog("make reports history folder......")
        
        self.curReportFolderName = "patch_" + "%s"%name + "_" +  baseCommitID
        self.curPatchworkPath = self.reportsPath + os.sep + self.curReportFolderName 
        if os.path.exists(self.curPatchworkPath) == False:
            os.makedirs(self.curPatchworkPath)
        
        self.curPatchPath = self.curPatchworkPath + os.sep + "patches"
        if os.path.exists(self.curPatchPath) == False:
            os.makedirs(self.curPatchPath)

    #################################################################################
    def recordSubmitInfo(self, submitInfo):
        submitInfoFile = self.curPatchworkPath + os.sep + "submitInfo.txt"
        print submitInfoFile
        if os.path.exists(submitInfoFile):
            os.remove(submitInfoFile)
        
        content = ""
        for item in submitInfo.keys():
            value = submitInfo[item]
            if value == None or len(value) == 0:
                continue
            
            valueStr = ""
            if isinstance(value, tuple) or isinstance(value, list):
                for subItem in value:
                    valueStr += "<val>%s"%subItem
            else:
                valueStr = value
            content += "".join(["%s::"%item, "<val>%s"%valueStr , os.linesep])
        
        with open(submitInfoFile, "wb") as submitInfo:
            submitInfo.write(content)

    ######################################################################
    def recordEnvInfo(self):
        envInfoFile = self.curPatchworkPath + os.sep + "envInfo.txt"
        print envInfoFile
        envInfo = {"kernel": "3.11.10-301.fc20.x86_64", 
                    "gcc" : "gcc_x86-64, 4.8.3", 
                    "os": "fedora",
                    "nic": "niantic", 
                    "testType": "Function",
                    "icc" : "16.0.2"}
        
        if os.path.exists(envInfoFile):
            os.remove(envInfoFile)

        content = ""
        content += "gcc::<val>%s"%envInfo["gcc"] + os.linesep
        content += "kernel::<val>%s"%envInfo["kernel"] + os.linesep
        content += "os::<val>%s"%envInfo["os"] + os.linesep
        content += "testType::<val>%s"%("auto") + os.linesep
        content += "nic::<val>%s"%("niantic") + os.linesep
        content += "icc::<val>%s"%envInfo["icc"] + os.linesep
        with open(envInfoFile, "wb") as info:
            info.write(content)

    #################################################################################        
    def makeCheckPatchErrorInfo(self, checkPatchDict):
        content = ""
        for item in checkPatchDict.keys():
            content += "".join(["%s: "%item, os.linesep, "%s"%checkPatchDict[item], os.linesep])
        checkPatchErrFile = "".join([self.curPatchworkPath, os.sep, "patches", os.sep, "checkPatchError.txt"])
        with open(checkPatchErrFile, "wb") as errorInfo:
            errorInfo.write(content)

    #################################################################################        
    def makePatchErrorInfo(self, malformedPatch):
        content = ""
        for item in malformedPatch.keys():
            content += "".join(["%s: "%item, os.linesep, "%s"%malformedPatch[item] , os.linesep])
        patchErrFile = "".join([self.curPatchworkPath, os.sep, 
                                "patches", os.sep, 
                                "patchError.txt"])
        with open(patchErrFile, "wb") as errorInfo:
            errorInfo.write(content)

    #################################################################################
    def makeResultsErrorLog(self, path):
        errorParser = ReportErrorLog(path)
        errorParser.makeReport()

    #################################################################################
    def run_baseline_testing(self, baseCommitID):
        baselineFile = self.reportsPath + os.sep + "baseline.log"
        if os.path.exists(baselineFile):
            with open(baselineFile, "rb") as info:
                preBaseCommitId = info.read()
        else:
            preBaseCommitId = 0

        if baseCommitID != preBaseCommitId:
            print "---------------------------------------------------------------------"
            print "---------------------------------------------------------------------"
            print "---------------------------------------------------------------------"
            print "pre baseline: [%s]"%preBaseCommitId
            
            self.baselinePath = self.reportsPath + os.sep + "baseline_%s"%baseCommitID 
            if os.path.exists(self.baselinePath) == False:
                os.makedirs(self.baselinePath)
            
            self.codeServer.getMasterCommitID()
            self.codeServer.makeTempBranch()
            self.codeServer.download_dpdk(self.compiler.getCompilePath())
            self.compiler.setLogsPath(self.baselinePath)
            self.compiler.compileDpdkDoc(baseCommitID)
            self.compiler.compileDpdk()


            curTime = time.localtime()
            curTimeStr = " %04d%02d%02d-%02d:%02d"%(curTime.tm_year,curTime.tm_mon,curTime.tm_mday,curTime.tm_hour,curTime.tm_min)
            
            patchInfo = dict()
            patchInfo["subject"] = "  "
            # user setting
            patchInfo["submitter"] = "yongjiex <yongjiex.gu@intel.com>"
            patchInfo["date"] = curTimeStr
            patchInfo["patchworkId"] = "  baseline-validation"
            patchInfo["patchlist"] = ""
            patchInfo["baseline"] = baseCommitID
            
            self.curPatchworkPath = self.baselinePath
            self.recordSubmitInfo(patchInfo)
            self.recordEnvInfo()
            self.reporter.setCurSubmitInfo(patchInfo)
            
            self.codeServer.makeBaselineBranch("baseline_%s"%baseCommitID)
            self.codeServer.switchGitMasterBranch()
            
            self.reporter.setReportPath(os.path.basename(self.baselinePath))
            self.reporter.copyToReadyDst()
            self.reporter.sendReport()
            with open(baselineFile, "wb") as info:
                info.write(baseCommitID)
            #self.checkRebootStatus()


    #################################################################################
    def execute(self):
        beginID, endID = self.patchId
        # get the last time update patchwork ID to do next job,
        gitPatchID = self.codeServer.getLastValidationId()
        print '##############'
        print gitPatchID
        if endID == 0:
            endID = self.patchwork.getNewPatchWorkID()
        print "New patchwork id in dpdk.org is {}".format(endID)
        printLog("last time patch %d"%gitPatchID)
        if beginID <= gitPatchID:
            beginID = gitPatchID + 1
        elif gitPatchID >= endID or gitPatchID <=0:
            print "input ID is too old!!!"
            return

        printLog("input %d -- %d"%(beginID, endID))
        self.reporter.logStatus()
        self.patchwork.prePatching(beginID,endID,self.codeServer)

#################################################################################
if __name__ == "__main__":
    # stop crab service
    #  crontab -e
    # * * * * * /home/patchWorkOrg/autoPatch/patchwork.sh auto
    #initLog()
    
    # make start/end patchWorkID
    if sys.argv[1] != "auto":
        intputBeginID= int(sys.argv[1])
        intputEndID = int(sys.argv[2])
    else:
        intputBeginID = 0
        intputEndID = 0
    
    autoValidation = PatchWorkValidation("/home/patchWorkOrg", 
                                         patchId=(intputBeginID, intputEndID))
    autoValidation.execute()

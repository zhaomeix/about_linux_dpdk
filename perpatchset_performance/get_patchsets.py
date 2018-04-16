# -*- coding:utf-8 -*-
import os
import shutil
import sys
import re
import time
import requests
import pexpect
from sgmllib import SGMLParser
import logging

os.sys.path.append( os.path.dirname(__file__) + os.sep + "..") 

reload(sys)
sys.setdefaultencoding('utf-8')

debugMode = 0

def printLog(inputStr=''):
    global debugMode
    if debugMode == 0:
        return
    
    if inputStr != '' :
        if debugMode == 2:
            logging.info(inputStr)
        else:
            print inputStr

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
    

class Patchwork():
    '''
    
    '''

    def __init__(self, basePath):
        # patches folder
        self.basePath = basePath
        self.patchesPath = "{}/patches".format(self.basePath) 
        self.patchListDict = {}

    def setMessageID(self, messageID):
        retMessageID = messageID
        patNo = r'(\d+-\d+-)(\d+)'
        foundResult = re.findall( patNo, messageID)
        if len(foundResult) > 0:
            retMessageID = foundResult[0][0] + "%03d"%int(foundResult[0][1])
            
        return retMessageID
    
    def getPatchPath(self):
        return self.patchesPath

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

    def checkBeginPatchID(self,beginID,endID):
        patMessageID = r'Message-Id: <([0-9-]+)-git-send-email-.*@.*>'
        patSubject = r'(?<=Subject:).+?(?=From:)'
        patPatchset = r'.*\[.*\/(\d+)\].*'

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
        patPatchset = r'.*\[.*\/(\d+)\].*'

        messgeIdPattern1 = r'(.*-.*)-\d+-git-send-email-(.*)'
        messgeIdPattern2 = r'.*\.(.*)\.git.(.*)'
        messgeIdPattern3 = r'(.*\..*)-\d+-(.*)'

        self.beginID = self.checkBeginPatchID(inBeginID, inEndID)
        self.endID = self.checkEndPatchID(inBeginID, inEndID)
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
            findMessgeID = re.findall(patMessageID, r.content,re.MULTILINE)
            # if it is not matched, give up this patch
            if len(findMessgeID) == 0:
                continue
            else:
                # mail subject
                subject = re.sub("\n","","".join(re.findall(patSubject, r.content, re.S)))
                messageID = "".join(findMessgeID)
                findPatchset = re.findall(patPatchset, subject, re.MULTILINE)
                if len(findPatchset)==0:
                    patch_num = "1"
                else:
                    patch_num = "".join(findPatchset)
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
                r = requests.get(url)
                time.sleep(1)
            except Exception,e:
                print "error: %s" % str(e)
                continue
            
            # if patchwork is empty
            if 'content-disposition' not in r.headers:
                continue
            
            patchName= r.headers['content-disposition'].split('=')[1]
            patchID = "%d"%cnt

            patchesDict[patchName] = r.content
            
            #with open(self.patchesPath  + os.sep + patchName, "wb") as code:
            #    code.write(r.content)

            self.patchListDict.setdefault(messageID,[]).append(patch_num)
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
        for cnt in range( 0, patchCount):
            messageID = patchKeyList[cnt]
            printLog( "*"*100)
            printLog("$$$$$$$$$$$$$$$    patching %s"%messageID)
            patchSet_num = int(self.patchListDict[messageID][0])
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
    
                if patchSet_num > 1:
                    for pattern in [messgeIdPattern1, messgeIdPattern2, messgeIdPattern3]:
                        foundResult = re.findall(pattern, messageID)
                        if len(foundResult) != 0:
                            break
                    if len(foundResult) > 0 and cnt < patchCount - 1:
                        nextMessageID = "".join(patchKeyList[cnt + 1])
                        print "nextMessageID is {}, foundResult is {}".format(nextMessageID, foundResult)
                        if (nextMessageID.find(foundResult[0][0]) != -1 and nextMessageID.find(foundResult[0][0]) != -1):
                            continue

                patchsetGrp["%d-%d"%(firstPatchID, lastPatchID)] = patchset
                patchset = dict()
                firstPatchID = 0
                lastPatchID  = 0 

        for patchSetID in sorted(patchsetGrp.keys()):
            if os.path.exists(self.patchesPath + os.sep + patchSetID) == False:
                os.makedirs(self.patchesPath + os.sep + patchSetID)
            with open("{}/{}/patchsetInfo.txt".format(self.patchesPath,patchSetID), "wb") as pi:
                pi.write(str(patchsetGrp[patchSetID]))
            for patch in patchesDict.keys():
                if patch in patchsetGrp[patchSetID].keys():
                    with open("{}/{}/{}".format(self.patchesPath,patchSetID,patch), "wb") as code:
                        code.write(patchesDict[patch])
            #codeServer.makeGitPatchWorkBranch(patchSetID)
            codeServer.switchGitMasterBranch()
            codeServer.recordExecutionLog(patchSetID)
            #codeServer.getMasterCommitID()

        printLog(sorted(self.patchListDict.keys()))
        return True


class codeServer():
    '''
    '''
    
    def __init__(self, basePath):
        # dpdk source code
        self.basePath = basePath
        self.dpdkPath = "{}/dpdk".format(basePath) 
        self.curMasterCID = ""
        self.beginID = 0
        self.endID = 0
        self.switchGitMasterBranch()

    def getGitFirstPatchWorkID(self):
        patPatchWorkID = "patchworkID:(\d+)-+(\d+).*"
        os.chdir(self.dpdkPath)
        handle = os.popen("git log -1 --pretty=short")
        gitLog = handle.read()
        handle.close()
        
        patchWorkID = re.findall(patPatchWorkID, gitLog, re.MULTILINE)
        printLog(patchWorkID)
        if len(patchWorkID) > 0:
            patchWorkNo = int(patchWorkID[0][1])
        else:
            patchWorkNo = 0

        return  patchWorkNo
    
    def getLastValidationId(self):
        # check current branch, switch to master branch
        self.switchGitMasterBranch()
        # get the last time update patchwork ID to do next job,
        gitPatchID = self.getGitFirstPatchWorkID()
        
        return gitPatchID
    
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
        sendPexpect("git push git@10.240.176.190:" + self.dpdkPath,
                    ["Are you sure you want to continue connecting","git@10.240.176.190's password:"],
                    ["yes","tester"])

    def getCommitID(self):
        # get commit ID
        handle = os.popen("git log -1")
        firstLog = handle.read()
        handle.close()
        commitIdPat = r'(?<=commit ).+?(?=Author:)'
        commitID = re.findall(commitIdPat, firstLog,re.S)
        
        return "".join(commitID)[:-1]

    def getMasterCommitID(self):    
        '''
        before running full validation, record last time commit ID
        '''
        os.chdir(self.dpdkPath)
        
        # remember old commit ID
        self.switchGitMasterBranch()
        self.curMasterCID = self.getCommitID()

    def makeGitPatchWorkBranch(self, patchset):
        os.chdir(self.dpdkPath)
        os.system("git branch -m temp " + " patchwork-%s"%patchset)

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


class PatchWorkValidation():
    '''
    '''
    def __init__(self, workPath, **kwargs):
        # basic folder
        self.basePath = workPath 
 
        self.patchId = kwargs["patchId"]
        self.patchwork = Patchwork(self.basePath)
        self.codeServer = codeServer(self.basePath)

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
        self.patchwork.prePatching(beginID,endID,self.codeServer)

if __name__ == "__main__":
    # make start/end patchWorkID
    if sys.argv[1] != "auto":
        intputBeginID= int(sys.argv[1])
        intputEndID = int(sys.argv[2])
    else:
        intputBeginID = 0
        intputEndID = 0
    
    autoValidation = PatchWorkValidation("/home/jenkins", patchId=(intputBeginID, intputEndID))
    autoValidation.execute()

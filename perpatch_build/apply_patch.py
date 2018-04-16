# -*- coding: utf-8 -*-
#######################################################################
import os
import shutil
import sys
import re
import time
import pexpect
import logging
import json

os.sys.path.append(os.path.dirname(__file__) + os.sep + "..") 
from parseError import *
from baseReporter import *

reload(sys)
sys.setdefaultencoding('utf-8')

debugMode = 1
REPOES = ["dpdk", "dpdk-next-net", "dpdk-next-crypto", "dpdk-next-virtio", "dpdk-next-eventdev"]

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
def GetPatchInfo(patch):
    patchSet = int(patch[0])
    patchID = int(patch[1])
    patchName = patch[2]
    submitterMail = patch[3]
    submitTime = patch[4]
    submitComment = patch[5]
    subject = patch[6]
    return patchSet, patchID, patchName, submitterMail, submitTime, submitComment, subject


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
    def getPatchPath(self):
        return self.patchesPath


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
    def getCommitID(self):
        # get commit ID
        handle = os.popen("git  log -1")
        firstLog = handle.read()
        handle.close()
        commitIdPat    = r'(?<=commit ).+?(?=Author:)'
        commitID = re.findall(commitIdPat, firstLog,re.S)
        
        return "".join(commitID)[:-1]

    #################################################################################
    def updateBranch_GetCommitID(self, repo):
        os.chdir(self.dpdkPath)
        lockFile = self.dpdkPath + os.sep + ".git" + os.sep + "index.lock"
        if os.path.exists(lockFile):
            os.remove(lockFile)
        os.system("git checkout -f %s" % repo)
        os.system("git clean -fd")
        os.system("git checkout -B %s %s/master" % (repo, repo))
        os.system("git pull")
        commitID = self.getCommitID()
        printLog("commitID = %s"%commitID)
        
        return "".join(commitID)

    #################################################################################
    def makeTempBranch(self, repo):
        os.chdir(self.dpdkPath)
        os.system("git clean -fd")
        os.system("git checkout -f %s" % repo)
        os.system("git branch -D" + " temp")
        os.system("git checkout -B " + " temp")
    
    #################################################################################
    def switchGitMasterBranch(self):
        printLog("switchGitMasterBranch......")
        os.chdir(self.dpdkPath)
        pattern = "^\* master"
        handle = os.popen("git branch") 
        out = handle.read()
        handle.close()
        printLog(out)
        matchGr = re.findall(pattern, out,re.MULTILINE)
        if len(matchGr) == 0:
            handle = os.popen("git checkout -f master")
            handle.close()
            if self.curMasterCID != "":
                os.system("git reset --hard " + "%s"%self.curMasterCID)
        else:
            printLog(matchGr)


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
        self.reportsPath = "/home/DPDK/patch_build_result"
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
    def setCurSubmitInfo(self, submitInfo):
        pattern = "<(.*)>"
        if debugMode == 1:
            if re.findall(pattern, submitInfo["submitter"]):
                #submitInfo["mail"] = ["fangfangx.wei@intel.com"]
                submitInfo["mail"] = "".join(re.findall(pattern, submitInfo["submitter"]))
            else:
                submitInfo["mail"] = submitInfo["submitter"]
        else:
            if re.findall(pattern, submitInfo["submitter"]):
                submitInfo["mail"] = "".join(re.findall(pattern, submitInfo["submitter"]))
            else:
                submitInfo["mail"] = submitInfo["submitter"]

        self.submitInfo = submitInfo

################################################################################################
#
################################################################################################
class PatchWorkValidation():
    '''
    '''
    #################################################################################
    def __init__(self, workPath, endId):
        # basic folder
        self.basePath = workPath 
        self.basePath + os.sep + "patches"
        self.curPatchworkPath = ""
        self.curPatchPath = ""
        self.baselinePath = ""
        
        #self.patchId =  kwargs["patchId"]
        self.endId = endId
        self.patchwork = Patchwork(self.basePath)
        self.codeServer = codeServer(self.basePath)
        #self.compiler = Compilation(self.basePath)
        self.reporter = PatchworkReport(self.basePath)
        self.reportsPath = self.reporter.getReportsPath()

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
    def makeDpdkFolder(self, patchNo, name, baseCommitID):
        dpdk_name = "dpdk%d" %patchNo
        dpdkFolderName = self.curPatchworkPath + os.sep + dpdk_name
        if os.path.exists(dpdkFolderName) == False:
            os.makedirs(dpdkFolderName)

    #################################################################################
    def recordSubmitInfo(self, submitInfo):
        submitInfoFile = self.curPatchworkPath + os.sep + "submitInfo.txt"
        print submitInfoFile
        if os.path.exists(submitInfoFile):
            os.remove(submitInfoFile)
        
        content = ""
        for item, value in submitInfo.iteritems():
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


    #################################################################################
    def recordTarMatchIdInfo(self, matchInfo):
        matchInfoFile = self.curPatchworkPath + os.sep + "TarMatchIdInfo.txt"
        print matchInfoFile
        if os.path.exists(matchInfoFile):
            os.remove(matchInfoFile)
        json.dump(matchInfo, open(matchInfoFile, 'w'))

    #################################################################################        
    def makePatchErrorInfo(self, malformedPatch):
        patchErrFile = "".join([self.curPatchworkPath, os.sep, 
                                "patches", os.sep, 
                                "patchError.txt"])
        if os.path.exists(patchErrFile):
            os.remove(patchErrFile)
        json.dump(malformedPatch, open(patchErrFile, 'w'))
        os.system("cp -r %s /home/patchWorkOrg/patchwork/applyPatch.log" %patchErrFile)

    #################################################################################
    def apply_patch_in_repo(self, patchset, patchsetInfo, repo, CommitID, baseCommitID):
        """
        apply patch into repo, if patch success, push to git server and generate dpdk tar files, or generate
        dictionary malPatchPerRepo which may contain the malformedpatch information.
        """
        printLog("Start patch file........")
        malPatchPerRepo = {}
        patchNo = 0
        matchInfo = {}

        first_patch = patchsetInfo[sorted(patchsetInfo.keys())[0]]
        first_patchSet, first_patchID, first_patchName, first_submitterMail, first_submitTime, first_submitComment, first_subject = GetPatchInfo(first_patch)

        for item in sorted(patchsetInfo.keys()):
            patchNo += 1
            patch = patchsetInfo[item]
            patchSet, patchID, patchName, submitterMail, submitTime, submitComment, subject = GetPatchInfo(patch)

            if patchNo == 1:
                matchInfo["dpdk%s"%patchNo] = "Patch%s-%s" % (patchID, patchID)
            else:
                matchInfo["dpdk%s"%patchNo] = "Patch%s-%s" % (first_patchID, patchID)
            # Get the abosulte path of patchfile.
            patchSetPath = self.PatchesPath+ os.sep + patchset
            patchFile = patchSetPath + os.sep + patchName

            self.makeDpdkFolder(patchNo, patchset, baseCommitID)

            os.chdir(self.codeServer.dpdkPath)
            cmd = "patch -d " + self.codeServer.dpdkPath + " -p1 <" + patchFile
            printLog(cmd)
            outStream = os.popen(cmd)
            patchingLog = outStream.read()
            printLog(patchingLog)
            outStream.close()
            malformedError = "malformed patch"
            hunkFailError = "FAILED at"
            patchResult = "success"
            if malformedError in patchingLog:
                patchResult = "malformed patch"
            elif hunkFailError in patchingLog:
                patchResult = "hunk failed"

            if patchResult != "success":
                printLog("apply patch error!")
                malPatchPerRepo[patchID] = patchingLog
            else:
                # push to git server
                printLog("Start generate tar files...........")
                os.chdir(self.codeServer.dpdkPath)
                print "dpdkpath is %s" % self.codeServer.dpdkPath
                os.system("git add --all")
                os.system("git commit -m \"" + "test" + "\"")
                sendPexpect("git push ")
                submitCommentExd = submitComment.replace("\"","")
                os.system("git commit --amend --author=\'" + submitterMail  + "\' --date=\'" + submitTime +"\' -m \""  + submitCommentExd+ "\"" )
                sendPexpect("git push ")

                #Copy the patched source to patchSetPath and then generate dpdk tar file.
                ##cp_cmd = "cp -r %s %s" %(self.codeServer.dpdkPath, patchSetPath)
                ##os.system(cp_cmd)
                ##os.chdir(patchSetPath)
                #os.system("mv dpdk %s" %patchName.split(".")[0])
                ##os.chdir(patchSetPath+ os.sep + 'dpdk')
                tar_cmd = "tar zcvf /home/DPDK/dpdk%d.tar.gz *" %patchNo
                os.system(tar_cmd)
                shutil.copy2("/home/DPDK/dpdk%d.tar.gz" %patchNo, self.curPatchPath)

            #Copy patch file into curPatchPath to backup.
            shutil.copy2(patchFile, self.curPatchPath)
        self.recordTarMatchIdInfo(matchInfo)

        return malPatchPerRepo


    #################################################################################
    def run_patchwork_validation(self, patchset, patchsetInfo, RepoCommitID, baseCommitID):
        malformedPatch = dict()
        print "---------------------------------------------------------------------"
        print "---------------------------------------------------------------------"

        #Write patchsetID and commitID into /home/DPDK/info.txt. This file will be used with compilation and report.
        dpdk_info = file("/home/DPDK/info.txt", "w+")
        dpdk_info.write(patchset + "_" + baseCommitID)
        dpdk_info.close()

        #Remove dpdk tar file which may be left after last build.
        os.system("rm -r /home/DPDK/dpdk*")

        #Try to apply patch files into repoes, if patch success then break, else continue to patch files to next repo
        for repo in REPOES:
            printLog("Try to apply patch into repo: %s......."%repo)
            #Make temp branch based on repo
            self.codeServer.makeTempBranch(repo)

            #Get current repo's commitID
            CommitID = RepoCommitID[repo]

            #Try to apply patch files into repo
            malPatchPerRepo = self.apply_patch_in_repo(patchset, patchsetInfo, repo, CommitID, baseCommitID) 

            if len(malPatchPerRepo) > 0:
                malformedPatch[repo] = malPatchPerRepo
            else:
                #if no patch file error, generate submitInfo.txt file
                for item, patch in patchsetInfo.iteritems():
                    patchSet, patchID, patchName, submitterMail, submitTime, submitComment, subject = GetPatchInfo(patch)

                    patchInfo = dict()
                    patchInfo["subject"] = re.sub( "\[dpdk-dev.*\]", "", subject)
                    patchInfo["submitter"] = submitterMail
                    patchInfo["date"] = submitTime
                    patchInfo["patchworkId"] = patchset
                    patchInfo["baseline"] = "Repo:%s, Branch:master, CommitID:%s" % (repo, CommitID)
                    self.reporter.setCurSubmitInfo(patchInfo)
                    self.recordSubmitInfo(patchInfo)
                    break
                break

        #if there are some malformed patch,generate /home/patchWorkOrg/patchwork/applyPatch.log file. 
        printLog("malformedPatch length is %s, it is %s"%(len(malformedPatch), malformedPatch))
        if len(malformedPatch) == len(REPOES):
            self.makePatchErrorInfo(malformedPatch)
            for item, patch in patchsetInfo.iteritems():
                patchSet, patchID, patchName, submitterMail, submitTime, submitComment, subject = GetPatchInfo(patch)

                patchInfo = dict()
                #patchInfo["subject"] = re.sub( "\[dpdk-dev.*\]", "", subject)
                patchInfo["subject"] = re.sub( "\[dpdk-dev", "[PATCH", subject)
                patchInfo["submitter"] = submitterMail
                patchInfo["date"] = submitTime
                patchInfo["patchworkId"] = patchset
                patchInfo["baseline"] = ""
                for malrepo, commitid in RepoCommitID.iteritems():
                    patchInfo["baseline"] += "Repo:%s, Branch:master, CommitID:%s;" % (malrepo, commitid)
                self.reporter.setCurSubmitInfo(patchInfo)
                self.recordSubmitInfo(patchInfo)
                break
        else:
            pass

    #################################################################################
    def execute(self):
        endId = self.endId
        if endId == 0:
            pass
        else:
            #Remove applyPatch.log which may be remained from last build.
            os.system("rm -rf /home/patchWorkOrg/patchwork/applyPatch.log")

            # get the last time update patchwork ID to do next job,
            print '##############'
            print endId
            beginId = endId + 1

            #Get the patchset which will be built this time.
            patchsets = os.listdir("/home/patchWorkOrg/patches")
            self.PatchesPath = self.patchwork.getPatchPath()
            patchsetId = ""
            if patchsets:
                for patchset in patchsets:
                    if patchset.startswith(str(beginId)):
                        patchsetId = patchset
                self.reporter.logStatus()

                print patchsetID
                if patchsetId:
                    print 'set patchID failed, please check download  patchset %d' % beginId
                #Get patchsetInfo which includes patchfilename, pasetfileId, Author, Time, Comments and etc.
                patchsetFile = open("/home/patchWorkOrg/patches/"+ patchsetId +"/patchsetInfo.txt")
                patchsetInfo = patchsetFile.read()
                patchsetFile.close()
                patchsetInfo = eval(patchsetInfo)
                if patchsetInfo != None and len(patchsetInfo) > 0:
                    #Check patch files format and style.
                    RepoCommitID = {repo:self.codeServer.updateBranch_GetCommitID(repo) for repo in REPOES}
                    baseCommitID = RepoCommitID["dpdk"]
                    self.makePatchworkReportsFolder(patchsetId, baseCommitID) 

                    #Update latest dpdk source about different repoes and get the latest commit ID.
                    #RepoCommitID = {repo:self.codeServer.updateBranch_GetCommitID(repo) for repo in REPOES}
                    #baseCommitID = RepoCommitID["dpdk"] 
                    #Apply patchset with per patch into repoes
                    self.run_patchwork_validation(patchsetId, patchsetInfo, RepoCommitID, baseCommitID)

                #Write this patchsetID into /home/DPDK/test.log
                logFile = file("/home/DPDK/test.log", "w+")
                logFile.write(patchsetId)
                logFile.close()
                cp_cmd = "cp /home/patchWorkOrg/patches/%s/patchsetInfo.txt /home/DPDK/patch_build_result/patch_%s_%s" %(patchsetId, patchsetId, baseCommitID)
                os.system(cp_cmd)
                patches_path = "/home/patchWorkOrg/patches/{}".format(patchsetId)
                for parent,dirnames,filenames in os.walk(patches_path):
                    for dirname in dirnames:
                        dir_path = os.path.join(parent,dirname)
                        os.system("rm -rf {}".format(dir_path))
                mv_cmd = "mv /home/patchWorkOrg/patches/%s /home/PatchSets" %patchsetId
                os.system(mv_cmd)
            else:
                with open("/home/patchWorkOrg/patchwork/applyPatch.log", "wb") as ap:
                    ap.write("no patch to test!")
            

#################################################################################
if __name__ == "__main__":
    endId = 0
    if os.path.exists("/home/DPDK/test.log"):
        logFile = open("/home/DPDK/test.log")
        patchsetID = logFile.read().strip()
        logFile.close()
        endId = int(patchsetID.split('-')[1])
    print endId
    # make start/end patchWorkID
   # if sys.argv[1] != "auto":
   #     intputBeginID= int(sys.argv[1])
   #     intputEndID = int(sys.argv[2])
   # else:
   #     intputBeginID = 0
   #     intputEndID = 0
   # 
    autoValidation = PatchWorkValidation("/home/patchWorkOrg", endId)
    autoValidation.execute()

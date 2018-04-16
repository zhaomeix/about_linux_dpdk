# BSD LICENSE
#
# Copyright(c) 2010-2017 Intel Corporation. All rights reserved.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#   * Neither the name of Intel Corporation nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# -*- coding: utf-8 -*-
import os
import sys
import time
import re
import shutil
import pexpect
import logging
import json
import argparse

reload(sys)
sys.setdefaultencoding('utf-8')

REPOES = ["dpdk", "dpdk-next-net", "dpdk-next-crypto", "dpdk-next-virtio",
          "dpdk-next-eventdev"]


def GetPatchInfo(patch):
    patchSet = int(patch[0])
    patchID = int(patch[1])
    patchName = patch[2]
    submitterMail = patch[3]
    submitTime = patch[4]
    submitComment = patch[5]
    subject = patch[6]
    return (patchSet, patchID, patchName, submitterMail, submitTime,
            submitComment, subject)


class PatchWorkValidation(object):
    '''
    You can get the path of test results, set submit
    '''

    def __init__(self, workPath, beginId, endId):
        self.share_folder = workPath
        self.beginId = beginId
        self.endId = endId

        self.curPatchworkPath = ""
        self.curPatchPath = ""
        self.curReportFolderName = ""
        self.reportsPath = "{}/patch_performance_result".format(self.share_folder)
        self.dpdkPath = "{}/dpdk".format(self.share_folder)
        self.patchesPath = "{}/patches".format(self.share_folder)
        self.patchListDict = {}
        self.curMasterCID = ""
        self.switchGitMasterBranch()

    def getCommitID(self):
        # get commit ID
        handle = os.popen("git log -1")
        firstLog = handle.read()
        handle.close()
        commitIdPat = r'(?<=commit ).+?(?=Author:)'
        commitID = re.findall(commitIdPat, firstLog, re.S)

        return "".join(commitID)[:-1]

    def updateBranch_GetCommitID(self, repo):
        os.chdir(self.dpdkPath)
        lockFile = "".join([self.dpdkPath, "/", ".git", "/", "index.lock"])
        if os.path.exists(lockFile):
            os.remove(lockFile)
        os.system("git checkout -f {}".format(repo))
        os.system("git clean -fd")
        os.system("git checkout -B {} {}/master".format(repo, repo))
        os.system("git pull")
        commitID = self.getCommitID()
        logging.info("commitID = {}".format(commitID))

        return "".join(commitID)

    def makeTempBranch(self, repo):
        os.chdir(self.dpdkPath)
        os.system("git clean -fd")
        os.system("git checkout -f {}".format(repo))
        os.system("git branch -D temp")
        os.system("git checkout -B temp")

    def switchGitMasterBranch(self):
        logging.info("switchGitMasterBranch......")
        os.chdir(self.dpdkPath)
        pattern = "^\* master"
        handle = os.popen("git branch")
        out = handle.read()
        handle.close()
        logging.info(out)
        matchGr = re.findall(pattern, out, re.MULTILINE)
        if len(matchGr) == 0:
            handle = os.popen("git checkout -f master")
            handle.close()
            if self.curMasterCID != "":
                os.system("git reset --hard {}".format(self.curMasterCID))
        else:
            logging.info(matchGr)

    def logStatus(self):
        handle = os.popen("date")
        out = handle.read()
        handle.close()
        logPath = self.reportsPath + os.sep + "runningLog.log"
        if os.path.exists(logPath):
            fp = open(logPath, 'r')
            out = "".join(["".join(fp.readlines()), out])
            fp.close()

        fp = open(logPath, 'w')
        fp.writelines(out)
        fp.close()

    def setCurSubmitInfo(self, submitInfo):
        pattern = "<(.*)>"
        if re.findall(pattern, submitInfo["submitter"]):
            submitInfo["mail"] = "".join(re.findall(pattern,
                                         submitInfo["submitter"]))
        else:
            submitInfo["mail"] = submitInfo["submitter"]

        self.submitInfo = submitInfo

    def makePatchworkReportsFolder(self, name, baseCommitID):
        logging.info("make reports history folder......")

        self.curReportFolderName = "patch_{}_{}".format(name, baseCommitID)
        self.curPatchworkPath = "".join([self.reportsPath, "/", self.curReportFolderName])
        if os.path.exists(self.curPatchworkPath) == False:
            os.makedirs(self.curPatchworkPath)
            os.makedirs(self.curPatchworkPath + os.sep + "performance_results")

        self.curPatchPath = self.curPatchworkPath + os.sep + "patches"
        if os.path.exists(self.curPatchPath) == False:
            os.makedirs(self.curPatchPath)

    def recordSubmitInfo(self, submitInfo):
        submitInfoFile = self.curPatchworkPath + os.sep + "submitInfo.txt"
        print submitInfoFile
        if os.path.exists(submitInfoFile):
            os.remove(submitInfoFile)

        content = ""
        for item, value in submitInfo.iteritems():
            if value is None or len(value) == 0:
                continue

            valueStr = ""
            if isinstance(value, tuple) or isinstance(value, list):
                for subItem in value:
                    valueStr += "<val>{}".format(subItem)
            else:
                valueStr = value
            content += "".join(["{}::".format(item),
                               "<val>{}".format(valueStr), os.linesep])

        with open(submitInfoFile, "wb") as submitInfo:
            submitInfo.write(content)

    def recordTarMatchIdInfo(self, matchInfo):
        matchInfoFile = self.curPatchworkPath + os.sep + "TarMatchIdInfo.txt"
        if os.path.exists(matchInfoFile):
            os.remove(matchInfoFile)
        json.dump(matchInfo, open(matchInfoFile, 'w'))

    def makePatchErrorInfo(self, malformedPatch):
        patchErrFile = "".join([self.curPatchworkPath, os.sep,
                                "patches", os.sep,
                                "patchError.txt"])
        if os.path.exists(patchErrFile):
            os.remove(patchErrFile)
        json.dump(malformedPatch, open(patchErrFile, 'w'))
        os.system("cp {} {}/applyPatch.log".format(patchErrFile, self.share_folder))

    def apply_patch_in_repo(self, patchset, patchsetInfo, repo, CommitID):
        """
        apply patch into repo, if patch success, push to git server and
        generate dpdk tar files, or generate dictionary malPatchPerRepo
        which may contain the malformedpatch information.
        """
        logging.info("Start patch file........")
        malPatchPerRepo = {}
        patchNo = 0
        matchInfo = {}

        first_patch = patchsetInfo[sorted(patchsetInfo.keys())[0]]
        (first_patchSet, first_patchID, first_patchName,
         first_submitterMail, first_submitTime,
         first_submitComment, first_subject) = GetPatchInfo(first_patch)

        for item in sorted(patchsetInfo.keys()):
            patchNo += 1
            patch = patchsetInfo[item]
            (patchSet, patchID, patchName, submitterMail, submitTime,
             submitComment, subject) = GetPatchInfo(patch)

            if patchNo == 1:
                matchInfo[patchNo] = "Patch%s-%s" % (patchID, patchID)
            else:
                matchInfo[patchNo] = "Patch%s-%s" % (first_patchID, patchID)

            # Get the abosulte path of patchfile.
            patchSetPath = self.patchesPath + os.sep + patchset
            patchFile = patchSetPath + os.sep + patchName

            os.chdir(self.dpdkPath)
            cmd = "patch -d {} -p1 < {}".format(self.dpdkPath,
                                                patchFile)
            logging.info(cmd)
            outStream = os.popen(cmd)
            patchingLog = outStream.read()
            logging.info(patchingLog)
            outStream.close()
            malformedError = "malformed patch"
            hunkFailError = "FAILED at"
            missFileError = "can't find file to patch at input"
            patchResult = "success"
            if malformedError in patchingLog:
                patchResult = "malformed patch"
            elif hunkFailError in patchingLog:
                patchResult = "hunk failed"
            elif missFileError in patchingLog:
                patchResult = "miss file"

            if patchResult != "success":
                logging.info("apply patch error!")
                malPatchPerRepo[patchID] = patchingLog

        # push to git server
        os.chdir(self.dpdkPath)
        os.system("git add --all")
        os.system("git commit -m \" test \"")
        submitCommentExd = submitComment.replace("\"", "")
        # os.system("git commit --amend --author=\'" + submitterMail +
        # "\' --date=\'" + submitTime + "\' -m \"" + submitCommentExd + "\"")
        commit_cmd = "git commit --amend --author=\'{}\' --date=\'{}\' \
                     -m \"{}\"".format(submitterMail, submitTime,
                                       submitCommentExd)
        os.system(commit_cmd)

        os.chdir(self.dpdkPath + "/../")
        tar_cmd = "tar zcvf {}/dpdk.tar.gz dpdk".format(share_folder)
        os.popen(tar_cmd)
        shutil.copy2("{}/dpdk.tar.gz".format(share_folder), self.curPatchPath)

        self.recordTarMatchIdInfo(matchInfo)

        # Copy patch file into curPatchPath to backup.
        shutil.copy2(patchFile, self.curPatchPath)

        return malPatchPerRepo

    def run_patchwork_validation(self, patchset, patchsetInfo, RepoCommitID,
                                 baseCommitID):
        malformedPatch = dict()

        # Write patchsetID and commitID into share_folder/info.txt.
        # This file include the patch about where to store test results.
        dpdk_info = file("{}/info.txt".format(share_folder), "w+")
        dpdk_info.write(patchset + "_" + baseCommitID)
        dpdk_info.close()

        # Remove dpdk tar file which may be left after last build.
        os.system("rm -rf {}/dpdk.tar.gz".format(share_folder))

        # Try to apply patch files into repoes, if patch success then break,
        # else continue to patch files to next repo
        repo = "dpdk"
        for item, patch in patchsetInfo.iteritems():
            patchSet, patchID, patchName, submitterMail, submitTime, \
             submitComment, subject = GetPatchInfo(patch)
            if re.search("net/", subject):
                repo = "dpdk-next-net"
            elif (re.search("crypto/", subject) or
                  re.search("cryptodev:", subject)):
                repo = "dpdk-next-crypto"
            elif re.search("event/", subject):
                repo = "dpdk-next-eventdev"
            elif re.search("vfio:", subject) or re.search("vfio/", subject):
                repo = "dpdk-next-virtio"

        self.makeTempBranch(repo)
        CommitID = RepoCommitID[repo]
        malPatchPerRepo = self.apply_patch_in_repo(patchset, patchsetInfo,
                                                   repo, CommitID)
        logging.info("malPatchPerRepo is {}".format(malPatchPerRepo))

        if len(malPatchPerRepo) > 0:
            malformedPatch[repo] = malPatchPerRepo
            self.makePatchErrorInfo(malformedPatch)
        for item, patch in patchsetInfo.iteritems():
            (patchSet, patchID, patchName, submitterMail, submitTime,
             submitComment, subject) = GetPatchInfo(patch)
            patchInfo = dict()
            patchInfo["subject"] = re.sub("\[dpdk-dev.*\]", "", subject)
            patchInfo["submitter"] = submitterMail
            patchInfo["date"] = submitTime
            patchInfo["patchworkId"] = patchset
            patchInfo["baseline"] = "Repo:{}, Branch:master, \
                                     CommitID:{}".format(repo, CommitID)
            self.setCurSubmitInfo(patchInfo)
            self.recordSubmitInfo(patchInfo)
            break

    def execute(self):
        patchsetId = "".join([self.beginId, '-', self.endId])
        # Remove applyPatch.log which may be remained from last build.
        os.system("rm -rf {}/applyPatch.log".format(self.share_folder))

        if os.path.exists("{}/{}".format(self.patchesPath, patchsetId)) is False:
            patchsets = os.listdir(self.patchesPath)
            patchsetId = ""
            if patchsets:
                for patchset in patchsets:
                    if patchset.startswith(str(self.beginId)):
                        patchsetId = patchset

        if patchsetId == "":
            print "patchset {}-{} not exist".format(self.beginId, self.endId)
            with open("{}/applyPatch.log".format(self.share_folder), "wb") as ap:
                ap.write("no patch to test!")

        else:
            self.logStatus()
            logging.info("Need to be tested patchset is {}".format(patchsetId))

            # Get patchsetInfo which includes patchfilename, pasetfileId,
            # Author, Time, Comments and etc.
            file_path = "{}/{}/patchsetInfo.txt".format(self.patchesPath, patchsetId)
            patchsetFile = open(file_path)
            patchsetInfo = patchsetFile.read()
            patchsetFile.close()
            patchsetInfo = eval(patchsetInfo)
            if patchsetInfo is not None and len(patchsetInfo) > 0:
                RepoCommitID = {repo: self.updateBranch_GetCommitID(
                                repo) for repo in REPOES}
                baseCommitID = RepoCommitID["dpdk"]
                self.makePatchworkReportsFolder(patchsetId, baseCommitID)
                # Apply patchset with per patch into repoes
                self.run_patchwork_validation(patchsetId, patchsetInfo,
                                              RepoCommitID, baseCommitID)

            # backup patchset files and patchset information
            cp_cmd = "cp {} {}/patch_{}_{}".format(file_path, self.reportsPath,
                                                   patchsetId, baseCommitID)
            os.system(cp_cmd)
            patcheset_path = "{}/{}".format(self.patchesPath, patchsetId)
            for parent, dirnames, filenames in os.walk(patcheset_path):
                for dirname in dirnames:
                    dir_path = os.path.join(parent, dirname)
                    os.system("rm -rf {}".format(dir_path))
            mv_cmd = "mv {} {}/PatchSets".format(patcheset_path, self.share_folder)
            os.system(mv_cmd)


if __name__ == "__main__":
    """
    argument:
    -p: the full path about share folder
    -b: the first patch id in one patch set
    -e: the last patch id in one patch set
    usage:
    python apply_patchset.py -p the/full/path/of/share/folder -b xxx -e xxx
    """

    parser = argparse.ArgumentParser(description='apply patch set to correct dpdk repo')
    parser.add_argument('-p', '--path', help='the absolute path of share folder')
    parser.add_argument('-b', '--begin-id', default=0, type=str, help='the begin id of the patch set')
    parser.add_argument('-e', '--end-id', default=0, type=str, help='the end id of the patch set')

    args = parser.parse_args()

    InputBeginID = args.begin_id
    InputEndID = args.end_id
    share_folder = args.path

    autoValidation = PatchWorkValidation(share_folder, InputBeginID, InputBeginID)
    autoValidation.execute()

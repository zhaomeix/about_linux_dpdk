# -*- coding:utf-8 -*-
import os
import sys
import re
import time
import argparse
import requests

reload(sys)
sys.setdefaultencoding('utf-8')


class Patchwork(object):
    '''
    Get patch set information and patch set content from dpdk.org.
    Download patch set information and stored it into patchsetInfo.txt.
    Download patches of patchset, and stored them into the directory which
    named with patchwork ID such as '27512-27514'.
    27512 is the first patch ID, 27514 is the last patch ID in this patchset.
    '''

    def __init__(self, workPath, **kwargs):
        self.basePath = workPath
        self.patchId = kwargs["patchId"]
        self.patchListDict = {}

    def GetNewestPatchWorkID(self):
        '''
        get the newest patch id in dpdk.org
        '''

        PatternNewCommitID = "patch_row:(\d+)"
        url = 'http://www.dpdk.org/dev/patchwork/project/dpdk/list/?page=1'
        try:
            r = requests.get(url)
            time.sleep(1)
        except Exception, e:
            print "Can't access dpdk.org, the error is {}".format(str(e))
            return 0

        PatchWorkID = re.findall(PatternNewCommitID, r.content, re.MULTILINE)
        if len(PatchWorkID) > 0:
            # n=[ int(i) for i in l ]
            Sorted_PatchWorkID = Sorted(PatchWorkID, reverse=True)
            if PatchWorkID[0] > Sorted_PatchWorkID[0]:
                newest_ID = PatchWorkID[0]
            else:
                newest_ID = Sorted_PatchWorkID[0]
            print "Get the newest patch id in dpdk.org is {}".format(newest_ID)
            rePatchWorkID = int(newest_ID)
        else:
            rePatchWorkID = 0

        # check if the patch id is the newest one
        cnt = 0
        while cnt < 100:
            url = "http://dpdk.org/dev/patchwork/patch/{}/mbox/".\
                  format(str(cnt+rePatchWorkID))
            try:
                r = requests.get(url)
                # if return code is not success flag, quit loop
                if r.status_code != 200:
                    rePatchWorkID += (cnt - 1)
                    break
                cnt += 1
            except Exception, e:
                print "error: {}".format(str(e))
                rePatchWorkID = 0
                break

        return rePatchWorkID

    def GetPatchSet(self, BeginID, EndID):
        '''
        Download patch set information and patch set files
        '''

        patSubmitterMail = r'From: (.*)'
        patSubmitTime = r'Date: (.*)'
        patSubmitComment = r'(?<=Date:).+?(?=[-]{3})'
        patMessageIDExd = r'([0-9-]+)-git-send-email-.*'
        patMessageID = r'Message-Id: <(.*)>'
        patSubject = r'(?<=Subject:).+?(?=From:)'
        patPatchset = r'.*\[.*\/(\d+)\,?.*\].*'

        messgeIdPattern1 = r'(.*-.*)-\d+-git-send-email-(.*)'
        messgeIdPattern2 = r'.*\.(.*)\.git.(.*)'
        messgeIdPattern3 = r'(.*\..*)-\d+-(.*)'

        self.beginID = BeginID
        self.endID = EndID
        if self.beginID > self.endID:
            print "Begin patch ID is larger than the end patch ID"
            return False

        PatchesDict = dict()
        for cnt in range(self.beginID, self.endID + 1):
            url = 'http://dpdk.org/dev/patchwork/patch/{}/mbox/'.\
                  format(str(cnt))
            try:
                r = requests.get(url)
                time.sleep(1)
            except Exception, e:
                print "can't access patch {}, error: {}".\
                      format(str(cnt), str(e))
                continue

            # if patchwork is empty, get the next patch info
            if 'content-disposition' not in r.headers:
                continue

            # get patch message id
            findMessgeID = re.findall(patMessageID, r.content, re.MULTILINE)
            if len(findMessgeID) == 0:
                continue
            else:
                # mail subject
                subject = re.sub("\n", "", "".join(re.findall(patSubject,
                                 r.content, re.S)))
                messageID = "".join(findMessgeID)
                # get patch number per patch set
                findPatchset = re.findall(patPatchset, subject, re.MULTILINE)
                if len(findPatchset) == 0:
                    patch_num = "1"
                else:
                    patch_num = "".join(findPatchset)
            findMail = re.findall(patSubmitterMail, r.content, re.MULTILINE)
            if len(findMail) == 0:
                continue
            submitterMail = "".join(findMail[0])

            findTime = re.findall(patSubmitTime, r.content, re.MULTILINE)
            if len(findTime) == 0:
                continue
            submitTime = "".join(findTime)

            patchID = str(cnt)

            findComment = re.findall(patSubmitComment, r.content, re.S)
            if len(findComment) == 0:
                continue

            submitComment = "".join(findComment).replace(submitTime, "")
            patchWorkID = "PatchWork ID: {}".format(patchID)
            gitComment = os.linesep.join([patchWorkID, submitComment])

            # fetch out the submitter's patch content, store it as a patch file
            url = 'http://dpdk.org/dev/patchwork/patch/{}/raw'.format(str(cnt))
            try:
                raw = requests.get(url)
                time.sleep(1)
            except Exception, e:
                print "error: {}".format(str(e))
                continue

            if 'content-disposition' not in raw.headers:
                continue
            patchName = raw.headers['content-disposition'].split('=')[1]
            patchID = str(cnt)

            PatchesDict[patchName] = raw.content

            self.patchListDict.setdefault(messageID, []).append(patch_num)
            self.patchListDict.setdefault(messageID, []).append(patchID)
            self.patchListDict.setdefault(messageID, []).append(patchName)
            self.patchListDict.setdefault(messageID, []).append(submitterMail)
            self.patchListDict.setdefault(messageID, []).append(submitTime)
            self.patchListDict.setdefault(messageID, []).append(gitComment)
            self.patchListDict.setdefault(messageID, []).append(subject)

        patchsetGrp = dict()
        patchKeyList = sorted(self.patchListDict.keys())
        patchCount = len(patchKeyList)
        firstPatchID = 0
        lastPatchID = 0

        patchset = dict()
        for cnt in range(patchCount):
            messageID = patchKeyList[cnt]
            patchSet_num = int(self.patchListDict[messageID][0])
            patchID = int(self.patchListDict[messageID][1])
            patchName = self.patchListDict[messageID][2]
            submitterMail = self.patchListDict[messageID][3]
            submitTime = self.patchListDict[messageID][4]
            submitComment = self.patchListDict[messageID][5]
            subject = self.patchListDict[messageID][6]
            if (patchName != "" and submitterMail != "" and
                    submitTime != "" and submitComment != ""):
                patchset[patchName] = self.patchListDict[messageID]
                if firstPatchID == 0 and lastPatchID == 0:
                    firstPatchID = patchID
                    lastPatchID = patchID
                else:
                    firstPatchID = min(firstPatchID, patchID)
                    lastPatchID = max(lastPatchID, patchID)

                if patchSet_num > 1:
                    for pattern in [messgeIdPattern1, messgeIdPattern2,
                                    messgeIdPattern3]:
                        foundResult = re.findall(pattern, messageID)
                        if len(foundResult) != 0:
                            break
                    if len(foundResult) > 0 and cnt < patchCount - 1:
                        nextMessageID = "".join(patchKeyList[cnt + 1])
                        if (nextMessageID.find(foundResult[0][0]) != -1 and
                           nextMessageID.find(foundResult[0][0]) != -1):
                            continue

                patchsetGrp["{}-{}".format(firstPatchID, lastPatchID)] = patchset
                patchset = dict()
                firstPatchID = 0
                lastPatchID = 0

        for PatchSetID in sorted(patchsetGrp.keys()):
            if os.path.exists(self.basePath + os.sep + PatchSetID) == False:
                os.makedirs(self.basePath + os.sep + PatchSetID)
            with open(self.basePath + os.sep + PatchSetID + os.sep + "patchsetInfo.txt", "wb") as pi:
                pi.write(str(patchsetGrp[PatchSetID]))
            for patch in PatchesDict.keys():
                if patch in patchsetGrp[PatchSetID].keys():
                    with open(self.basePath + os.sep + PatchSetID + os.sep + patch, "wb") as code:
                        code.write(PatchesDict[patch])

        return True

    def execute(self):
        beginID, endID = self.patchId
        # If the given endID is 0, get the newest patch ID from dpdk.org as endID
        if endID == 0:
            endID = self.GetNewestPatchWorkID()

        self.GetPatchSet(beginID, endID)


if __name__ == "__main__":
    """
    Download patch set information and patch set files from dpdk.org
    Arguments:
    -p/--dst-path: the destination path where the downloaded patch set will be stored
    -b/--begin-id: the begin patchwork id of the patch set
    -e/--end-id: the end patchwork id of the patch set
    """

    parser = argparse.ArgumentParser(description='Get patch set from dpdk.org')
    parser.add_argument('-p', '--dst-path', type=str, help='the destination path where the downloaded patch set will be stored')
    parser.add_argument('-b', '--begin-id', default=0, type=int, help='the begin id of the patch set')
    parser.add_argument('-e', '--end-id', default=0, type=int, help='the end id of the patch set')

    args = parser.parse_args()

    InputBeginID = args.begin_id
    InputEndID = args.end_id

    if os.path.exists(args.dst_path):
        patchwork = Patchwork(args.dst_path, patchId=(InputBeginID, InputEndID))
        patchwork.execute()
    else:
        print "{} is not existed".format(args.dst_path)

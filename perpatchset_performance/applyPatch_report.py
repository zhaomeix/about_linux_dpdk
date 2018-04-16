# -*- coding:utf-8 -*-
import os
import re
import sys
import datetime
import string
import types
import exceptions
import json
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


share_folder = "/home/performance_ci"
report_folder = share_folder+ os.sep +"patch_build_result"


class PatchworkReport():
    def __init__(self):
        self.patchInfoDict = dict()
        self.patchsetID = ""
        self.patch_info = ""
        self.patchFolderName = ""
        self.compilation = dict()
        self.testStatus = "SUCCESS"

    def readInfo(self):
        patch_file = open(share_folder+ os.sep +"info.txt")
        #patch_file = open(share_folder+ os.sep +"i.txt")
        self.patch_info = patch_file.read().strip()
        patch_file.close()
    
    def getPatchsetID(self):
        self.patchsetID = self.patch_info.split("_")[0]
        return self.patchsetID

    def getPatchSetInfo(self):
        with open(report_folder + os.sep + self.patchFolderName + os.sep + "patchsetInfo.txt", "rb") as pi:
            patchInfo = pi.read()
        self.patchSetInfoDict = eval(patchInfo)
        return self.patchSetInfoDict

    def fetch_keys_values(self, content):
        retDict = dict()
        if content == "":
            return retDict
        patKey = "(.*)::(.*)"
        patValue = "<val>"
        
        result = re.findall(patKey, content, re.M)
        for item in result:
            key = item[0]
            value = item[1].split(patValue)[1:]
            if len(value) > 1:
                retDict[key] = value
            else:
                retDict[key] = "".join(value)

        return retDict

    def getPatchInfo(self):
        self.readInfo()
        self.patchFolderName = "patch_{}".format(self.patch_info)
        submitInfoFile = report_folder + os.sep + self.patchFolderName + os.sep + "submitInfo.txt"
        if os.path.exists(submitInfoFile):
            with open(submitInfoFile, "rb") as info:
                content = info.read()
                infoDict = self.fetch_keys_values(content)
            for item in infoDict.keys():
                self.patchInfoDict[item] = infoDict[item]
        patchSetID = self.getPatchsetID()
        self.patchInfoDict["patchsetID"] = patchSetID

    def make_content(self):
        self.getPatchInfo()
        content_dict = {}
        self.testStatus = "FAILURE"
        matchDict = json.load(open(report_folder + os.sep + self.patchFolderName + os.sep + "TarMatchIdInfo.txt", "r"))
        patch_error_dict = json.load(open(report_folder + os.sep + self.patchFolderName + os.sep + "patches" + os.sep + "patchError.txt", "r"))
        self.patchSetInfoDict = self.getPatchSetInfo()

        whole_patchsetID = matchDict[str(sorted(int(key) for key in matchDict.keys())[-1])]
        last_patchID = whole_patchsetID.split("-")[-1]

        #for dpdk in sorted(matchDict.keys()):
        content = ""

        content += "Test-Label: Intel-Performance-Testing" + os.linesep
        content += "Test-Status: {}\n".format(self.testStatus)
        content += "http://dpdk.org/patch/{}\n\n".format(last_patchID)
        content += "_apply patch file failure_\n\n"
        content += "Submitter: {}\n".format(self.patchInfoDict["submitter"])
        content += "Date: {}\n".format(self.patchInfoDict["date"])
        content += "DPDK git baseline: {}".format(self.patchInfoDict["baseline"].replace(";","\n                   "))
        content += os.linesep
 
        content += "Apply patch set {} failed:\n".format(whole_patchsetID)
        for repo, error_log in patch_error_dict.iteritems():
            for error_key, error_content in error_log.iteritems():
                content += "Repo: {}\n".format(repo)
                content += "{}:\n".format(error_key)
                content += error_log[error_key]
                content += os.linesep

        content += os.linesep + "DPDK STV team" + os.linesep
        content_dict[last_patchID] = content

        return content_dict, whole_patchsetID 

    def send_report(self):
        content_dict, whole_patchsetID= self.make_content()
        for patchID, content in content_dict.iteritems():
            subject = "|{}| patch set {} Intel DPDK Patchset Performance Test Report".format(self.testStatus, whole_patchsetID)
            #receivers = ["fangfangx.wei@intel.com"]
            receivers = ["qian.q.xu@intel.com", "yulong.pei@intel.com", "feix.y.wang@intel.com", "fangfangx.wei@intel.com"]
            #receivers = [self.patchInfoDict["mail"], "test-report@dpdk.org"]
            #receivers = ["test-report@dpdk.org"]
            #cc_list = [self.patchInfoDict["mail"]]
            #cc_list = ["fangfangx.wei@intel.com"]
            cc_list = []

            print "patchID is {}".format(patchID)
            print "content is {}".format(content)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = "sys_stv@intel.com"
            msg['To'] = ", ".join(receivers)
            msg['CC'] = ", ".join(cc_list)
            part2 = MIMEText(content, "plain", "utf-8")
            msg.attach(part2)
            smtp = smtplib.SMTP('smtp.intel.com')
            smtp.sendmail("sys_stv@intel.com", receivers, msg.as_string())
            smtp.quit()

if __name__ == "__main__":
    reporter = PatchworkReport()
    flag_file = "/home/jenkins/applyPatch.log"
    if os.path.exists(flag_file):
        with open(flag_file, 'rb') as ff:
            content = ff.read()
        if "no patch" in content:
            pass
        else:
            reporter.send_report()
    else:
        pass

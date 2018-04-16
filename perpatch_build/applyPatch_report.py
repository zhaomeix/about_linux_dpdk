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


share_folder = "/home/DPDK"
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

        for dpdk in sorted(matchDict.keys()):
            content = ""
            failed_patches = []
            current_patchID = matchDict[dpdk].split('-')[1]

            content += "Test-Label: Intel-compilation" + os.linesep
            content += "Test-Status: {}\n".format(self.testStatus)
            #content += "Patchwork ID: {}\n".format(current_patchID)
            #content += "http://www.dpdk.org/dev/patchwork/patch/{}\n".format(current_patchID)
            content += "http://dpdk.org/patch/{}\n\n".format(current_patchID)
            content += "_apply patch file failure_\n\n"
            content += "Submitter: {}\n".format(self.patchInfoDict["submitter"])
            content += "Date: {}\n".format(self.patchInfoDict["date"])
            content += "DPDK git baseline: {}".format(self.patchInfoDict["baseline"].replace(";","\n                   "))
            content += os.linesep
 
            content += "Apply patch file failed:\n"
            error_flag = False
            for repo, error_log in patch_error_dict.iteritems():
                if error_log.has_key(current_patchID):
                    content += "Repo: {}\n".format(repo)
                    content += "{}:\n".format(current_patchID)
                    content += error_log[current_patchID]
                    content += os.linesep
                    error_flag = True
                else:
                    failed_patches.extend(error_log.keys())
            if error_flag is False:
                content += "This patchset {} apply failed on all repoes, please check error details at:\n".format(self.patchsetID)
                for i in set(failed_patches):
                    content += "http://dpdk.org/patch/{}\n".format(i)

            content += os.linesep + "DPDK STV team" + os.linesep
            content_dict[current_patchID] = content

        return content_dict

    def send_report(self):
        content_dict = self.make_content()
        for patchID, content in content_dict.iteritems():
            for patchname in self.patchSetInfoDict.keys():
                if self.patchSetInfoDict[patchname][1] == patchID:
                    SubjectInfo = self.patchSetInfoDict[patchname][6]
                    patchSubject_comma = re.sub("\[dpdk-dev", "[PATCH", SubjectInfo)
                    patchSubject = patchSubject_comma.replace(",", " ")
            #subject = "[dpdk-test-report][Intel PerPatch Build]|{}| pw{} {}".format(self.testStatus, patchID, patchSubject)
            subject = "|{}| pw{} {}".format(self.testStatus, patchID, patchSubject)
            #receivers = ["fangfangx.wei@intel.com"]
            #receivers = ["qian.q.xu@intel.com", "weichunx.chen@intel.com", "yong.liu@intel.com", "fangfangx.wei@intel.com", "peipeix.lu@intel.com"]
            #receivers = [self.patchInfoDict["mail"], "test-report@dpdk.org"]
            receivers = ["test-report@dpdk.org"]
            cc_list = [self.patchInfoDict["mail"]]

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
    flag_file = "/home/patchWorkOrg/patchwork/applyPatch.log"
    if os.path.exists(flag_file):
        with open(flag_file, 'rb') as ff:
            content = ff.read()
        if "no patch" in content:
            pass
        else:
            reporter.send_report()
    else:
        pass

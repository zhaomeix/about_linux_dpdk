# -*- coding:utf-8 -*-
import os
import re
import sys
import datetime
import string
import types
import exceptions
import pdb
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import sys

reload(sys)
sys.setdefaultencoding('utf8')

share_folder = "/home/DPDK"
report_folder = share_folder+ os.sep +"patch_build_result"


class PatchworkReport():
    def __init__(self):
        self.patchInfoDict = dict()
        self.patchsetID = ""
        self.dpdkCommit = ""
        self.patch_info = ""
        self.patchFolderName = ""
        self.compilation = dict()
        self.testStatus = "SUCCESS"
        self.pathSetInfoDict = dict()

    def readInfo(self):
        patch_file = open(share_folder+ os.sep +"info.txt")
        #patch_file = open(share_folder+ os.sep +"i.txt")
        self.patch_info = patch_file.read().strip()
        patch_file.close()

    def getPatchSetInfo(self):
        with open(report_folder + os.sep + self.patchFolderName + os.sep + "patchsetInfo.txt", "rb") as pi:
            patchInfo = pi.read()
        self.patchSetInfoDict = eval(patchInfo) 
        return self.patchSetInfoDict

    def getPatchsetID(self):
        self.patchsetID = self.patch_info.split("_")[0]
        return self.patchsetID

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

    def make_patchinfo_content(self, patchID):
        content = ""
        self.getPatchInfo()
        #content += "Patchwork ID: " + self.patchInfoDict["patchworkId"] + os.linesep
        #content += "http://www.dpdk.org/dev/patchwork/patch/{}\n".format(patchID)
        content += "Submitter: {}\n".format(self.patchInfoDict["submitter"])
        content += "Date: {}\n".format(self.patchInfoDict["date"])
        content += "DPDK git baseline: {}\n".format(self.patchInfoDict["baseline"].replace(";","\n                   "))
        content += os.linesep

        return content

    def get_compilation_info(self):
        ret = True
        pattern = "Build complete"
        patCompileFile = r"compile_(.*).log"

        patchFolder = report_folder + os.sep + self.patchFolderName
        for patchFile in os.listdir(patchFolder):
            if patchFile.startswith("dpdk"):
                self.compilation[patchFile] = dict()
                for os_name in os.listdir(patchFolder + os.sep + patchFile):
                    self.compilation[patchFile][os_name] = dict()
                    for fileName in os.listdir(patchFolder + os.sep + patchFile + os.sep + os_name):
                        if fileName.startswith("compile_") == False:
                            continue
                        result = re.findall(patCompileFile, fileName)
                        if len(result) == 0:
                            continue
                        target = "".join(result)
                        self.compilation[patchFile][os_name].setdefault(target,[]).append(patchFolder + os.sep + patchFile + os.sep + os_name + os.sep + fileName)
                        fp = open(self.compilation[patchFile][os_name][target][0], 'rb')
                        content = "".join(fp.readlines())
                        m = re.findall(pattern, content, re.MULTILINE)
                        if len(m) == 0:
                            self.compilation[patchFile][os_name].setdefault(target,[]).append("compile error")
                            ret = False
                        else:
                            self.compilation[patchFile][os_name].setdefault(target,[]).append("compile pass")
        print "self.compilation is {}".format(self.compilation)
        return ret

    def make_content(self):
        self.getPatchInfo()
        pass_flag = self.get_compilation_info()
        matchDict = json.load(open(report_folder + os.sep + self.patchFolderName + os.sep + "TarMatchIdInfo.txt", "r"))
        print matchDict
        self.patchSetInfoDict = self.getPatchSetInfo()
        content_dict = dict()
        for dpdk in sorted(matchDict.keys()):
            match_flag = True
            fail_cnt = 0
            pass_cnt = 0
            content = ""
            error_content = ""

            current_patchID = matchDict[dpdk].split('-')[1]
            patchset_content = self.make_patchinfo_content(current_patchID)

            content += "Test-Label: Intel-compilation\n"
            for i in self.compilation[dpdk]:
                for result in self.compilation[dpdk][i]:
                    if self.compilation[dpdk][i][result][1] == 'compile error':
                        match_flag = False
                        fail_cnt += 1
                    else:
                        pass_cnt += 1
            if match_flag == True:
                content += "Test-Status: SUCCESS\n"
                content += "http://dpdk.org/patch/{}\n\n".format(current_patchID)
                content += "_Compilation OK_\n\n"
                content += patchset_content
                content += "{} --> compile pass\n".format(matchDict[dpdk])
            else:
                content += "Test-Status: FAILURE\n\n"
                content += "http://dpdk.org/patch/{}\n\n".format(current_patchID)
                content += "_Compilation issues_\n\n"
                content += patchset_content
                content += "{} --> compile error\n".format(matchDict[dpdk])

            content += "Build Summary: {} Builds Done, {} Successful, {} Failures\n".format((pass_cnt+fail_cnt), pass_cnt, fail_cnt)

            content += os.linesep
            content += "Test environment and configuration as below:\n"

            fail_build_num = 0
            for os_name in self.compilation[dpdk].keys():
                content += "OS: " + os_name + os.linesep
                with open(report_folder + os.sep +self.patchFolderName + os.sep + dpdk + os.sep + os_name + os.sep + "system.conf", "rb") as oi:
                        os_info = oi.read()
                os_list = eval(os_info)
                content += "    " + os_list[0].strip() + '\n'
                content += "    " + os_list[1].strip() + '\n'
                content += "    " + os_list[2].strip() + '\n'
                content += "    " + os_list[3].strip() + '\n'
                for target in self.compilation[dpdk][os_name].keys():
                    content += "    " + target + os.linesep

                    if self.compilation[dpdk][os_name][target][1] == "compile pass":
                        continue

                    if os.path.exists(self.compilation[dpdk][os_name][target][0]):
                        with open(self.compilation[dpdk][os_name][target][0], "rb") as cl:
                            log_list = cl.read().split("== ")
                        error_log = ''
                        for item in log_list:
                            if item.find("Error ") != -1:
                                item = "\n== " + item
                                item = item.replace("Configuration done", "")
                                item = re.sub(r">>>.*<<<", "", item)
                                item = re.sub(r'\=\=\s.*\n', "", item)
                                item = re.sub(r'\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=\=', "", item)
                                item = re.sub(r'g?make(\[\d+\])?\:.*\n', "", item)
                                item = re.sub(r'\s+CC\s+.*\.o.*\n', "", item)
                                item = re.sub(r'LD\s+test.*\n', "", item)
                                item = re.sub(r'\n*$', "\n", item)
                                item = re.sub(r'^\s+', "", item)
                                item = re.sub(r'\^\n+', "^\n", item)
                                item = re.sub(r'\n\s*\n+', "    \n", item)
                                error_log += item
                        error_content += os.linesep + "Failed Build #{}:\n".format(fail_build_num+1)
                        error_content += "OS: {}\n".format(os_name)
                        if "shared" in target or "debug" in target:
                            error_content += "Target: {}\n\n".format(target)
                        else:
                            error_content += "Target: {}\n".format(target)
                        error_content += error_log
                        fail_build_num += 1
                        error_content += os.linesep

            content += error_content
            content += os.linesep + "DPDK STV team" + os.linesep
            content_dict[current_patchID] = content

        return content_dict 

    def send_report(self):
        content_dict = self.make_content()
        print len(content_dict)
        for patchID, content in content_dict.iteritems():
            for patchname in self.patchSetInfoDict.keys():
                if self.patchSetInfoDict[patchname][1] == patchID:
                    SubjectInfo = self.patchSetInfoDict[patchname][6]
                    patchSubject_comma = re.sub("\[dpdk-dev", "[PATCH", SubjectInfo)
                    patchSubject = patchSubject_comma.replace(",", " ")
            if "Test-Status: SUCCESS" in content:
                self.testStatus = "SUCCESS"
            else:
                self.testStatus = "FAILURE"
            #subject = "[dpdk-test-report][Intel PerPatch Build]|{}| pw{} {}".format(self.testStatus, patchID, patchSubject)
            subject = "|{}| pw{} {}".format(self.testStatus, patchID, patchSubject)
            #receivers = ["qian.q.xu@intel.com", "weichunx.chen@intel.com", "yong.liu@intel.com", "fangfangx.wei@intel.com", "peipeix.lu@intel.com"]
            receivers = ["test-report@dpdk.org"]
            #receivers = ["fangfangx.wei@intel.com"]
            print self.patchInfoDict
            if self.testStatus == "SUCCESS":
                cc_list = []
            else:
                cc_list = [self.patchInfoDict["mail"]]

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = "sys_stv@intel.com"
            #msg['From'] = "fangfangx.wei@intel.com"
            msg['To'] = ", ".join(receivers)
            msg['CC'] = ", ".join(cc_list)
            part2 = MIMEText(content, "plain", "utf-8")
            msg.attach(part2)
            smtp = smtplib.SMTP('smtp.intel.com')
            #smtp.sendmail("sys_stv@intel.com", receivers, msg.as_string())
            smtp.sendmail("sys_stv@intel.com", receivers, msg.as_string())
            smtp.quit()
 

if __name__ == "__main__":
    reporter = PatchworkReport()
    reporter.send_report()   

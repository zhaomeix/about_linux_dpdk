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
import xlrd

reload(sys)
sys.setdefaultencoding('utf8')

share_folder = "/home/performance_ci"
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
        content += "Submitter: {}\n".format(self.patchInfoDict["submitter"])
        content += "Date: {}\n".format(self.patchInfoDict["date"])
        content += "DPDK git baseline: {}\n".format(self.patchInfoDict["baseline"].replace(";","\n                   "))
        content += os.linesep

        return content

    def get_test_info(self, platform_name):
        '''
        OS-NIC-TestType
        '''
        m = platform_name.split("_")
        print "platform_name is {}, m is {}".format(platform_name, m)
        os = m[0]
        test_type = m[-1]
        test_type2 = m[-2]+"_"+m[-1]
        name_length = len(platform_name)
        os_length = len(os)
        test_type_length = len(test_type)
        test_type_length2 = len(test_type2)
        if test_type == "Unit":
            test_type = test_type2
            nic = platform_name[os_length+1:name_length-test_type_length2-1]
        else :
            nic = platform_name[os_length+1:name_length-test_type_length-1]
        return os,nic,test_type

    def get_system_info(self, folder):
        '''Kernel-GCC'''
        f = None
        kernel = 'NA'
        gcc = 'NA'
        system_filename = 'system.conf'
        vm_system_filename = 'virtual_system.conf'
        if os.path.exists(folder+os.sep+system_filename):
            f = open(folder+os.sep+system_filename)
        else:
            f = None

        if f is not None:
            line = f.readline()
            s = line.split(',')
            pattern = re.compile(r':.*')
            kernel = ''
            gcc = ''
            k = pattern.search(s[0])
            if k:
                kernel = k.group()[1:-7]
            g = pattern.search(s[2])
            if g:
                gcc = g.group()[1:-4]
                gcc = gcc.split(" ")[2]

        return kernel, gcc

    def check_multiple_targets(self, folder,platform_name):
        '''check whether platform run multiple targets
           if true return 0 else return 1
        '''
        print "check multiple targets folder is {}".format(folder)
        if os.path.isdir(folder):
            fnames = os.listdir(folder)
            i = 0
            flag = 0
            if fnames is not None:
                for fname in fnames:
                    if os.path.isfile(folder+'/'+fname) and i < 4:
                        flag += 1
                        i += 1
                if flag == 0:
                    return 0
                else :
                    return 1

    def get_sheet(self, result_filename):
        if os.path.exists(result_filename):
            d = xlrd.open_workbook(result_filename)
            sheet = d.sheets()[0]

            return sheet

    def get_failed_cases_info(self, sheet):
        column = len(sheet.col_values(1))
        m = 1
        total_number = 0
        failed_number = 0
        failed_case_list = []
        target = sheet.cell(1,1).value
        if sheet.cell(1,5).value != None and sheet.cell(1,5).value != '':
            failed_total_number = 'N/A: {}'.format(sheet.cell(1,5).value)
        else:
            while m < column:
                if sheet.cell(m,4).value != None and sheet.cell(m,4).value != '':
                    total_number += 1
                if sheet.cell(m,5).value.startswith('FAILED') or sheet.cell(m,5).value.startswith('BLOCKED'):
                    failed_number += 1
                    failed_case_list.append(sheet.cell(m,4).value)
                m += 1
            failed_total_number = str(failed_number)+'/'+str(total_number)

        return failed_total_number,failed_case_list,failed_number,target

    def get_all_info(self,foldername,platform_name):
        all_info = []
        fail_number = 0

        test_info = self.get_test_info(platform_name)
        print "test_info is {}".format(test_info)
        os_info = test_info[0]
        nic_info = test_info[1].lower()
        test_type = test_info[2]

        result_filename = '{}_single_core_perf.txt'.format(nic_info)

        folder = report_folder+os.sep+foldername+os.sep+platform_name
        flag = self.check_multiple_targets(folder, platform_name)
        print "flag is {}".format(flag)
        if flag == 1 and os.path.exists(folder+os.sep+"test_results.xls"):
            system_info = self.get_system_info(folder)
            kernel_info = system_info[0]
            gcc_info = system_info[1]

            row = []
            perf_content = ""
            row.append(os_info)
            row.append(nic_info)
            row.append(test_type)
            row.append(kernel_info)
            row.append(gcc_info)

            sheet = self.get_sheet(folder+os.sep+"test_results.xls")
            failed_cases_info = self.get_failed_cases_info(sheet)
            failed_total_number = failed_cases_info[0]
            failed_cases_list = failed_cases_info[1]
            failed_number = failed_cases_info[2]
            target = failed_cases_info[3]

            if failed_number != 0:
                fail_number += 1

            if os.path.exists(folder+os.sep+result_filename):
                with open(folder+os.sep+result_filename) as perf_file:
                    for line in perf_file.readlines():
                        perf_content += line
            if 'N/A' in failed_total_number:
                perf_content += failed_total_number.split(':')[-1]
                fail_number = 1
            row.append(target)
            row.append(perf_content)
            row.append(failed_total_number)
            row.append(failed_cases_list)
            all_info.append(row)
            print "flag 1 row is %s"%row
        if flag == 0:
            filenames = os.listdir(folder)
            for filename in filenames:
                if os.path.exists(folder+os.sep+filename+os.sep+result_filename):
                    system_info = self.get_system_info(folder+os.sep+filename)
                    kernel_info = system_info[0]
                    gcc_info = system_info[1]
                    row = []
                    row.append(os_info)
                    row.append(nic_info)
                    row.append(test_type)
                    row.append(kernel_info)
                    row.append(gcc_info)
                    target = 'N/A'
                    target = filename

                    sheet = self.get_sheet(folder+os.sep+"test_results.xls")
                    failed_cases_info = self.get_failed_cases_info(sheet)
                    failed_total_number = failed_cases_info[0]
                    failed_cases_list = failed_cases_info[1]
                    failed_number = failed_cases_info[2]
                    target = failed_cases_info[3]
                    if os.path.exists(folder+os.sep+result_filename):
                        with open(folder+os.sep+filename+os.sep+result_filename) as perf_file:
                            for line in perf_file.readlines():
                                perf_content += line
                    if 'N/A' in failed_total_number:
                        perf_content += failed_total_number.split(':')[-1]
                        fail_number = 1

                    row.append(target)
                    row.append(perf_content)

                    if failed_number != 0:
                        fail_number += 1
                    row.append(failed_total_number)
                    row.append(failed_cases_list)

                    all_info.append(row)
                    print "row is %s"%row
        return all_info, fail_number

    def execute_local(self,cmd):
        print cmd
        outStream = os.popen(cmd)
        out = outStream.read()
        outStream.close()
        print out
        return out

    def get_report_content(self):
        report_content = []
        foldername = "patch_{}/regression_results".format(self.execute_local("sed -n '1 p' {}/info.txt".format(share_folder)).split("\n")[0])
        filenames = []
        flag = 0
        filenames = os.listdir(report_folder+os.sep+foldername)
        print "filename is {}".format(filenames)
        for filename in filenames:
            if os.path.isdir(report_folder+os.sep+foldername+os.sep+filename):
                all_info = self.get_all_info(foldername, filename)
                report_content.extend(all_info[0])
                flag += all_info[1]
        return report_content, flag

    def content_combine(self):
        content = ''
        report_content, flag = self.get_report_content()
        print "report_content is {}".format(report_content)
        for i in report_content:
            content += '\n' + i[0] + '\n'
            content += "Kernel: %s\n" % i[3]
            content += "GCC: %s\n" % i[4]
            content += "NIC: %s\n" % i[1]
            content += "Target: %s\n" % i[5]
            if 'N/A' in i[7]:
                content += "Fail/Total: N/A\n"
            else:
                content += "Fail/Total: {}\n".format(i[7])
            if len(i[8]):
                content += "Failed cases list:\n"
                for case in i[8]:
                    content += "      - DTS %s\n" % case
            content += os.linesep
            content += "Detail performance results: \n%s\n" % i[6]
        return content, flag

    def send_report(self):
        content = ""
        performance_content, flag = self.content_combine()
        print "performance_content is {}".format(performance_content)
        status = 'ERROR'
        if flag ==0:
            status = 'SUCCESS'

        self.getPatchInfo()
        matchDict = json.load(open(report_folder + os.sep + self.patchFolderName + os.sep + "TarMatchIdInfo.txt", "r"))
        
        self.patchSetInfoDict = self.getPatchSetInfo()
        whole_patchsetID = matchDict[str(sorted(int(key) for key in matchDict.keys())[-1])]
        last_patchID = whole_patchsetID.split("-")[-1]
        patchset_content = self.make_patchinfo_content(last_patchID)

        content += "Test-Label: Intel-Performance-Testing\n"
        if status == "SUCCESS":
            content += "Test-Status: SUCCESS\n"
            content += "http://dpdk.org/patch/{}\n\n".format(last_patchID)
            content += "_Performance Testing PASS_\n\n"
            content += patchset_content
            content += "{} --> performance testing pass\n".format(whole_patchsetID)
        else:
            content += "Test-Status: FAILURE\n\n"
            content += "http://dpdk.org/patch/{}\n\n".format(last_patchID)
            content += "_Performance Testing issues_\n\n"
            content += patchset_content
            content += "{} --> performance testing error\n".format(whole_patchsetID)

        content += os.linesep
        content += "Test environment and result as below:\n"

        content += performance_content
        content += os.linesep + "DPDK STV team" + os.linesep

        subject = "|{}| {} Intel DPDK PatchSet Performance Test Report".format(status, whole_patchsetID)
        rece_maillist = ["qian.q.xu@intel.com", "yulong.pei@intel.com", "feix.y.wang@intel.com", "fangfangx.wei@intel.com"]
        #rece_maillist = ["fangfangx.wei@intel.com"]
        from_maillist = "sys_stv@intel.com"
        if status == "SUCCESS":
            cc_list = []
        else:
            cc_list = []
            #cc_list = ["fangfangx.wei@intel.com"]

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = "sys_stv@intel.com"
        msg['To'] = ", ".join(rece_maillist)
        msg['CC'] = ", ".join(cc_list)
        part2 = MIMEText(content, "plain", "utf-8")
        msg.attach(part2)
        smtp = smtplib.SMTP('smtp.intel.com')
        smtp.sendmail("sys_stv@intel.com", rece_maillist, msg.as_string())
        smtp.quit()
 

if __name__ == "__main__":
    reporter = PatchworkReport()
    reporter.send_report()   

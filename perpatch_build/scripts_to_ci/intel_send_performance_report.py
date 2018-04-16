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

# -*- coding:utf-8 -*-
import os
import re
import sys
import datetime
import exceptions
import argparse
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import xlrd

reload(sys)
sys.setdefaultencoding('utf8')


class PatchworkReport(object):
    def __init__(self, report_folder):
        self.report_folder = report_folder
        self.patchInfoDict = dict()
        self.testStatus = "SUCCESS"

    def getPatchSetInfo(self):
        InfoFile = "".join([self.report_folder, "/patchsetInfo.txt"])
        with open(InfoFile, "rb") as pi:
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
        submitInfoFile = "".join([self.report_folder, "/submitInfo.txt"])
        if os.path.exists(submitInfoFile):
            with open(submitInfoFile, "rb") as info:
                content = info.read()
                infoDict = self.fetch_keys_values(content)
            for item in infoDict.keys():
                self.patchInfoDict[item] = infoDict[item]

    def make_patchinfo_content(self):
        content = ""
        self.getPatchInfo()
        content += "Submitter: {}\n".format(self.patchInfoDict["submitter"])
        content += "Date: {}\n".format(self.patchInfoDict["date"])
        content += "DPDK git baseline: {}\n".format(self.patchInfoDict["baseline"].replace(";", "\n "))
        content += os.linesep
        return content

    def get_test_info(self, platform_name):
        '''
        platform_name is named as "OS-NIC"
        '''
        m = platform_name.split("_")
        os = m[0]
        nic = "_".join(m[1:])
        return os, nic

    def get_system_info(self, folder):
        '''Kernel-GCC'''
        f = None
        kernel = 'NA'
        gcc = 'NA'
        system_filename = 'system.conf'
        vm_system_filename = 'virtual_system.conf'
        if os.path.exists(folder + os.sep + system_filename):
            f = open(folder + os.sep + system_filename)
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
        target = sheet.cell(1, 1).value
        if sheet.cell(1, 5).value is not None and sheet.cell(1, 5).value != '':
            failed_total_number = 'N/A: {}'.format(sheet.cell(1, 5).value)
        else:
            while m < column:
                if sheet.cell(m, 4).value is not None and sheet.cell(m, 4).value != '':
                    total_number += 1
                if (sheet.cell(m, 5).value.startswith('FAILED')
                    or sheet.cell(m, 5).value.startswith('BLOCKED')):
                    failed_number += 1
                    failed_case_list.append(sheet.cell(m, 4).value)
                m += 1
            failed_total_number = str(failed_number)+'/'+str(total_number)

        return failed_total_number, failed_case_list, failed_number, target

    def get_all_info(self, resultPath, platform_name):
        all_info = []
        fail_number = 0

        test_info = self.get_test_info(platform_name)
        os_info = test_info[0]
        nic_info = test_info[1].lower()

        result_filename = '{}_single_core_perf.txt'.format(nic_info)

        folder = resultPath + os.sep + platform_name
        if os.path.exists(folder + os.sep + "test_results.xls"):
            system_info = self.get_system_info(folder)
            kernel_info = system_info[0]
            gcc_info = system_info[1]

            row = []
            perf_content = ""
            row.append(os_info)
            row.append(nic_info)
            row.append(kernel_info)
            row.append(gcc_info)

            sheet = self.get_sheet(folder + os.sep + "test_results.xls")
            failed_cases_info = self.get_failed_cases_info(sheet)
            failed_total_number = failed_cases_info[0]
            failed_cases_list = failed_cases_info[1]
            failed_number = failed_cases_info[2]
            target = failed_cases_info[3]

            if failed_number != 0:
                fail_number += 1

            if os.path.exists(folder + os.sep + result_filename):
                with open(folder + os.sep + result_filename) as perf_file:
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
        return all_info, fail_number

    def execute_local(self, cmd):
        print cmd
        outStream = os.popen(cmd)
        out = outStream.read()
        outStream.close()
        print out
        return out

    def get_report_content(self):
        report_content = []
        resultPath = "{}/regression_results".format(self.report_folder)
        filenames = []
        flag = 0
        filenames = os.listdir(resultPath)
        for filename in filenames:
            if os.path.isdir("".join([resultPath, os.sep, filename])):
                all_info = self.get_all_info(resultPath, filename)
                report_content.extend(all_info[0])
                flag += all_info[1]
        return report_content, flag

    def content_combine(self):
        content = ''
        report_content, flag = self.get_report_content()
        for i in report_content:
            content += '\n' + i[0] + '\n'
            content += "Kernel: {}\n".format(i[2])
            content += "GCC: {}\n".format(i[3])
            content += "NIC: {}\n".format(i[1])
            content += "Target: {}\n".format(i[4])
            if 'N/A' in i[6]:
                content += "Fail/Total: N/A\n"
            else:
                content += "Fail/Total: {}\n".format(i[6])
            if len(i[7]):
                content += "Failed cases list:\n"
                for case in i[7]:
                    content += "      - DTS {}\n".format(case)
            content += os.linesep
            content += "Detail performance results: \n{}\n".format(i[5])
        return content, flag

    def send_email(self, receivers, cc_list, subject, content):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = "the sender's email address"
        msg['To'] = ", ".join(receivers)
        msg['CC'] = ", ".join(cc_list)
        part2 = MIMEText(content, "plain", "utf-8")
        msg.attach(part2)
        smtp = smtplib.SMTP('the smtp server')
        smtp.sendmail("the sender's email", receivers, msg.as_string())
        smtp.quit()

    def send_report(self, status):
        self.getPatchInfo()
        TarMatchfile = "".join([self.report_folder, "/TarMatchIdInfo.txt"])
        matchDict = json.load(open(TarMatchfile, "r"))

        sortedKey = sorted(int(key) for key in matchDict.keys())
        whole_patchsetID = matchDict[str(sortedKey[-1])]
        first_patchID = whole_patchsetID.split("-")[0]

        self.patchSetInfoDict = self.getPatchSetInfo()

        if status:
            performance_content, flag = self.content_combine()
            patchset_content = self.make_patchinfo_content()
            self.testStatus = "FAILURE"
            if flag == 0:
                self.testStatus = "SUCCESS"
        else:
            self.testStatus = "FAILURE"
            patchErrorfile = "".join([self.report_folder,
                                     "/patches/patchError.txt"])
            patch_error_dict = json.load(open(patchErrorfile, "r"))

        content = ""
        content += "Test-Label: Performance-Testing" + os.linesep
        content += "Test-Status: {}\n".format(self.testStatus)
        content += "http://dpdk.org/patch/{}\n\n".format(first_patchID)
        if status:
            if self.testStatus == "SUCCESS":
                content += "_Performance Testing PASS_\n\n"
                content += patchset_content
                content += "{} --> performance testing pass\n".format(whole_patchsetID)
            else:
                content += "_Performance Testing issues_\n\n"
                content += patchset_content
                content += "{} --> performance testing fail\n".format(whole_patchsetID)
            content += os.linesep
            content += "Test environment and result as below:\n"
            content += performance_content
        else:
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
        print "content is {}".format(content)

        subject = "|{}| {} DPDK PatchSet Performance Test Report".format(self.testStatus, whole_patchsetID)
        rece_maillist = ["receiver's email address"]
        if status == "SUCCESS":
            cc_list = []
        else:
            cc_list = [self.patchInfoDict["submitter"]]

        self.send_email(rece_maillist, cc_list, subject, content)


if __name__ == "__main__":
    """
    Send report to patchwork.
    If patchError.txt exists, it maybe apply patch set failed or no patch
    to tests.
    If patchError.txt doesn't exists, it apply patch set successfully.
    Arguments:
    -p/--dst-path: the full path of share folder which store test result
    """
    parser = argparse.ArgumentParser(description='Send report to patchwork')
    parser.add_argument('-p', '--path', type=str, help='the absolute path of result folder')
    args = parser.parse_args()
    reporter = PatchworkReport(args.path)

    flag_file = "{}/patches/patchError.txt".format(args.path)
    if os.path.exists(flag_file):
        with open(flag_file, 'rb') as ff:
            content = ff.read()
        if "no patch" in content:
            pass
        else:
            reporter.send_report(False)
    else:
        reporter.send_report(True)

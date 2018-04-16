#!/usr/bin/python

import re
import os, sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_report(_from,_to,_sub,_cc,_content):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = _sub
    msg['From'] = _from
    msg['CC'] = ",".join(_cc)
    msg['To'] = ", ".join(_to)   
    part2 = MIMEText(_content, "plain", "utf-8")
    msg.attach(part2)
    smtp = smtplib.SMTP('smtp.intel.com')
    smtp.sendmail(_from, _to, msg.as_string())
    smtp.quit()


def get_latest_commit_info():
    f = os.popen("git log -1 --pretty=medium")
    lines = f.readlines()
    commit = lines[0].split(' ')[1]
    author = lines[1].split(':')[1]
    author = author[:-1]
    date = lines[2].split(':')[1:]
    date = ''.join(date)
    date = date[:-1]
    comment = lines[4]
    comment = comment[:-1]
    
    return author,date,comment,commit

def get_commit_content(pro):
    project = str(pro).upper()
    content = ''
    author = get_latest_commit_info()[0]
    date = get_latest_commit_info()[1]
    comment = get_latest_commit_info()[2]
    commit = get_latest_commit_info()[3]
    content += '{} last commit information:\n'.format(project)
    content += 'Commit Hash: ' +commit
    content += 'Author: '+author+'\n'
    content += 'Commit time: '+date+'\n'
    content += 'Comment: '+comment+'\n\n'

    return content

def execute_local(cmd):
    print cmd
    outStream = os.popen(cmd)
    out = outStream.read()
    outStream.close()
    print type(out)
    print out
    return out

def get_system_info(dir , filename):
    system_info = []
    OS = filename.rsplit("-")[2]
    print OS
    system_info.append(OS)
    with open(dir +os.sep+ filename) as f:
        line = f.read()
    line = line.split("\n")[0]
    line_info = line.replace("{", "").replace("}", "").split(",")
    for _ in line_info:
        split_info = _.replace("[", "").replace("]", "").split(":")
        if split_info[0].find("KERNEL") != -1 :
            Kernel = split_info[1]
            system_info.append(Kernel)
        elif split_info[0].find("GCC") != -1 :
            GCC = split_info[1]
            system_info.append(GCC)
        elif split_info[0].find("ICC") != -1 :
            ICC = split_info[1]
            system_info.append(ICC)
        else:
            CLANG = split_info[1]
            system_info.append(CLANG)
    #print system_info       
    return system_info

def main():
    build_log_dir = sys.argv[1]
    rec_mailist = ["npg.sw.data.plane.virtual.switching.and.fpga@intel.com","zhihong.wang@intel.com","jianfeng.tan@intel.com","jiayu.hu@intel.com","heqing.zhu@intel.com","heqing.zhu@intel.com","helin.zhang@intel.com","qian.q.xu@intel.com", "fangfangx.wei@intel.com"]
    #rec_mailist = ["fangfangx.wei@intel.com"]
    #from_mailist = "fangfangx.wei@intel.com"
    from_mailist = "sys_stv@intel.com"
    cc_mailist = []

    out1 = execute_local("uname -r")
    m = re.search("\d+\.\d+\.\d+-\d+",out1)
    kernel_ver = m.group()
    out2 = execute_local("gcc --version | head -n 1")
    n = re.search("gcc \(GCC\) (\d+\.\d+\.\d+)", out2)
    gcc_version = n.group(1)

    os.chdir(build_log_dir+'/../dpdk')
    content = get_commit_content("dpdk-stable-17.05")
    os.chdir(build_log_dir+'/../ovs')
    ovs_content = get_commit_content("ovs")
    content += ovs_content
    fail_count = 0
    pass_count = 0
    build_info_dict = dict()

    for parent,dirnames,filenames in os.walk(build_log_dir):
        for filename in filenames:
            if re.search("^ovs-build-", filename):
                build_info_dict[filename] = dict()
                print filename, parent
                system_info = get_system_info(parent, filename)
                f = open(os.path.join(parent,filename), 'r')
                readline = f.readlines()
                f.close()
                
                error_msg = []
                warning_msg = []
                message = "".join(readline)
                config = ''
                n = re.search(">>>(.*)<<<", readline[1])
                target = n.group(1)
                config += 'Config: {}\n'.format(target)
                msg = re.search(">>>(.*)<<<", readline[2])
                if msg:
                    config += '{}\n'.format(msg.group(1))
                build_info_dict[filename]['config'] = config
                if re.search( r'GCC', target, re.M|re.I) :
                    build_info_dict[filename]['system_info'] = "%s / Linux %s / GCC %s\n" %(system_info[0], system_info[1], system_info[2])
                elif re.search( r'ICC', target, re.M|re.I) :
                    build_info_dict[filename]['system_info'] = "%s / Linux %s / ICC %s\n" %(system_info[0], system_info[1], system_info[3])
                else :
                    build_info_dict[filename]['system_info'] = "%s / Linux %s / CLANG %s\n" %(system_info[0], system_info[1], system_info[4])

                pattern = "Libraries have been installed in"
                m = re.findall(pattern, message, re.MULTILINE)
                if len(m) == 0:
                    fail_count += 1
                    build_info_dict[filename]['result'] = 'Error Messages:\n'
                    for line in readline:
                        if re.search("\s+error(s?)", line, re.I) or re.search("\s+fail(ed)?", line, re.I):
                            build_info_dict[filename]['result'] += line
                            #error_msg.append(line)
                        if re.search("^\s+Warn(ing)?", line, re.I):
                            warning_msg.append(line)
                else:
                    pass_count += 1
                    build_info_dict[filename]['result'] = 'SUCCESS'

    content += '\nBuild Summary:    ' + str(pass_count + fail_count) + " Builds Done, " + str(pass_count) + " Successful, " + str(fail_count) + " Failure(s).\n\n"
    content_suc = ''
    content_err = ''
    for key in build_info_dict.keys():
        if build_info_dict[key]['result'] == 'SUCCESS':
            content_suc += '\nSuccess build:\n'
            content_suc += build_info_dict[key]['system_info'] + build_info_dict[key]['config']
        else:
            content_err += '\nFailed build:\n'
            content_err += build_info_dict[key]['system_info'] + build_info_dict[key]['config'] + build_info_dict[key]['result']

    result = "ERROR"
    if fail_count == 0:
        result = "SUCCESS"
    subject = "[ %s ]DPDK OVS Build Test Report (%s/%s)"%(result, str(pass_count),str(pass_count+fail_count))
    content += content_err + content_suc
    print "start to send report\n"
    send_report(from_mailist, rec_mailist, subject, cc_mailist, content)

if __name__ == "__main__":
    main()

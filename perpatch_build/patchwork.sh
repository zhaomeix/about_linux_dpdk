#!/bin/bash

source /root/.bash_profile
source /etc/profile
#python /home/patchWorkOrg/isg_cid-dpdk/tools/DTF/tools/patchwork/patchwork.py $*
export http_proxy=http://proxy-shz.intel.com:911
#python /home/patchWorkOrg/patchwork/patchwork.py $*
python /home/patchWorkOrg/patchwork/get_patchsets.py $*

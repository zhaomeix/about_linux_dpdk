#/user/bin/bash
path="/var/www/DPDK_TEST_RESULT/"
save_json_path="/var/www/DPDK_TEST_RESULT/"
#path="/c/Users/zhaomeiX/Desktop/shell_script/"
#save_json_path="/c/Users/zhaomeiX/Desktop/shell_script/"
file_name="test_result"
date_time=`date "+%F"`
cd $path
commit_path=(`ls | grep $date_time`)

echo $commit_path
cd  $commit_path[0]
temp=(`ls`)
if [ !$temp ] ;then
    cd ..
	cd $commit_path[1]
echo `pwd`
#plats=(`ls -l $total_path |awk '/^d/ {print $NF}'`)
json_files=(`find ./ -name test_results.json`)
for (( i=0;i< ${#json_files[@]};i++ ))
do
	cp ${json_files[i]} $save_json_path${file_name}$i.json
done

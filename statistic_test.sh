#/user/bin/bash

result_file1="haha.txt"
result_file2="sort_result.txt"
result_csv="result.csv"
fail_list="fail_list.csv"
owner_list="Book1.csv"


#handle owner_list filename

sed -i "/test_plan/d" ${owner_list}
sed -i 's/[[:space:]]//g' ${owner_list}
sed -i "s/TestSuite_//g" ${owner_list}
sed -i "s/.py//g" ${owner_list}

echo "1111"

args=$*

rm -rf $result_file1 $result_file2 $result_csv $fail_list

for filename in ${args}
do
        ip=`sed -n '2p' $filename | cut -d ":" -f 1`
		platform=`sed -n '3p' $filename | cut -d ":" -f 1`
		add_info=":"${ip}":"${platform}
		#echo $add_info
        sed '1,3d' $filename | tac | sed '1,3d' | tac | sort -t ":" -k1 | sed "s/$/${add_info}/" | sed 's/,//g' | sed 's/[[:space:]]//g' | sed "s/\"//g" >> $result_file1
		
done
sort -t ":" -k1 $result_file1 > $result_file2

na_num=0
pass_num=0
fail_num=0
blocked_num=0

#total_repeat_num=(`cut -d ":" -f 1 $result_file2 | uniq -c | grep -o '[0-9]\{1,2\}'`)

case_list=(`cut -d ":" -f 1 $result_file2 | uniq -c | grep -o '[a-z].*'`)
suite_list=(`cut -d ":" -f 1 $result_file2 | uniq -c | grep -o '[a-z].*' | cut -d "/" -f1`)
#owners_list=(`cut -d "," -f 2 $owner | sed 's/[[:space:]]//g'`)
rm -rf $result_file1

echo "OWNER","CASE NAME","TOTAL NUM","PASS","FAIL","N/A","BLOCKED" > $result_csv

for (( i=0;i< ${#case_list[@]};i++ ))
do
        
		total_repeat_num=`grep -o ${case_list[i]} ${result_file2} | wc -l`
		results=(`grep ${case_list[i]} ${result_file2} | cut -d ":" -f 2`)
		
		ip=(`grep ${case_list[i]} ${result_file2} | cut -d ":" -f 3`)
		
		platform=(`grep ${case_list[i]} $result_file2 | cut -d ":" -f 4`)
		
		owner=`grep ^"${suite_list[i]}""," $owner_list | cut -d "," -f2`
		
		echo $owner
		echo ${case_list[i]}
		echo "on going ..."
		for (( j=0;j< ${#results[@]};j++ ))
		do
				
				if [ ${results[j]} == "passed" ];then
						let pass_num=pass_num+1
				fi
				if [ ${results[j]} == "n/a" ];then
						let na_num=na_num+1
				fi
				if [ ${results[j]} == "blocked" ];then
						let blocked_num=blocked_num+1
						echo ${owner},${case_list[i]},${results[j]},${ip[j]},${platform[j]} >> $fail_list
				fi
				if [ ${results[j]} == "failed" ];then
						let fail_num=fail_num+1
						
						echo ${owner},${case_list[i]},${results[j]},${ip[j]},${platform[j]} >> $fail_list
				fi
		done
		
		echo ${owner},${case_list[i]},${total_repeat_num},${pass_num},${fail_num},${na_num},${blocked_num}>> $result_csv
		na_num=0
		pass_num=0
		fail_num=0
		blocked_num=0
		
		
done
echo "everyone own case number:"
cut -d "," -f 1 ${result_csv}| sed '1d' | sort | uniq -c
echo "---------------------------"
echo "everyone fail case count as follow:"
cut -d "," -f 1 ${fail_list} | sort | uniq -c



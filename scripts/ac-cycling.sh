#! /bin/bash


# This line needs to be first to get the correct execution path of 
# this script. This is needed for dynamically setting the
# config file path.
declare -g script_path=$_;

check_lock() {
    touch $lock_file
    # Ensure permission allow anyone to kill script.
    # 666=r/w for all users.
    #
    # Example:
    #   echo 1 > /path/to/lock_file
    chmod 666 $lock_file

    if [[ $(cat $lock_file) == 1 ]]; then 
        log_line "Recieved signal to terminate process (exit 0)"
        exit 0;
    fi
}

is_booted() {
    nc -4 -d -z -w 1 $sut_host $sut_port &> /dev/null;
    if [ $? -eq 0 ]; then
        echo true
    else
        echo false
    fi
}

wait_for_boot() {
    declare -i time_start=$SECONDS
    # Timeout after 5 minutes. I've seen 300 at most.
    # Adjust as necessary.
    declare -i time_max=320;
    declare -i time_min=90;
    
    local is_booted=false; 
    
    while true;
    do
        declare -i duration=$(($SECONDS-$time_start));
        if [ $(is_booted) ] && \
            [ $duration -gt $time_min ]; then
            # SUT cycled in the expected time.
            break
        elif [ $(is_booted) ] && \
            [ $duration -lt $time_min ]; then
            # SUT did not cycle. Retry.
            ac_cycle;
            declare -i time_start=$SECONDS
        elif [ $duration -gt $time_max ]; then
            # Timeout waiting for boot. Retry.
            ac_cycle;
            declare -i time_start=$SECONDS
        else
            sleep 5;
        fi
    done
}


log_line() {
    declare line=$1;
    declare log_time=$(date +"%Y-%m-%d-%H-%M-%S")
    printf "${log_time} ${line}\n" >> $log_file;
}

write_config() {
    if [ -f $config_file ]; then
        rm $config_file
    fi

    declare config_lines=(\
        "# Target server IP" \
        "sut_host=''" \
        "# Target server password" \
        "sut_pass=''" \
        "# Target server port" \
        "# Use 22 for Linux, 3389 for Windows" \
        "sut_port=22" \
        "# Rack IP for target server" \
        "rack_host=''" \
        "# Rack password for target server" \
        "rack_pass=''" \
        "# Rack port for target server" \
        "rack_sut_port=" \
        "# Cycling start count (0 unless resuming)" \
        "cycle_start=0" \
        "# Cycle end count" \
        "cycle_end=1000" \
        "# Log directory" \
        "log_dir='/var/tmp/'" \
        "# Lock file to stop cycling" \
        "# echo 1 > /path/to/lock_file" \
        "lock_file='/tmp/kill-ac-cycling'" \
    )

    for i in $(seq 0 $((${#config_lines[*]}-1)));
    do
        echo ${config_lines[${i}]} >> $config_file;
    done
}
    
ac_cycle() {
    sshpass -f <(printf '%s\n' $rack_pass) ssh -c aes256-cbc root@$rack_host \
        "set manager port off -i ${rack_sut_port}" &>> $log_file;
    sleep 5;
    sshpass -f <(printf '%s\n' $rack_pass) ssh -c aes256-cbc root@$rack_host \
        "set manager port on -i ${rack_sut_port}" &>> $log_file;
}

read_config() {
    declare -g sut_host;
    declare -g sut_pass;
    declare -g sut_port;
    declare -g rack_host;
    declare -g rack_pass;
    declare -g rack_sut_port;
    declare -ig cycle_start;
    declare -ig cycle_end;
    declare -g log_dir;
    declare -g lock_file;

    source $config_file
    
    # Dumb fix if missing tailing "/" in log_dir which could break 
    # concatenated path strings.
    if [ ${log_dir[-1]} != "/" ]; then
        log_dir+="/"
    fi
}

configure() {
    declare -g config_file=$(echo $script_path | grep -oP "/*.+/")config.conf;

    if [ -f $config_file ]; then
        read_config;
    else
        write_config;
        exit 1
    fi

    declare -g log_file="${log_dir}"`
        `"ac-cycling-$(date +"%Y-%m-%d-%H-%M-%S").log";

    if [ -f $lock_file ]; then
        log_line "Process locked by $lock_file"
        exit 1
    fi

}

main() {
    configure;
    while [ $cycle_start -lt $cycle_end ];
    do
        ac_cycle;
        wait_for_boot;
        check_lock;
        cycle_start+=1
    done
}

main


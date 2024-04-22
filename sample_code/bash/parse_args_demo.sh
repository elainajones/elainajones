#! /bin/bash

parse_args() {
    args="$@";
    declare -Ag CONFIG=();
    declare keys=($(echo $args | grep -oP "\B\-\S+"));
    for i in $(seq 1 ${#keys[@]}); do
        declare key="${keys[$((i-1))]}";
        # 1. Use variable keys to match everything up to the next 
        #    variable key as the variable value.
        # 2. Remove leading/trailing whitespace.
        declare val="$(\
            echo $args | \
            grep -oP "(?<=$key\s).+?(?=${keys[$i]}(\s|\Z))" | \
            grep -oP "\S.*" | grep -oP ".*\S" \
        )";
        CONFIG["$key"]="$val";
    done
}

print_help() {
    lines=(\
        "Usage: parse_args_demo [OPTIONS]" \
        "" \
        "  Example CLI application to demonstrate parsing args." \
        "" \
        "Options:" \
        "  -h, --help\tShow this message and exit." \
        "  -i, --input [INPUT]\tInput value." \
        "  -o, --output [OUTPUT]\tOutput value." \
        "  -d, --daemonize\tRun as a background process." \
    );

    for i in ${!lines[@]}; do
        line=${lines[$i]};
        printf "$line\n";
    done
}

require_val() {
    declare key="$1";
    declare val="$2";
    if ! [[ "$val" ]]; then
        echo "Option '$key' requires an argument";
        echo "Try '--help' for more information.";
        exit 1;
    fi
}

do_thing() {
    declare input="$1";
    declare output="$2";
    # Added delay to more clearly demonstrate the '-d' option.
    sleep 5;
    printf "Input:\t'$input'\n";
    printf "Output:\t'$output'\n";
}

main() {
    args=$@;
    parse_args $args;

    if ! [[ "$args" ]] || ! [[ "${!CONFIG[@]}" ]]; then
        print_help;
        exit 0;
    fi
    
    # Declare vars and define default values.
    declare input="";
    declare output="";
    declare daemonize=0;

    for key in "${!CONFIG[@]}"; do
        val="${CONFIG[$key]}";
        case $key in
            "-i")
                require_val "$key" "$val";
                input=$val;
                ;;
            "--input")
                require_val "$key" "$val";
                input=$val;
                ;;
            "-o")
                require_val "$key" "$val";
                output=$val;
                ;;
            "--output")
                require_val "$key" "$val";
                output=$val;
                ;;
            "-h")
                print_help;
                exit 0;
                ;;
            "--help")
                print_help;
                exit 0;
                ;;
            "-d")
                daemonize=1;
                ;;
            "--daemonize")
                daemonize=1;
                ;;
            *)
                echo "Invalid option '$key'";
                echo "Try '--help' for more information.";
                exit 1;
        esac
    done

    if (( $daemonize )); then
        do_thing "$input" "$output" &
        pid=$!;
        echo "Running with pid $pid";

    else
        do_thing "$input" "$output"
    fi
}

main $@;

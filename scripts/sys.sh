SYS_OSX="darwin"
SYS_CYGWIN="cygwin"
SYS_LINUX="linux"
SYS_UNKNOWN="unknown"

function sys_detect()
{
    local systems=($SYSTEM_OSX $SYSTEM_CYGWIN $SYSTEM_LINUX)
    local system_line=$(uname -s | awk '{print tolower($0)}') # to support bash v < 4.0
    local result=

    for system in ${systems[@]}
    do
        if [[ $system_line =~ $system ]]
        then
            result=$system
            break
        fi
    done

    if [[ -z $result ]]
    then
        detected=$SYSTEM_UNKNOWN
    fi

    echo $result
}

function sys_pwd()
{
    local system=$(sys_detect)
    local result=
    local addition=

    if [[ -n $1 ]]
    then
        addition="/$1"
    fi

    case $system in
        $SYSTEM_CYGWIN)
            result=$(echo "$(pwd)$addition" | cygpath -w -f -);;
        *)
            result="$(pwd)$addition"
    esac

    echo $result
}

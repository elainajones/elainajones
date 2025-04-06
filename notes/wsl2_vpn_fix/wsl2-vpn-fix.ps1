# Get ip output for the wsl2 ethernet device
$wsl_addr=C:\Windows\System32\wsl.exe -e /bin/bash --noprofile --norc -c "ip -o -4 addr list eth0"
# Parses the actual address from the output
$wsl_addr = $wsl_addr.split()[6].split('/')[0]

# Get ip route output for the wsl2 ethernet device
$wsl_gw = C:\Windows\System32\wsl.exe -e /bin/bash --noprofile --norc -c "ip -o route show table main default"
# Parses the actual address from the output (gateway)
$wsl_gw = $wsl_gw.split()[2]

$ifindex = Get-NetRoute -DestinationPrefix $wsl_gw/32 | Select-Object -ExpandProperty "IfIndex"
$routemetric = Get-NetRoute -DestinationPrefix $wsl_gw/32 | Select-Object -ExpandProperty "RouteMetric"

# Add route for WSL
route add $wsl_addr mask 255.255.255.255 $wsl_addr metric $routemetric if $ifindex


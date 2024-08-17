import socket
import subprocess
import time


def host_run(args: str) -> tuple:
    """Run shell commands on the host

    Both stdout and stderr are combined for convenience. Additionally,
    some applications may not always respect these streams and may mix
    stdout with stderr. Other parameters used here were added
    specifically with the following in mind.

    `args` is required for all calls and should be a string, or a
    sequence of program arguments. If passing a single string, either
    shell must be True or else the string must simply name the program
    to be executed without specifying any arguments.

    This can be useful if you are using Python primarily for the enhanced
    control flow it offers over most system shells and still want convenient
    access to other shell features such as shell pipes, filename wildcards,
    environment variable expansion, and expansion of ~ to a user’s home
    directory.

    https://docs.python.org/3/library/subprocess.html

    Args:
        args: Arguments to execute.

    Returns:
        Tuple of output and return code.
    """
    res = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True
    )

    return res.stdout, res.returncode


def failsafe(func) -> object:
    """Wraps functions into a try/except condition.

    This allows problematic legacy functions to break without
    interrupting the rest of the code.

    Can be used as a function decorator using @failsafe syntax.

    Args:
        func: Function to wrap

    Returns:
        Function wrapped in a try/except.
    """
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            pass

    return wrapper


def is_host_reachable(host: str, port: int, timeout: int = 3) -> bool:
    """Checks if a host is reachable.

    Tries to establish a socket connection to a port on the target host.
    If the socket connection fails, we assume the host is not reachable.

    For reference if SSH is enabled, port 22 may be used. If RDP is
    enabled, port 3389 may be used.

    Args:
        host: Host ip address.
        port: Host port
        timeout: Time to wait for a connection.

    """
    try:
        # Uses timeout=3 by default to allow plenty of time for a socket to
        # make a connection. This helps ensure we're not returning a false
        # positive if we experience connection issues caused by network
        # latency.
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Try host connection.
        sock.connect((host, port))
        sock.close()
        return True
    except socket.error:
        # Could not connect. Host may be down.
        return False


def wait_for_shutdown(host: str, timeout=120) -> bool:
    """Waits for a host to go offline.

    This is often useful after triggering system power functions
    (OS reboot, AC/DC power cycling, system resets, etc). There's
    often a short delay between the trigger and the system actually
    going offline.

    Automation that performs such actions often relies on the connection
    status to determine what actions to perform. Due to the initial
    delay following a reset action, scripts that rely on pinging the host
    to monitor the reboot status may employ a short sleep time
    beforehand to avoid false positives.

    Rather than hardcoded, arbitrary code delays, this function can be
    used instead where accuracy of shutdown timing and execution time
    is a concern.

    Args:
        host: Host ip address.
        timeout: Time in seconds to wait for the system to shutdown.

    Returns:
        A boolean to indicate whether the system shutdown in the
            expected time. False often indicates the system failed
            to shutdown.
    """
    time_start = time.time()

    while time.time() - time_start <= timeout:
        # Checks ports for SSH and RDP
        if not any([
            is_host_reachable(host, 22),
            is_host_reachable(host, 3389),
        ]):
            return True

    return False


def wait_for_boot(host: str, timeout=300) -> bool:
    """Waits for host to go online.

    Args:
        host: Host ip address.
        timeout: Time in seconds to wait for the system to boot.

    Returns:
        A boolean to indicate whether the system booted in the
            expected time. False often indicates the system failed
            to boot.
    """
    time_start = time.time()

    while time.time() - time_start <= timeout:
        # Checks ports for SSH and RDP
        if any([
            is_host_reachable(host, 22),
            is_host_reachable(host, 3389),
        ]):
            return True

        time.sleep(15)

    return False


def wait_for_tunnel_boot(tunnel, timeout=300) -> bool:
    """Wait for host to go online.

    Very situational, such as BMC reboot operations.

    Args:
        tunnel: Tunnel object from MagicSSH.
        timeout: Time in seconds to wait for tunnel to boot.

    Returns:
        Boolean indicating whether the system booted in the expected
            time.
    """
    time_start = time.time()

    while time.time() - time_start <= timeout:
        tunnel.check_tunnels()
        if tunnel.tunnel_is_up.get(
            tunnel.local_bind_address, False
        ):
            return True

    return False


def wait_for_tunnel_shutdown(tunnel, timeout=120):
    """Wait for host to go online.

    Very situational, such as BMC reboot operations.

    Args:
        tunnel: sshtunnel tunnel object.
        timeout: Time in seconds to wait for tunnel to shutdown

    Returns:
        Boolean indicating whether the system shutdown in the expected
            time.

    """
    time_start = time.time()

    while time.time() - time_start <= timeout:
        tunnel.check_tunnels()
        if not tunnel.tunnel_is_up.get(
            tunnel.local_bind_address, False
        ):
            return True

    return False

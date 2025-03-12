import socket
import subprocess
import time

def is_float(s: str) -> bool:
    """Checks if a given string is a float.

    Args:
        s: String to test

    Returns:
        Boolean indicating whether or not the string
        is a float.
    """
    r = False
    if s.isalpha():
        # Try to catch obvious non-floats.
        pass
    else:
        try:
            float(s)
            r = True
        except:
            pass

    return r


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
    access to other shell features such as shell pipes, filename wild cards,
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

    Can be used as a decorator.

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

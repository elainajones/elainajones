import inspect
import logging
import socket
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


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


def retry(n: int = 1) -> object:
    """Wraps functions with retries on Exception.

    This is a decorator that takes an argument.

    Can be used as a function decorator using @retry syntax.

    Args:
        n: Number of retries to perform.

    Returns:
        Decorator with wrapped function.
    """
    dec_name = inspect.currentframe().f_code.co_name

    def decorator(func) -> object:
        def wrapper(*args, **kwargs):
            retries = n
            while retries > 0:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    exception = e
                    tb = sys.exc_info()[2]

                time.sleep(60)
                retries -= 1

            e = exception
            msg = '\n'.join([
                f'{dec_name} Exception after {n} attempts in '
                f'{func.__module__}.{func.__name__}',
                f"Caused by: {type(e).__name__}: {str(e)}",
            ])
            raise Exception(msg).with_traceback(tb)

        return wrapper
    return decorator


def blackbox_logger(func: object) -> object:
    """Function decorator that logs runtime inputs and outputs.

    This decorator provides the boilerplate necessary to perform
    blackbox code analysis and logging at runtime. This will log
    function kwargs, duration, return (and type), and safely re-
    raises any exceptions that occur when calling the wrapped
    function

    Args:
        func: The function being wrapped (implied when decorating)

    Returns:
        The normal function output.
    """
    dec_name = inspect.currentframe().f_code.co_name

    def wrapper(*args, **kwargs):
        func_args = [*args]
        func_kwargs = {}

        spec = inspect.getfullargspec(func)

        i = 0
        defaults = spec.defaults and [*spec.defaults] or []
        for key in spec.args:
            if len(func_args):
                # Unpack args. This only works because positional arguments
                # must precede keyword arguments.
                val = func_args.pop(0)
                func_kwargs[key] = val
            elif all([
                len(defaults),
                len(spec.args[spec.args.index(key):]) <= len(defaults)
            ]):
                # Unpack defaults. Defaults are a tuple (immutable).
                # This only works because parameters with defaults must follow
                # parameters without defaults.
                func_kwargs[key] = defaults[i]
                i += 1

        # Resolve discrepancies between args, defaults, and kwargs.
        func_kwargs = {**func_kwargs, **kwargs}

        start = time.time()
        tb = ''
        exception = None
        try:
            # Run wrapped function.
            ret = func(**func_kwargs)
        except Exception as e:
            exception = e
            tb = sys.exc_info()[2]

        dur = round(time.time() - start, 4)

        # Search for 'Hello blackbox' in the logs.
        logger.info(
            f'Hello {dec_name} from {func.__module__}.{func.__name__}'
        )
        logger.info(f'kwargs: {func_kwargs}')
        logger.info(f'duration: {dur}')

        if exception:
            e = exception
            msg = '\n'.join([
                f"{dec_name} Exception: {e}",
                f"Caused by: {type(e).__name__}: {str(e)}",
            ])
            logger.error(f'EXCEPTION: {e}')

            raise Exception(msg).with_traceback(tb)

        logger.info(f'return {type(ret)}: {ret}')

        return ret

    return wrapper

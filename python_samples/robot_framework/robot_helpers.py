import inspect

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.BuiltIn import RobotNotRunningError


def robot_args(func: object) -> dict:
    """Function decorator that "pre-fills" runtime arguments.

    RobotFramework keyword function decorator to decouple libaries.
    When used as a decorator, this will set all function args
    matching a specific dictionary key names (our API) to their
    corresponding values. Although designed for use with robot keyword
    functions, the underlying function will remain the same when run
    outside of robot framework.

    Positional arguments passed from robot framework are also
    supported and will be defined in the same order they are
    passed, both in the robot file and the function definition.
    This keeps the number of arguments we need to pass from robot
    framework minimal for test cases with many arguments.

    Args:
        func: The function being wrapped (implied when decorating)

    Returns:
        The normal function return, called with API arguments as
        defaults.

    """
    try:
        robot_kwargs = {}
        # Don't call get_variable_value() in the keyword functions or it
        # will only work from RobotFramework.
        robot_kwargs['example'] = \
            BuiltIn().get_variable_value('${example}')

        def wrapper(*args, **kwargs):
            func_args = [*args]
            func_kwargs = {}

            spec = inspect.getfullargspec(func)

            # Index counter for unpacking args
            i = 0
            for key in spec.args:
                if key in robot_kwargs.keys():
                    val = robot_kwargs.get(key)
                    func_kwargs[key] = val

            for key in spec.args:
                if key in func_kwargs.keys():
                    if len(args) >= len(func_kwargs):
                        # Using @robot_args means you only need to call
                        # the keyword from RobotFramework with minimal,
                        # non-API arguments. Unpacking this is easy
                        # since we know these correspond to any leftover
                        # `spec.args` not already defined.
                        #
                        # When calling from Python, all args are passed
                        # so we need to increment past the API args.
                        # We'll still overwrite API args but this time
                        # the index needs to point to the correct value
                        # to unpack leftover, non-API args.
                        i += 1
                elif len(func_args[i:]):
                    # Unpack args. This only works because positional
                    # arguments must precede keyword arguments. All
                    # positional args here should be any that are left
                    # unmatched with the `spec.args`.
                    #
                    # For other cases where a mix of args and kwargs
                    # are provided, the leftover args are (incorrect)
                    # duplicates of kwargs but are overwritten to use
                    # the actual kwargs.
                    val = func_args[i:][0]
                    func_kwargs[key] = val
                    i += 1

            # Combine unpacked args and kwargs, respectively
            # (func_kwargs is constructed using args). Duplicates
            # between the args and kwargs will be overwritten to use
            # the kwargs.
            func_kwargs = {**func_kwargs, **kwargs}

            return func(**func_kwargs)

    except RobotNotRunningError:
        # We're not running from robot so leave the function unchanged.
        wrapper = func

    return wrapper


@keyword('hello')
@robot_args
def hello(example):
    """Example keyword function

    Args:
        example (str): Example string. Will need to be passed explicitly
            unless called from RobotFramework which will "pre-fill" the
            value.
    """
    print(example)

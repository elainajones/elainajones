import os
import re
import csv
import argparse


def get_robot_files(path: str) -> list:
    """Gets a list of robot files.

    Crawls the project directory to find all the *.robot
    files.

    Args:
        path: String of root directory to start crawling.

    Returns:
        List of robot file paths.

    """
    robot_files = []

    if path.endswith('.robot'):
        robot_files.append(path)

    for root, dirs, files in os.walk(path):
        for i in files:
            if i.endswith('.robot'):
                robot_files.append(os.path.join(root, i))

    return robot_files


def get_test_cases(robot_files: list) -> list:
    """Gets test case data

    Args:
        robot_files: List of robot file paths to parse.

    Returns:
        List of lists containing RobotFramework test case data.
    """
    header_match = re.compile(
        r'\*{3}[\w\s]+?\*{3}',
        re.I
    )

    # List of tuples (id, name, [tags])
    test_case_data = {}
    for path in robot_files:
        if not os.path.exists(path):
            continue

        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()

        suite = os.path.basename(path)
        suite = os.path.splitext(suite)
        suite = suite and suite[0]

        header_list = re.findall(header_match, data)

        settings_section = None
        test_case_section = None
        for i in range(len(header_list)):
            header = header_list[i]
            next_header = i == len(header_list) - 1 and r'\Z'
            next_header = next_header or re.escape(header_list[i + 1])
            if 'settings' in header.lower():
                settings_section = (re.escape(header), next_header)
            elif 'test cases' in header.lower():
                test_case_section = (re.escape(header), next_header)

        if not test_case_section:
            # No test cases, skip further parsing since this
            # is probably a resource file.
            continue

        # Parse settings section.
        settings = re.findall(
            r'{}(.+){}'.format(*settings_section),
            data,
            re.S
        )
        settings = settings and settings[0] or ''

        # Parse test case section.
        test_cases = re.findall(
            r'{}(.+){}'.format(*test_case_section),
            data,
            re.S
        )
        test_cases = test_cases and test_cases[0] or ''

        resource_list = []
        for file in re.findall(
            r'^Resource\s+(.+\.robot)',
            settings,
            re.I | re.M,
        ):
            resource_list.append(file.strip())

        # Use test case names to parse tags
        for test in re.findall(
            r'^[\w\[].+?(?=^[^#\s]|\Z)',
            test_cases,
            re.S | re.M,
        ):
            name = re.findall(r'^[\w\[].+?(?=#|$)', test, re.M)
            name = name[0].strip()

            key_name = '.'.join([
                re.sub(r'[-_]', ' ', suite),
                name,
            ]).lower()

            # Parse out tags from the test block.
            tags = re.findall(r'\[Tags\](.+)', test)
            tags = tags and tags[0] or ''
            # Convert to list.
            tags = tags.split()

            # Parse test case id from name.
            test_id = re.findall(r'tc_[\d_-]+', name, re.I)
            test_id = test_id and test_id[0] or None

            # If no test id, check tags for backup id
            if not test_id:
                test_id = [t for t in tags if t.lower().startswith('tc_')]
                # Get the first id since we only expect 1 anyway.
                test_id = test_id and test_id[0] or None

            if test_case_data.get(key_name):
                print(f"DUPLICATE: '{name}'")

            test_case_data.update({
                key_name: {
                    'suite': suite,
                    'id': test_id,
                    'tags': tags,
                    'name': name,
                    'path': path,
                    'text': test,
                    'resources': resource_list,
                }
            })

    return test_case_data


def get_new_tags():
    """Reads the retag.csv file.

    Expects retag.csv to be in the directory as the script.
    The file retag.csv must contain at least 3 columns for
    test id, test name, and the new tags, respectively. A fourth
    column may be added for tags to remove.

    Both the tags to add and tags to remove columns should contain
    the tags as space-separated strings.

    Returns:
        Dictionary with test name keys and ([new tags], [remove tags])
        as the value.
    """
    # TODO: Support xlsx data.
    tag_dict = {}
    with open('retag.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=',')
        expected = 5
        for row in reader:
            row.extend(['' for i in range(expected - len(row))])

            name = row[1]
            new = row[2]
            remove = row[3]

            tag_dict[name.lower()] = (new, remove)

    return tag_dict


def retag_test_case(path, id_match, name_match, new_tags):
    """Find and retag  test case.

    Both the test case name will be used to find the corresponding
    test case to retag. Failing that, the tag may be used instead
    as a backup for matching in case the name somehow differs, but
    this can be unreliable so should be handled with care.

    Args:
        path (str): Path of robot file to search.
        id_match (str): Test case id matching the test case
            to retag (this can be None if not applicable).
        name_match (str): Test case name matching the test case
            to retag.
        new_tags (list): List of tags to replace existing tags.

    Returns:
        None
    """
    new_data = ""
    with open(path, 'r', encoding='utf-8') as f:
        data = f.read()

    data_start = re.findall(
        r'^.*^\*{3}\s+?test\s+?cases\s+?\*{3}',
        data,
        re.S | re.M | re.I,
    )
    data_start = data_start and data_start[0] or ''
    new_data += data_start + '\n'

    test_cases = re.findall(
        r'^\*{3}\s+?test\s+?cases\s+?\*{3}(.+)',
        data,
        re.S | re.M | re.I,
    )
    test_cases = test_cases and test_cases[0] or ''

    for test in re.findall(
        r'^[\w\[].+?(?=^[^#\s]|\Z)',
        test_cases,
        re.S | re.M,
    ):
        name = re.findall(r'^([\w\[].+)#?', test)
        name = name[0].strip()

        old_tags = re.findall(r'\[Tags\](.+)', test)
        old_tags = old_tags and old_tags[0] or ''

        # Convert to list.
        old_tags = old_tags.split()

        # Parse test case id from name.
        test_id = re.findall(r'tc_[\d_-]+', name, re.I)
        test_id = test_id and test_id[0] or None

        # If no test id, check tags for backup id
        if not test_id:
            test_id = [t for t in old_tags if t.lower().startswith('tc_')]
            # Get the first id since we only expect 1 anyway.
            test_id = test_id and test_id[0] or None

        if name_match.lower() == name.lower():
            # Found corresponding test case by name.
            # Parse out tags from the test block.
            tags = '  '.join(new_tags)
            tags = tags.strip()
            new_test = re.sub(
                r'(?<=\[Tags\])(.+)',
                '  ' + tags,
                test
            )
            new_data += new_test.strip() + '\n\n'
        elif test_id and id_match == test_id:
            # Couldn't find corresponding test case by name. This can
            # happen if the name was changed so use test id as a
            # backup and warn that the name doesn't match.
            print(f'Test case name does not match for {test_id}')
            print(f"Expected: '{name_match}'")
            print(f"Found: '{name}'")
            input('(enter to continue)')
            # Parse out tags from the test block.
            tags = '  '.join(new_tags)
            tags = tags.strip()
            new_test = re.sub(
                r'(?<=\[Tags\])(.+)',
                '  ' + tags,
                test
            )
            new_data += new_test.strip() + '\n\n'
        else:
            new_data += test.strip() + '\n\n'

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_data)


def main(root_path: str) -> None:
    """Makes a CSV with test case data.

    Parses test case information from robot files and makes
    a CSV report.

    Args:
        root_path: Path to robot file root directory.

    Returns:
        None
    """
    robot_files = get_robot_files(root_path)
    test_case_data = get_test_cases(robot_files)

    # Dictionary key with (new tags, remove tags) value.
    name_tags = get_new_tags()

    # List of tuples with new data.
    retag_list = []
    for name, data in test_case_data.items():
        test_name = data.get('name')
        if name_tags.get(test_name.lower()):
            test_tags = data.get('tags', [])

            path = data.get('path')
            test_id = data.get('id')
            tags = test_tags.copy()

            new_tags, remove_tags = name_tags.get(test_name.lower())

            remove_tags = [i.lower() for i in remove_tags.split()]
            new_tags = new_tags.split()

            # Remove tags to remove
            if remove_tags:
                tags = [i for i in tags if i.lower() not in remove_tags]

            # Add new tags
            tags.extend(new_tags)

            # Make sure TC id is in the tags
            if not test_id:
                # input(f"No test id for '{name}'")
                pass
            elif test_id.lower() not in [i.lower() for i in tags]:
                tags.append(test_id)

            # Remove duplicate tags
            unique_tags = []
            for i in tags:
                if i.strip() not in unique_tags:
                    unique_tags.append(i.strip())

            retag_list.append([path, test_id, test_name, unique_tags])

    x = None
    for path, tc_id, name, test_tags in retag_list:
        if x is None:
            x = path
            print(f'DONE {x}')
        elif not path == x:
            print(f'DONE {x}')
            x = path

        print(f'Updating tags for {tc_id} in {path}')
        retag_test_case(path, tc_id, name, test_tags)


if __name__ == '__main__':
    # script_path = os.path.dirname(os.path.realpath(__file__))
    # Use current dir to avoid the need for '--robot-dir' now
    # that this is under `tools/`.
    script_path = os.getcwd()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input',
        default=script_path,
        help='Robot file or project root path'
    )

    args = parser.parse_args()
    root_path = args.input

    main(root_path)

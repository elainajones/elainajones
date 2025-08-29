import os
import re
import argparse
import xml.etree.ElementTree as ET

import dateparser
import xlsxwriter


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


def get_result_files(path):
    """Gets a list of result files.

    Crawls the project directory to find all the *.xml report
    files.

    Args:
        path: String of root directory to start crawling.

    Returns:
        List of xml file paths.
    """
    result_files = []

    for root, dirs, files in os.walk(path):
        for i in files:
            if i.endswith('.xml') and 'output' not in i.lower():
                result_files.append(os.path.join(root, i))

    return result_files


def seconds_to_hms(seconds):
    """Convert seconds to hh:mm:ss format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"


def parse_message(msg):
    """Parses message attribute strings.

    Returns:
        List of separate failure messages.
    """
    if re.findall(
        r'several failures occurred:',
        msg,
        re.S | re.I
    ):
        msg_list = re.findall(r'\d+\)(.+)', msg) or []
        msg_list = [i and i.strip() for i in msg_list]
    elif re.findall(
        r'skipped in.+?(teardown|setup):',
        msg,
        re.S | re.I
    ):
        e = re.findall(
            r'skipped in.+?[teardown|setup]:',
            msg,
            re.S | re.I
        ) or []
        e = e and e[0] or ''

        msg = re.sub(re.escape(e), '', msg, re.S | re.I)

        msg_list = re.split(r'Earlier message:', msg) or []
        # Put the earlier message first, assuming it's last.
        msg_list = msg_list and [msg_list.pop(), *msg_list]
        msg_list = [i and i.strip() for i in msg_list]
    elif re.findall(
        r'(setup|teardown) failed:',
        msg,
        re.S | re.I
    ):
        msg_list = re.findall(
            r'[(?<=setup)|(?<=teardown)] failed:(.+)',
            msg,
            re.S | re.I
        ) or []
        msg_list = [i and i.strip() for i in msg_list]
    elif msg.strip():
        msg_list = [msg.strip()]
    else:
        msg_list = []

    return msg_list


def get_test_results(result_files):
    """Gets test result data

    Args:
        result_files: List of result files paths to read.

    Returns:
    """
    result_list = []
    for path in result_files:
        tree = ET.parse(path)
        root = tree.getroot()

        properties = {}

        for i in root.findall('.//property'):
            a = i.attrib
            properties.update({a['name'].lower(): a['value']})

        bios_version = properties.get('03_bios')

        # Single results file.
        # <testsuite><testsuite><testcase>
        for parent_suite in root.findall('.//testsuite'):
            for suite in parent_suite.findall('testsuite'):
                suite_name = suite.attrib.get('name')
                suite_timestamp = suite.attrib.get('timestamp')
                for test_case in suite.findall('testcase'):
                    test_name = test_case.attrib.get('name')
                    test_time = float(test_case.attrib.get('time'))

                    if not test_name:
                        continue

                    fails = []
                    for i in test_case.findall('failure'):
                        fails.append(i.attrib.get('message'))

                    skips = []
                    for i in test_case.findall('skipped'):
                        skips.append(i.attrib.get('message'))

                    result_list.append({
                        'suite': suite_name,
                        'name': test_name,
                        'fails': fails,
                        'skips': skips,
                        'time': test_time,
                        'timestamp': suite_timestamp,
                        'bios': bios_version,
                    })

            # Single results file (variation)
            # <testsuite><testcase>
            suite_name = parent_suite.attrib.get('name')
            suite_timestamp = parent_suite.attrib.get('timestamp')
            for test_case in parent_suite.findall('testcase'):
                test_name = test_case.attrib.get('name')
                test_time = float(test_case.attrib.get('time'))

                if not test_name:
                    continue

                fails = []
                for i in test_case.findall('failure'):
                    fails.append(i.attrib.get('message'))

                skips = []
                for i in test_case.findall('skipped'):
                    skips.append(i.attrib.get('message'))

                result_list.append({
                    'suite': suite_name,
                    'name': test_name,
                    'fails': fails,
                    'skips': skips,
                    'time': test_time,
                    'timestamp': suite_timestamp,
                    'bios': bios_version,
                })

        # Suite level result file
        # <testcase>
        for test_case in root.findall('testcase'):
            suite_name = root.attrib.get('name')
            suite_timestamp = root.attrib.get('timestamp')

            test_name = test_case.attrib.get('name')
            test_time = float(test_case.attrib.get('time'))

            if not test_name:
                continue
            elif suite_name.lower() == 'tests*':
                # Skip Test/ directory splattering. This is a
                # duplicate xml of the actual logs which won't
                # match anything in our actual robot data.
                break

            fails = []
            for i in test_case.findall('failure'):
                fails.append(i.attrib.get('message'))

            skips = []
            for i in test_case.findall('skipped'):
                skips.append(i.attrib.get('message'))

            result_list.append({
                'suite': suite_name,
                'name': test_name,
                'fails': fails,
                'skips': skips,
                'time': test_time,
                'timestamp': suite_timestamp,
                'bios': bios_version,
            })

    return result_list


def consolidate_results(result_list):
    unique_results = {}
    not_suite = re.compile(r'[-_]')

    for data in result_list:
        test_name = data['name']
        test_suite = data['suite']

        test_fails = data['fails']
        test_skips = data['skips']

        key_name = '.'.join([
            re.sub(not_suite, ' ', test_suite),
            test_name
        ]).lower()

        is_pass = False
        if not any([*test_fails, *test_skips]):
            is_pass = True

        d = dict(data)
        d.update({'pass': is_pass})

        if not unique_results.get(key_name):
            # No data yet so add it.
            unique_results.update({key_name: d})
        elif unique_results.get(key_name, {}).get('pass') is True:
            # Data exists and is passing so this is a duplicate.
            pass
        elif is_pass:
            # Data exists but this failed so replace with a passing run.
            unique_results.update({key_name: d})

    return unique_results


def main():
    # script_path = os.path.dirname(os.path.realpath(__file__))
    # Use current dir to avoid the need for '--robot-dir' now
    # that this is under `tools/`.
    script_path = os.getcwd()
    output_path = get_report_path(script_path)

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--robot-dir',
        default=script_path,
        help='Robot file or project root path'
    )
    parser.add_argument(
        '--input',
        '-i',
        default=[],
        help='Root paths for report discovery',
        nargs='+',
    )
    parser.add_argument(
        '--output',
        '-o',
        default=output_path,
        help='Save path for xlsx report'
    )
    parser.add_argument(
        '--link',
        '-l',
        help='Result link'
    )

    args = parser.parse_args()

    robot_path = args.robot_dir
    result_dirs = args.input
    save_path = args.output
    result_link = args.link

    save_dir = os.path.dirname(save_path)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(os.path.dirname(save_dir), exist_ok=True)
    if not save_path.endswith('.xlsx'):
        # TODO: Edge case for file that exists without .xlsx
        save_path += '.xlsx'
    elif os.path.isdir(save_path):
        save_path = get_report_path(save_path)

    workbook = xlsxwriter.Workbook(save_path)

    robot_files = get_robot_files(robot_path)
    test_case_data = get_test_cases(robot_files)

    result_list = []
    for i in result_dirs:
        # This is the root path only. We need the actual
        # paths to the result xml.
        result_files = get_result_files(i)
        # Read and consolidate results.
        result_list.extend(get_test_results(result_files))

    test_result_data = consolidate_results(result_list)

    headers = [
        'Start Time',
        'Suite',
        'Test Case ID',
        'Test Case Name',
        'Run Results',
        'Fail Count',
        'Failure Reason',
        'Duration',
        'Link',
        'Tags',
    ]
    row_list = [headers]

    test_name_list = []
    for name, data in test_result_data.items():
        time_start = dateparser.parse(data.get('timestamp', ''))
        test_time = seconds_to_hms(data.get('time', ''))
        test_fails = data.get('fails', [])
        test_skips = data.get('skips', [])

        # Use the data from the robot files instead.
        test_suite = test_case_data.get(name).get('suite', '')
        test_name = test_case_data.get(name).get('name', '')
        test_id = test_case_data.get(name).get('id', '')
        test_tags = test_case_data.get(name).get('tags', [])

        test_name_list.append(test_name.lower())
        test_tags = ' '.join(test_tags)

        # Assume there's one failure
        test_fails = test_fails and test_fails[0] or ''
        # Assume there's one skip.
        test_skips = test_skips and test_skips[0] or ''

        test_fails = parse_message(test_fails)
        test_skips = parse_message(test_skips)

        if any(test_fails):
            test_status = 'FAILED'
        elif any(test_skips):
            test_status = 'SKIPPED'
        else:
            # Assume this passed
            test_status = 'PASSED'

        fail_msg = '; '.join([*test_fails, *test_skips])
        fail_count = test_fails and len(test_fails) or ''

        row_list.append([
            time_start,
            test_suite,
            test_id,
            test_name,
            test_status,
            fail_count,
            fail_msg,
            test_time,
            result_link,
            test_tags,
        ])

    worksheet = workbook.add_worksheet()

    x = 0
    y = 0
    for row in row_list:
        worksheet.write_row(y, x, row)
        y += 1

    workbook.close()

    print('Report saved to ' + save_path)


def get_report_path(path):
    n = 0
    name = 'robot_report'

    while os.path.isfile(os.path.join(
        path,
        name + f'_{n}' * (n and 1) + '.xlsx',
    )):
        n += 1

    report_path = os.path.join(
        path,
        name + f'_{n}' * (n and 1) + '.xlsx'
    )

    return report_path


if __name__ == '__main__':
    main()

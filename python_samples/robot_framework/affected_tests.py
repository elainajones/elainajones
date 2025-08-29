import os
import re
import csv
import argparse
from threading import Thread


def get_path_basename(path: str) -> str:
    """Get the path basename

    This is a simple wrapper for os.path.basename() which
    also converts the path separators to those of the running
    OS to ensure both Linux and Windows paths are evaluated
    correctly.

    Args:
        path (str): File path.

    Returns:
        File path basename (the file name).
    """
    # Convert Linux separators for native OS so the basename
    # method works properly on Windows.
    path = path.replace('/', os.sep)
    # Convert Windows separators for native OS so the basename
    # method works properly on Linux.
    path = path.replace('\\', os.sep)

    basename = os.path.basename(path)

    return basename


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


def get_keywords(robot_files: list) -> list:
    """Gets keyword data

    Args:
        robot_files: List of robot file paths to parse.

    Returns:
        List of lists containing RobotFramework keyword data.
    """
    header_match = re.compile(
        r'\*{3}[\w\s]+?\*{3}',
        re.I
    )

    # List of tuples (id, name, [tags])
    keyword_data = {}
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
        keyword_section = None
        for i in range(len(header_list)):
            header = header_list[i]
            next_header = i == len(header_list) - 1 and r'\Z'
            next_header = next_header or re.escape(header_list[i + 1])
            if 'settings' in header.lower():
                settings_section = (re.escape(header), next_header)
            elif 'keywords' in header.lower():
                keyword_section = (re.escape(header), next_header)

        if not keyword_section:
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
        keyword_list = re.findall(
            r'{}(.+){}'.format(*keyword_section),
            data,
            re.S
        )
        keyword_list = keyword_list and keyword_list[0] or ''

        # Parse resources files
        resource_list = []
        for file in re.findall(
            r'^Resource\s+(.+\.robot)',
            settings,
            re.I | re.M,
        ):
            resource_list.append(file.strip())

        # Parse keyword names
        for keyword in re.findall(
            r'^[\w\[].+?(?=^[^#\s]|\Z)',
            keyword_list,
            re.S | re.M,
        ):
            name = re.findall(r'^[\w\[].+?(?=#|$)', keyword, re.M)
            name = name[0].strip()

            key_name = '.'.join([
                re.sub(r'[-_]', ' ', suite),
                name,
            ]).lower()

            if keyword_data.get(key_name):
                print(f"DUPLICATE: '{name}'")

            keyword_data.update({
                key_name: {
                    'suite': suite,
                    'name': name,
                    'path': path,
                    'text': keyword,
                    'resources': resource_list,
                }
            })

    return keyword_data


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


def popularity_contest(data, test_data):
    def __thread(data, name_match, d):
        for v in data.values():
            text = v.get('text', '')
            resources = [get_path_basename(i) for i in v.get('resources', [])]
            p = get_path_basename(v.get('path', ''))

            if not re.findall(name_match, text):
                # Keyword not found.
                continue
            elif path == p:
                d['use_count'] += 1
            elif path in resources:
                d['use_count'] += 1

    updated_data = {}

    for key, val in data.items():
        name = val.get('name', '').lower()
        path = get_path_basename(val.get('path', ''))
        use_count = updated_data.get(key, {}).get('use_count', 0)

        d = dict(val)
        d.update({'use_count': use_count})

        name_match = re.compile(
            r'(?:\s{2,}|\t)' + re.escape(name) + r'(?=\s{2,}|\t|$)',
            re.I
        )

        threads = [
            Thread(target=__thread, args=[data, name_match, d]),
            Thread(target=__thread, args=[test_data, name_match, d]),
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]

        updated_data.update({key: d})

    return updated_data


def update_affected(keyword_list, data):
    """Finds keywords that call those in keyword_list.

    This will check the keyword definition for positive matches
    of keywords from keyword_list. If a keyword is found to
    be affected, this will update the 'affected_by' list with
    the keyword.

    Just because a keyword matches, does not mean the affected keyword
    is identical. The same keyword name can be used more than once when
    defined in different files. This is a dumb function which is not
    aware of these nuances.

    Args:
        keyword_list: List of keywords to look for
        data: Keyword data to update.

    Returns:
        Updated keyword data.
    """
    match_list = []
    for i in keyword_list:
        match_list.append(
            re.compile(
                r'(?:\s{2,}|\t)' + re.escape(i) + r'(?=\s{2,}|\t|$)',
                re.I
            )
        )

    updated_data = {}
    for key, val in data.items():
        affected_by = updated_data.get(key, {})
        affected_by = affected_by.get('affected_by', [])

        text = val.get('text', '')
        for i in range(len(match_list)):
            match = match_list[i]
            if re.findall(match, text):
                affected_by.append(keyword_list[i])

        # Remove duplicates
        affected_by = list(set([i.lower() for i in affected_by]))

        v = dict(val)
        v.update({'affected_by': affected_by})
        updated_data.update({key: v})

    return updated_data


def main() -> None:
    script_path = os.getcwd()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input',
        '-i',
        default=script_path,
        help='Robot file or project root path'
    )
    parser.add_argument(
        '--keyword',
        help='Keyword'
    )
    parser.add_argument(
        '-t',
        '--tags',
        help='Tags',
        default=[],
        nargs='+',
    )

    args = parser.parse_args()
    root_path = args.input
    keyword = args.keyword
    tags = args.tags

    tags = [i.lower() for i in tags]
    robot_files = get_robot_files(root_path)

    keyword_data = get_keywords(robot_files)
    test_case_data = get_test_cases(robot_files)

    affected_keywords = {}
    affected_test_cases = {}

    affected_count = 0
    keyword_blacklist = [keyword and keyword.lower()]
    resource_blacklist = []
    # Since some affected keywords may be called by other keyword, keep
    # iterating to crawl the call stack until we don't find any more
    # affected keywords.
    while keyword and affected_count != len(keyword_blacklist):
        affected_count = len(keyword_blacklist)

        updated_data = update_affected(keyword_blacklist, keyword_data)
        for name, data in updated_data.items():
            if not data.get('affected_by'):
                continue

            keyword_name = data.get('name')
            file_name = get_path_basename(data.get('path', ''))
            resource_list = data.get('resources', [])

            resource_list = [get_path_basename(i) for i in resource_list]

            # Get any existing keyword list to update
            affected_by = affected_keywords.get(name, {})
            affected_by = affected_by.get('affected_by', [])
            # Add new keywords to affected list
            affected_by.extend(data.get('affected_by', []))
            # Remove duplicates and normalize strings
            affected_by = list(set([i.lower() for i in affected_by]))

            if not file_name:
                continue
            elif keyword.lower() in affected_by:
                # First affected keywords.
                keyword_blacklist.append(keyword_name)
                resource_blacklist.append(file_name)
            elif file_name in resource_blacklist:
                # Keyword uses a blacklisted keyword that likely
                # came from the same file.
                keyword_blacklist.append(keyword_name)
            elif any([i in resource_blacklist for i in resource_list]):
                # Keyword uses a blacklisted keyword that likely
                # came from an imported resource.
                keyword_blacklist.append(keyword_name)

            d = dict(data)
            d.update({'affected_by': affected_by})
            affected_keywords.update({name: d})

            # Remove duplicates and normalize strings.
            keyword_blacklist = list(set(
                [i.lower() for i in keyword_blacklist]
            ))

    if keyword:
        updated_data = update_affected(
            keyword_blacklist,
            test_case_data
        )
        for name, data in updated_data.items():
            test_tags = data.get('tags', [])

            if not data.get('affected_by'):
                continue
            elif tags and not all([
                x in [y.lower() for y in test_tags] for x in tags
            ]):
                continue
            affected_test_cases.update({name: data})
    else:
        keyword_data = popularity_contest(keyword_data, test_case_data)

        rank = [(k, v['use_count']) for k, v in keyword_data.items()]
        rank = sorted(rank, key=lambda i: i[1])

        not_name = re.compile(r'(suite|test).+(setup|teardown)', re.I)
        results = []
        for name, count in rank:
            if name and not re.findall(not_name, name):
                results.append((name, count))

        most_common = results[-10:]
        least_common = results[:10]

        most_common.reverse()

        print('Most common')
        for name, count in most_common:
            print(f'{count}\t{name}')

        print('Least common')
        for name, count in least_common[:10]:
            print(f'{count}\t{name}')

    headers = [
        'Suite',
        'Test Case ID',
        'Test Case Name',
        'Tags',
    ]
    row_list = [headers]

    for name, data in affected_test_cases.items():
        test_suite = data.get('suite', [])
        test_id = data.get('id')
        test_name = data.get('name')
        test_tags = data.get('tags', [])

        affected_by = data.get('affected_by', [])

        row_list.append([
            test_suite,
            test_id,
            test_name,
            ' '.join(test_tags)
        ])

        print(f'{test_name}')
        for i in affected_by:
            print(f"\tvia '{i}'")

    with open('affected.csv', 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        for row in row_list:
            writer.writerow(row)

    # for name, data in affected_keywords.items():
    #     keyword_name = data.get('name')
    #     affected_by = data.get('affected_by', [])
    #     print(f'{name}')
    #     for i in affected_by:
    #         print(f"\tvia '{i}'")


if __name__ == '__main__':
    main()

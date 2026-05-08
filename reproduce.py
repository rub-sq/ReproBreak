import argparse
import sys
import json
import os
import subprocess
from pathlib import Path
import sqlite3
import shutil
import time
import docker

from config import LB_PATH, REPRODUCTION_PATH
from create_reproducible_dataset import clone_repo, replace_locator, setup_base_image, run_e2e_tests, TestStatus, \
    reset_repository


def main():
    parser = argparse.ArgumentParser(description='Reproduce environment from locator break')
    parser.add_argument('--locator_id', type=int, required=True,
                        help='Locator_change_id of the locator break to reproduce')
    parser.add_argument('--db', default=LB_PATH,
                        help='Path to SQLite database')
    parser.add_argument('--work_dir', default=REPRODUCTION_PATH,
                        help='Working directory for reproduction (default: ./reproduction)')
    parser.add_argument('--reproduce_break', default=False,
                        help='Reproduce break with old locator (default: False')
    parser.add_argument('--reset', type=str, default=True,
                        help='Reset repository before reproduction (default: True)')

    args = parser.parse_args()

    print("=" * 50)
    print("  Locator Break Reproduction")
    print("=" * 50)
    print()

    repos_path = f'{args.work_dir}/repos'
    if not os.path.exists(repos_path):
        os.mkdir(repos_path)

    # Step 1: Get info from database
    print(f"🔍 Getting info for locator break ID: {args.locator_id}")
    info = get_locator_break_reproduction_info(args.db, args.locator_id)

    if not info:
        print(f"❌ No locator break found with ID: {args.locator_id}")
        sys.exit(1)

    print(f"  Repository: {info['repository_name']}")
    print(f"  Commit: {info['commit_sha']}")
    print()

    # Step 2: Clone repository and checkout commit sha
    repo_name = info["repository_name"].split("/")[-1]
    reproduce_path = f'{repos_path}/{repo_name}'
    repo_path = f'{reproduce_path}/{repo_name}'
    clone_repo(info['repository_name'], repo_path)
    if args.reset:
        reset_repository(repo_path)
    subprocess.call(["git", "-C", repo_path, "checkout", info['commit_sha']])

    # Step 3: Extract reproduce files
    extract_reproduction_files(info['files_json'], reproduce_path, repo_name)

    # Step 4: Setup image
    print("🔧 Setting up Docker image...")
    client = docker.from_env()

    image = f"{repo_name}:{info['commit_sha']}"

    filtered_images = client.images.list(filters={'reference': image})
    if len(filtered_images) < 1:
        image = setup_base_image(client, reproduce_path, info['commit_sha'])
        if image is None:
            print(f"❌ Failed to build Docker image.")
            sys.exit(1)
    else:
        print(f"Docker image already exists. Skipping build.")

    # Step 5: Replace locator
    test_file_path = info['test_file_path']
    absolute_repo_path = os.path.abspath(repo_path)
    if args.reproduce_break:
        print(f"Replacing locator to reproduce break...")
        replace_locator(info["new_locator"], info["old_locator"], info["line_no"], info["test_file_path"], repo_path)

    absolute_test_file_path = f"{absolute_repo_path}/{test_file_path}"

    # Step 6: Run tests
    test_result = run_e2e_tests(
        client,
        image,
        command=f"bash /run_tests.sh /app/{test_file_path}",
        volumes={
            f'{absolute_test_file_path}': {'bind': f'/app/{test_file_path}', 'mode': 'ro'}
        }
    )

    print(f"Locator information")
    print(f"File path: {os.path.abspath(absolute_test_file_path)}")
    print(f"Line number: {info['line_no']}")
    if args.reproduce_break:
        print(f"Locator change: {info['old_locator']} -> {info['new_locator']}")

    if test_result == TestStatus.PASSED:
        print(f"✅ Test passed successfully!")
    elif test_result == TestStatus.FAILED:
        print(f"❌ Test failed!")
    else:
        print(f"⚠️ Test execution resulted in failure: {test_result}")

def get_locator_break_reproduction_info(db_path, locator_id):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    query = """SELECT lc.repository_name, lc.test_file_path, lc.commit_sha, lc.old_locator, lc.new_locator, lc.line_no, rf.json, rf.instructions
            FROM locator_break lb
            INNER JOIN reproduce_files rf ON lb.reproduce_files_id = rf.id
            INNER JOIN locator_change lc ON lb.locator_change_id = lc.id
            WHERE lb.locator_change_id = ?
        """

    cur.execute(query, (locator_id,))

    result = cur.fetchone()
    con.close()

    if not result:
        return None

    return {
        'repository_name': result[0],
        'test_file_path': result[1],
        'commit_sha': result[2],
        'old_locator': result[3],
        'new_locator': result[4],
        'line_no': result[5],
        'files_json': result[6],
        'instructions': result[7],
    }


def extract_reproduction_files(files_json, output_path, repo_name):
    # Clean old files
    script_dir = Path(__file__).parent
    target_path = script_dir / output_path
    repo_path = target_path / repo_name

    for item in target_path.iterdir():
        if item.is_dir() and item.name == repo_name:
            continue
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    print(f"Extracting reproduce files...")

    files = json.loads(json.loads(files_json))
    for filename, content in files.items():
        file_path = os.path.join(output_path, filename)

        with open(file_path, 'w') as f:
            f.write(content)

        print(f"  ✓ {filename}")


if __name__ == "__main__":
    main()
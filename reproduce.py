import argparse
import sys
import json
import os
import subprocess
from pathlib import Path
import sqlite3
import shutil
import time

from config import LB_PATH, REPRODUCTION_PATH


def main():
    parser = argparse.ArgumentParser(description='Reproduce environment from locator break')
    parser.add_argument('--locator_id', type=int, required=True,
                        help='Locator_change_id of the locator break to reproduce')
    parser.add_argument('--db', default=LB_PATH,
                        help='Path to SQLite database')
    parser.add_argument('--work_dir', default=REPRODUCTION_PATH,
                        help='Working directory for reproduction (default: ./reproduction)')
    parser.add_argument('--reproduce_break', default=True,
                        help='Reproduce break with old locator (default: True')

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
    subprocess.call(["git", "-C", repo_path, "checkout", info['commit_sha']])

    # Step 3: Replace locator
    if args.reproduce_break:
        replace_locator(info["new_locator"], info["old_locator"], info["line_no"], info["test_file_path"], repo_path)

    # Step 4: Extract reproduce files
    extract_reproduction_files(info['files_json'], reproduce_path, repo_name)

    if info['instructions']:
        print("*" * 10 + " Instructions " + "*" * 10, )
        print(info['instructions'])

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

def clone_repo(repo_name, repo_path):
    print("Cloning repo: " + repo_name)
    if not os.path.exists(repo_path):
        repo_link = f'https://github.com/{repo_name}.git'
        subprocess.call(["git", "clone", repo_link, repo_path])

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

def replace_locator(old_locator, new_locator, line_no, test_file_path, repo_path):
    file_path = f'{repo_path}/{test_file_path}'

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    target_line = lines[line_no - 1]
    if old_locator not in target_line:
        print("Old locator not found")
    else:
        lines[line_no - 1] = target_line.replace(old_locator, new_locator, 1)

        with open(file_path, 'w') as file:
            file.writelines(lines)

if __name__ == "__main__":
    main()
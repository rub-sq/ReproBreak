import sqlite3
import subprocess
import time
import json
import re
from tqdm import tqdm
import os
import shutil

from config import LB_PATH, REPRODUCTION_PATH
from reproduce import replace_locator, clone_repo


def create_dataset(repo, ready_message):
    """Checks for reproducible locator breaks of repo and adds them to db
    First gets all potential locator breaks for the repo
    Then clones the repo and setups the result folder.
    Then iterates the locator changes to find reproducible locator breaks
    In the end the reporduction files are copied to the result folder

    Parameters:
    ready_message: Log message of application when it succesfully started. Used to determine if the application is ready
    """
    con = sqlite3.connect(LB_PATH)
    cur = con.cursor()
    potential_breaks = get_potential_breaks_for_repo(cur, repo)

    repo_name = repo.split("/")[-1]
    reproduce_path = f'{REPRODUCTION_PATH}/repos/{repo_name}'
    repo_path = f'{reproduce_path}/{repo_name}'

    clone_repo(repo, repo_path)

    reproduction_result_folder = get_reproduction_result_folder(reproduce_path)

    process_breaks(repo_path, reproduce_path, potential_breaks, ready_message, reproduction_result_folder)
    copy_reproduction_files(reproduce_path, reproduction_result_folder)

def get_reproduction_result_folder(reproduce_path):
    """Creates numbered result folder

    Parameters:
    reproduce_path: Path for result folder

    Returns: Path to result folder

    """
    result_folder = f"{reproduce_path}/results"
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
    folder_number = sum(1 for entry in os.scandir(result_folder) if entry.is_dir())
    reproduction_result_folder = f"{result_folder}/{folder_number + 1}"
    return reproduction_result_folder

def extend_reproduction(repo, ready_message):
    """
    Checks for reproducible locator breaks of repo and adds them to db.
    Only runs for the potential locator breaks which are not yet reproducible
    """
    repo_name = repo.split("/")[-1]
    reproduce_path = f'{REPRODUCTION_PATH}/repos/{repo_name}'
    repo_path = f'{reproduce_path}/{repo_name}'
    result_folder = f"{reproduce_path}/results"

    folder_number = sum(1 for entry in os.scandir(result_folder) if entry.is_dir())
    with open(f"{result_folder}/{folder_number}/results.json", "r") as file:
        latest_results = json.load(file)
    remaining = {}
    for commit, commit_info in latest_results.items():
        if not commit_info["is_startable"] or not commit_info["did_setup_e2e"]:
            remaining[commit] = commit_info
        else:
            files = {file_path: file_info for file_path, file_info in commit_info["test_files"].items() if not file_info["tests_startable"]}
            if files:
                remaining[commit] = {
                    "is_startable": True,
                    "did_setup_e2e": True,
                    "test_files": files
                }

    reproduction_result_folder = get_reproduction_result_folder(reproduce_path)

    process_breaks(repo_path, reproduce_path, remaining, ready_message, reproduction_result_folder)
    copy_reproduction_files(reproduce_path, reproduction_result_folder)

def copy_reproduction_files(reproduction_files_folder, reproduction_result_folder):
    for item in os.listdir(reproduction_files_folder):
        src_path = f"{reproduction_files_folder}/{item}"
        if os.path.isfile(src_path):
            shutil.copy2(src_path, reproduction_result_folder)

def save_reproduction_results(reproduction_result_folder, commit_sha, commit_breaks):
    """
    Saves reproduction results to a json file
    """
    reproduction_result_file = f"{reproduction_result_folder}/results.json"
    os.makedirs(reproduction_result_folder, exist_ok=True)
    results = {}
    if os.path.exists(reproduction_result_file):
        with open(reproduction_result_file, "r") as file:
            results = json.load(file)
    results[commit_sha] = commit_breaks
    with open(reproduction_result_file, "w") as file:
        json.dump(results, file, indent=4)

def process_breaks(repo_path, reproduce_path, potential_breaks, ready_message, result_folder):
    """
    1. Iterates all commits
        1. Checkout commit
        2. Start the application
        3. Wait for application to start
        If started:
            4. Run E2E Setup
            If Setup successful:
                5. Iterate test files
                    1. Run tests of file
                    If successful:
                        2. Iterate locator changes
                            1. Replace locator with old locator
                            2. Rerun test
                            If sucessful: Reproducible locator break
                            3. Reset
    """
    for commit_sha, commit_breaks  in tqdm(potential_breaks.items(), desc="Processing commits", position=0):
        subprocess.call(["git", "-C", repo_path, "checkout", commit_sha])
        subprocess.call(["make", "start"], cwd=reproduce_path)
        if wait_for_ready(reproduce_path, ready_message):
            commit_breaks["is_startable"] = True
            commit_breaks["did_setup_e2e"] = run_e2e_setup(reproduce_path)
            if commit_breaks["did_setup_e2e"]:
                for test_file_path, breaks_in_file in tqdm(commit_breaks["test_files"].items(), desc="Testing files", position=1, leave=False):
                    tests_startable, tests_did_pass, tests_error_logs = run_e2e_tests(reproduce_path, test_file_path)
                    breaks_in_file["tests_startable"] = tests_startable
                    breaks_in_file["tests_did_pass"] = tests_did_pass
                    breaks_in_file["error_logs"] = tests_error_logs
                    if breaks_in_file["tests_startable"] and breaks_in_file["tests_did_pass"]:
                        for potential_break in tqdm(breaks_in_file["potential_breaks"], desc="Testing potential breaks", position=2, leave=False):
                            replace_locator(potential_break["new_locator"], potential_break["old_locator"], potential_break["line_no"], test_file_path, repo_path)
                            tests_startable, tests_did_pass, tests_error_logs = run_e2e_tests(reproduce_path, test_file_path)
                            if tests_startable and not tests_did_pass:
                                potential_break["is_reproducible_break"] = True
                            subprocess.call(["git", "-C", repo_path, "reset", "--hard"])
                    elif breaks_in_file["tests_startable"] and not breaks_in_file["tests_did_pass"]:
                        print("Some tests failed")
                    else:
                        print("Tests did not start")
                else:
                    print("Test setup failed")
        else:
            print("Application did not start")

        subprocess.call(["make", "stop"], cwd=reproduce_path)
        subprocess.call(["git", "-C", repo_path, "reset", "--hard"])
        save_reproduction_results(result_folder, commit_sha, commit_breaks)

def run_e2e_setup(dir):
    result = subprocess.run(["make", "setup-e2e"], capture_output=True, text=True, cwd=dir)
    return result.returncode == 0

def run_e2e_tests(dir, file_path = None):
    startable = False
    did_pass = False
    error_logs = ""
    run_args = ['make', 'test']
    if file_path:
        run_args.append(f"SPEC={file_path}")
    result = subprocess.run(run_args, capture_output=True, text=True, cwd=dir)
    stdout = result.stdout
    stderr = result.stderr
    combined = stdout + stderr

    tests_started = bool(re.search(r'Running \d+ tests? using \d+ workers?', combined)) or bool(
        re.search(r'(Run Starting)', combined))

    if result.returncode == 0:
        startable = True
        did_pass = True

    elif tests_started:
        startable = True
    else:
        error_logs = combined

    return startable, did_pass, error_logs

def wait_for_ready(reproduce_path, ready_message):
    """Waits for the application to start

    Parameters:
    ready_message: Log message of application when it succesfully started. Used to determine if the application is ready
    """
    timeout = 600
    interval = 10
    elapsed = 0
    while elapsed < timeout:
        # Check if container is still running
        ps_result = subprocess.run(
            ["docker", "compose", "ps", "-q", "app"],
            capture_output=True,
            text=True,
            cwd=reproduce_path
        )

        if not ps_result.stdout.strip():
            return False

        result = subprocess.run(
            ["docker", "compose", "logs", "app"],
            capture_output=True,
            text=True,
            cwd=reproduce_path
        )

        if ready_message in result.stdout:
            return True

        time.sleep(interval)
        elapsed += interval
    return False

def get_potential_breaks_for_repo(cur, repo_name, commits = None):
    query = f"""SELECT lb.commit_sha, lb.test_file_path, lb.old_locator, lb.new_locator, lb.line_no
                FROM locator_break lb
                WHERE lb.repository_name = ?
    """

    if commits:
        placeholders = ",".join("?" * len(commits))
        query += f" AND lb.commit_sha IN ({placeholders})"
        cur.execute(query, [repo_name] + commits)
    else:
        cur.execute(query, (repo_name,))

    result = {}
    for commit_sha, test_file_path, old_locator, new_locator, line_no in cur.fetchall():
        commit_entry = result.setdefault(commit_sha, {
            "is_startable": False,
            "did_setup_e2e": False,
            "test_files": {},
        })
        commit_entry["test_files"].setdefault(test_file_path, {
            "tests_startable": False,
            "tests_did_pass": False,
            "error_logs": "",
            "potential_breaks": [],
        })["potential_breaks"].append({
            "old_locator": old_locator,
            "new_locator": new_locator,
            "line_no": line_no,
            "is_reproducible_break": False,
        })
    return result
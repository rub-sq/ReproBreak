import sqlite3
import subprocess
import json
import re
import sys
from enum import Enum

import docker
from tqdm import tqdm
import os
import shutil

from config import LB_PATH, REPRODUCTION_PATH
from reproduce import replace_locator, clone_repo

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    DID_NOT_START = "did not start"
    EARLIER_ERROR = "earlier error"
    BROKEN_IMAGE = "broken image"

def create_dataset(repo):
    """Checks for reproducible locator breaks of repo and adds them to db
    First gets all potential locator breaks for the repo
    Then clones the repo and setups the result folder.
    Then iterates the locator changes to find reproducible locator breaks
    In the end the reporduction files are copied to the result folder

    Parameters:
    ready_message: Log message of application when it succesfully started. Used to determine if the application is ready
    """
    repo_name = repo.split("/")[-1]
    reproduce_path = f"{REPRODUCTION_PATH}/repos/{repo_name}"
    repo_path = f"{reproduce_path}/{repo_name}"

    prepare_json(repo, reproduce_path)
    clone_repo(repo, repo_path)

    reproduction_result_folder = get_reproduction_result_folder(reproduce_path)

    reproduction_results = process_breaks(repo_path, reproduce_path, reproduction_result_folder)
    copy_reproduction_files(reproduce_path, reproduction_result_folder)


def prepare_json(repo_name, path):
    con = sqlite3.connect(LB_PATH)
    cur = con.cursor()

    locator_changes = get_potential_breaks_for_repo(cur, repo_name)

    with open(path + "/reproduction.json", "w") as file:
        json.dump(locator_changes, file, indent=4)


def get_potential_breaks_for_repo(cur, repo_name):
    query = f"""SELECT lc.id, lc.commit_sha, lc.test_file_path, lc.old_locator, lc.new_locator, lc.line_no
                FROM locator_change lc
                WHERE lc.repository_name = ?
    """

    cur.execute(query, (repo_name,))

    result = {}
    for locator_change_id, commit_sha, test_file_path, old_locator, new_locator, line_no in cur.fetchall():
        commit_entry = result.setdefault(
            commit_sha,
            {
                "test_files": {},
                "has_error": False,
            },
        )
        commit_entry["test_files"].setdefault(
            test_file_path,
            {
                "status": None,
                "locator_changes": [],
            },
        )["locator_changes"].append(
            {
                "lc.id": locator_change_id,
                "old_locator": old_locator,
                "new_locator": new_locator,
                "line_no": line_no,
                "is_reproducible_break": None,
            }
        )
    return result


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


def extend_reproduction(repo):
    """
    Checks for reproducible locator breaks of repo and adds them to db.
    Only runs for the potential locator breaks which are not yet reproducible
    """
    repo_name = repo.split("/")[-1]
    reproduce_path = f"{REPRODUCTION_PATH}/repos/{repo_name}"
    repo_path = f"{reproduce_path}/{repo_name}"

    reproduction_result_folder = get_reproduction_result_folder(reproduce_path)

    process_breaks(repo_path, reproduce_path, reproduction_result_folder)
    copy_reproduction_files(reproduce_path, reproduction_result_folder)


def copy_reproduction_files(reproduction_files_folder, reproduction_result_folder):
    for item in os.listdir(reproduction_files_folder):
        if not item.endswith(".json"):
            src_path = f"{reproduction_files_folder}/{item}"
            if os.path.isfile(src_path):
                shutil.copy2(src_path, reproduction_result_folder)


def convert_enums(obj):
    if isinstance(obj, TestStatus):
        return obj.value
    elif isinstance(obj, dict):
        return {k: convert_enums(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_enums(item) for item in obj]
    return obj


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
    results[commit_sha] = convert_enums(commit_breaks)
    with open(reproduction_result_file, "w") as file:
        json.dump(results, file, indent=4)


def get_current_results(path):
    json_path = path + "/reproduction.json"
    if os.path.exists(json_path):
        with open(json_path, "r") as file:
            return json.load(file)
    return {}

def get_changes_with_error(path):
    results = get_current_results(path)
    filtered = {}
    for commit_sha, commit_entry in results.items():
        filtered_files = {
            path: file_entry
            for path, file_entry in commit_entry["test_files"].items()
            if file_entry["status"] not in (TestStatus.PASSED, TestStatus.FAILED)
        }
        if filtered_files:
            filtered[commit_sha] = {**commit_entry, "test_files": filtered_files}
    return filtered


def process_breaks(repo_path, reproduce_path, reproduction_result_folder):
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
    client = docker.from_env()
    commits_to_process = get_changes_with_error(reproduce_path)

    for commit_sha, commit_breaks in tqdm(
        commits_to_process.items(),
        desc="Processing commits",
        position=0,
    ):
        subprocess.call(["git", "-C", repo_path, "checkout", commit_sha])
        print("building base image for commit " + commit_sha)
        commit_image = setup_base_image(client, reproduce_path, commit_sha)
        if commit_image is None:
            commit_breaks["has_error"] = True
            for test_file_path, breaks_in_file in commit_breaks["test_files"].items():
                breaks_in_file["status"] = TestStatus.BROKEN_IMAGE
            continue
        for test_file_path, breaks_in_file in tqdm(
            commit_breaks["test_files"].items(),
            desc="Testing files",
            position=1,
            leave=False,
        ):
            if commit_breaks["has_error"]:
                breaks_in_file["status"] = TestStatus.EARLIER_ERROR
                continue
            print("Initial test run for file " + test_file_path)
            status = run_e2e_tests(
                client,
                commit_image,
                f"bash /run_tests.sh /app/{test_file_path}"
            )
            breaks_in_file["status"] = status
            match status:
                case TestStatus.PASSED:
                    for potential_break in tqdm(
                        breaks_in_file["locator_changes"],
                        desc="Testing potential breaks",
                        position=2,
                        leave=False,
                    ):
                        replace_locator(
                            potential_break["new_locator"],
                            potential_break["old_locator"],
                            potential_break["line_no"],
                            test_file_path,
                            repo_path,
                        )

                        absolute_repo_path = os.path.abspath(repo_path)
                        test_result = run_e2e_tests(
                            client,
                            commit_image,
                            command=f"bash /run_tests.sh /app/{test_file_path}",
                            volumes={
                                f'{absolute_repo_path}/{test_file_path}': {'bind': f'/app/{test_file_path}', 'mode': 'ro'}
                            }
                        )

                        reset_repository(repo_path)

                        if test_result == TestStatus.FAILED:
                            potential_break["is_reproducible_break"] = True
                        elif test_result == TestStatus.PASSED:
                            potential_break["is_reproducible_break"] = False
                case TestStatus.FAILED:
                    print("Some tests failed")
                case TestStatus.DID_NOT_START:
                    commit_breaks["has_error"] = True
                    print("Tests could not be started")

        save_reproduction_results(reproduction_result_folder, commit_sha, commit_breaks)
        client.images.remove(commit_image)

    return commits_to_process


def reset_repository(repo_path):
    """Resets the repository to the original state after modifying test files."""
    subprocess.call(["git", "-C", repo_path, "reset", "--hard"])


def run_e2e_tests(client, image, command="bash /run_tests.sh", volumes=None):
    """Run e2e tests in a container and return the test result."""
    container = None
    try:
        container = client.containers.run(
            image=image,
            command=command,
            volumes=volumes,
            detach=True,
            remove=False,
        )

        exit_code = container.wait()["StatusCode"]
        output = container.logs(stream=False)

        return parse_test_result(exit_code, output)

    except Exception as e:
        return TestStatus.DID_NOT_START

    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass


def parse_test_result(exit_code, output):
    """Parse container output to determine test result."""
    combined = output.decode("utf-8", errors="ignore")

    tests_started = bool(
        re.search(r"Running \d+ tests? using \d+ workers?", combined)
    ) or bool(re.search(r"(Run Starting)", combined))

    if tests_started:
        if exit_code == 0:
            return TestStatus.PASSED
        else:
            return TestStatus.FAILED
    else:
        return TestStatus.DID_NOT_START


def setup_base_image(client, reproduce_path, commit_sha):
    """Build the base image for a commit from the Dockerfile."""
    image_tag = f"{reproduce_path.split('/')[-1]}:{commit_sha}"
    try:
        client.images.build(
            path=reproduce_path,
            tag=image_tag,
            rm=True,
        )
        return image_tag
    except Exception:
        return None

if __name__ == "__main__":
    create_dataset(sys.argv[1])

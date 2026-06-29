import json
import sys
from pathlib import Path

from config import REPRODUCTION_PATH

def analyze_results(repo, run_number = None):
    repo_name = repo.split("/")[-1]
    reproduce_path = f"{REPRODUCTION_PATH}/repos/{repo_name}"

    if run_number:
        result_file = f"{reproduce_path}/results/{run_number}/results.json"
    else:
        result_file = f"{reproduce_path}/reproduction.json"

    if not Path(result_file).exists():
        print(f"Error: Result file not found at {result_file}")
        sys.exit(1)

    with open(result_file, "r") as f:
        data = json.load(f)

    commits_with_error = []
    commits_without_error = []
    test_files_with_error = 0
    failing_test_files = 0
    successful_test_files = 0

    reproducible_locator_break = []
    no_locator_break = []

    for commit_sha, commit_breaks in data.items():
        if commit_breaks["has_error"]:
            commits_with_error.append(commit_sha)
        else:
            commits_without_error.append(commit_sha)

        for test_file_path, breaks_in_file in commit_breaks["test_files"].items():
            if breaks_in_file["status"] == "failed":
                failing_test_files += 1
            elif  breaks_in_file["status"] == "passed":
                successful_test_files += 1
            else:
                test_files_with_error += 1

            for locator_change in breaks_in_file["locator_changes"]:
                if locator_change["is_reproducible_break"]:
                    reproducible_locator_break.append(locator_change["lc.id"])
                elif locator_change["is_reproducible_break"] is not None and not locator_change["is_reproducible_break"]:
                    no_locator_break.append(locator_change["lc.id"])



    return {
        "commits_with_error": commits_with_error,
        "commits_without_error": commits_without_error,
        "test_files_with_error": test_files_with_error,
        "failing_test_files": failing_test_files,
        "successful_test_files": successful_test_files,
        "reproducible_locator_break": reproducible_locator_break,
        "no_locator_break": no_locator_break,
    }


def main():

    if len(sys.argv) != 3:
        print("Usage: python analyze_results.py <repo_name> <run_number>")
        print("Example: python analyze_results.py ghiscoding/angular-slickgrid 1")
        sys.exit(1)

    repo_name = sys.argv[1]
    run_number = int(sys.argv[2])

    results = analyze_results(repo_name, run_number)

    print("=" * 60)
    print(f"Analysis Results for {repo_name} (Run {run_number})")
    print("=" * 60)
    print(f"Total commits with error: {len(results['commits_with_error'])}: {results['commits_with_error']}")
    print(f"Total commits without error: {len(results['commits_without_error'])}: {results['commits_without_error']}")
    print(f"Total test files with error: {results['test_files_with_error']}")
    print(f"Total failing test files: {results['failing_test_files']}")
    print(f"Total successful test files: {results['successful_test_files']}")
    print(f"Total reproducible locator breaks: {len(results['reproducible_locator_break'])}: {results['reproducible_locator_break']}")
    print(f"Total no locator breaks: {len(results['no_locator_break'])}: {results['no_locator_break']}")
    print("=" * 60)


def lb_ratio_for_repo(repo_name):
    repo_name = repo_name.split("/")[-1]
    reproduction_json_path = f"{REPRODUCTION_PATH}/repos/{repo_name}/reproduction.json"
    with open(reproduction_json_path, "r") as f:
        result = json.load(f)

    total_lc = 0
    total_inspected_lc = 0
    reproducible_breaks = 0
    no_breaks = 0

    for commit in result.values():
        for test_file in commit["test_files"].values():
            for locator_change in test_file["locator_changes"]:
                total_lc += 1
                is_reproducible_break = locator_change["is_reproducible_break"]
                if is_reproducible_break is not None:
                    total_inspected_lc += 1
                    if is_reproducible_break:
                        reproducible_breaks += 1
                    else:
                        no_breaks += 1

    return total_lc, total_inspected_lc, reproducible_breaks, no_breaks


def lb_ratio_for_all_repos():
    repos_path = f"{REPRODUCTION_PATH}/repos"
    total_lc = 0
    total_inspected_lc = 0
    reproducible_breaks = 0
    no_breaks = 0

    for repo_dir in Path(repos_path).iterdir():
        if repo_dir.is_dir():
            repo_name = repo_dir.name
            lc, lic, rb, nb = lb_ratio_for_repo(repo_name)
            total_lc += lc
            total_inspected_lc += lic
            reproducible_breaks += rb
            no_breaks += nb

    return total_lc, total_inspected_lc, reproducible_breaks, no_breaks

if __name__ == "__main__":
    if len(sys.argv) == 1:
        total_lc, total_inspected_lc, reproducible_breaks, no_breaks = lb_ratio_for_all_repos()
        print(f"Total locator changes: {total_lc}")
        print(f"Total inspected locator changes: {total_inspected_lc}")
        print(f"Reproducible locator breaks: {reproducible_breaks}")
        print(f"No locator breaks: {no_breaks}")
    elif len(sys.argv) == 2:
        total_lc, total_inspected_lc, reproducible_breaks, no_breaks = lb_ratio_for_repo(sys.argv[1])
        print(f"Locator changes for {sys.argv[1]}:")
        print(f"Total locator changes: {total_lc}")
        print(f"Total inspected locator changes: {total_inspected_lc}")
        print(f"Reproducible locator breaks: {reproducible_breaks}")
        print(f"No locator breaks: {no_breaks}")
    else:
        main()
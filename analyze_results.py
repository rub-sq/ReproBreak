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
    test_files_with_error = []
    failing_test_files = []
    successful_test_files = []

    reproducible_locator_break = []
    no_locator_break = []

    for commit_sha, commit_breaks in data.items():
        if commit_breaks["has_error"]:
            commits_with_error.append(commit_sha)
        else:
            commits_without_error.append(commit_sha)

        for test_file_path, breaks_in_file in commit_breaks["test_files"].items():
            if breaks_in_file["status"] == "failed":
                failing_test_files.append(test_file_path)
            elif  breaks_in_file["status"] == "passed":
                successful_test_files.append(test_file_path)
            else:
                test_files_with_error.append(test_file_path)

            for locator_change in breaks_in_file["locator_changes"]:
                if locator_change["is_reproducible_break"]:
                    reproducible_locator_break.append(locator_change["lc.id"])
                elif not locator_change["is_reproducible_break"]:
                    no_locator_break.append(test_file_path)



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
    print(f"Total test files with error: {len(results['test_files_with_error'])}: {results['test_files_with_error']}")
    print(f"Total failing test files: {len(results['failing_test_files'])}: {results['failing_test_files']}")
    print(f"Total successful test files: {len(results['successful_test_files'])}: {results['successful_test_files']}")
    print(f"Total reproducible locator breaks: {len(results['reproducible_locator_break'])}: {results['reproducible_locator_break']}")
    print(f"Total no locator breaks: {len(results['no_locator_break'])}: {results['no_locator_break']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
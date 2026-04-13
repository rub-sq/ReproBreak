import csv
import os
import pandas as pd

from config import OUTPUT_PATH

overview_csv = "overview.csv"
error_overview_csv = "error_overview.csv"

def initiate_repo_overview(result_path):
    overview_path = f'{result_path}/{overview_csv}'
    if not os.path.exists(overview_path):
        print("Initiating repo overview")

        with open(overview_path, "w", newline="", encoding="utf-8") as overview:
            writer = csv.writer(overview)
            writer.writerow(["repository", "amount of test files", "amount of test cases", "amount of commits"])

def add_to_repo_overview(result_path, repo):
    overview_path = f'{result_path}/{overview_csv}'
    print("Adding overview to repo:", repo.repository_name)
    with open(overview_path, "a", newline="", encoding="utf-8") as overview:
        writer = csv.writer(overview)
        writer.writerow([
            repo.repository_name,
            len(repo.test_files),
            repo.get_test_case_amount(),
            repo.get_test_file_changes_amount()
        ])

def initiate_error_overview(result_path):
    error_overview_path = f'{result_path}/{error_overview_csv}'
    print("Initiating error overview")
    with open(error_overview_path, "w", newline="", encoding="utf-8") as error_overview:
        writer = csv.writer(error_overview)
        writer.writerow(["repository", "error message"])

def add_to_error_overview(result_path, repo_name, error):
    error_overview_path = f'{result_path}/{error_overview_csv}'
    print("Adding error to error overview for repo:", repo_name)

    with open(error_overview_path, "a", newline="", encoding="utf-8") as error_overview:
        writer = csv.writer(error_overview)
        writer.writerow([
            repo_name,
            error
        ])
from os.path import exists

from config import REPOS_PATH, DELETE_REPO_AFTER_ANALYZE, CREATE_OVERVIEW, \
    SAVE_TO_DB, START_WITH_CLEAN_DB, REPO_LIST
from export import add_to_repo_overview, initiate_repo_overview, initiate_error_overview, add_to_error_overview
from helpers import *
from database.database import *
import os
from tqdm import tqdm
from datetime import datetime
print("Initializing output csv's")
if not exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)
if not exists(REPOS_PATH):
    os.makedirs(REPOS_PATH)

#Setup for results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
result_path = f'{OUTPUT_PATH}/{timestamp}'
os.makedirs(result_path)
initiate_repo_overview(result_path)
initiate_error_overview(result_path)

#Setup DB
db_path = OUTPUT_PATH
if START_WITH_CLEAN_DB:
    db_path = result_path
db_path = f'{db_path}/locator_break.db'
setup_locator_break_db(db_path)

if not REPO_LIST:
    print("Repo list is empty")
    exit()

repos = []

print("Cloning repos and getting test files")
if not os.path.exists(REPOS_PATH):
    os.makedirs(REPOS_PATH)

# For each repo we do the following:
# 1. Clone/Update Repo
# 2. Get the test files of the current version
# 3. Get all commits and modifications
# 4. Get Locator breaks
# 5. Add to overview and store in db
# 6. Delete Repo
for repo_name in tqdm(REPO_LIST, desc="Processing repos"):
    repo = None
    try:
        clone_repo(repo_name)
        repo_tests = get_tests(repo_name)
        repo = RepositoryTest(repo_name)
        repo.test_files = repo_tests
        repos.append(repo)
        get_commits(repo)
        get_locator_breaks(repo)

        if CREATE_OVERVIEW:
            add_to_repo_overview(result_path, repo)
        if SAVE_TO_DB:
            save_to_db(db_path, repo)
    except Exception as e:
        print("Error in repo:", repo_name)
        add_to_error_overview(result_path, repo_name, e)
    finally:
        if DELETE_REPO_AFTER_ANALYZE:
            delete_repo(repo_name)
        print("Finished repo:", repo_name)

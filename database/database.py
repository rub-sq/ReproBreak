import sqlite3
from pathlib import Path
import os

from config import OUTPUT_PATH

#db_path = Path(__file__).parent.parent / OUTPUT_PATH / "locator_break.db"
#result_db_path = Path(__file__).parent.parent / "current_results" / "locator_break.db"

def get_repos(db):
    print('Getting repository_names from DB')
    con = sqlite3.connect(db)
    cur = con.cursor()

    cur.execute(f'SELECT DISTINCT repository_name from gui_testing_test_details WHERE ('
                f'is_cypress_js = 1 OR is_cypress_ts = 1 OR '
                f'is_playwright_js = 1 OR is_playwright_ts = 1 OR is_playwright_java = 1 OR is_playwright_py = 1 OR '
                f'is_puppeteer_js = 1 OR is_puppeteer_ts = 1 OR is_puppeteer_py = 1)')
    repos = cur.fetchall()

    return [repo[0] for repo in repos]

def get_test_from_db(db, repo_names):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    placeholders = ','.join('?' for _ in repo_names)

    query = (f"SELECT repository_name, test_path, number_of_tests "
             f"FROM gui_testing_test_details "
             f"WHERE repository_name IN ({placeholders}) "
             f"AND (is_selenium_java = 0 AND is_selenium_js = 0 AND is_selenium_ts = 0 AND is_selenium_py = 0)")

    cur.execute(query, repo_names)

    repos = cur.fetchall()

    return repos

def setup_locator_break_db(db_path):
    print('Setting up locator_break_db')
    con = sqlite3.connect(db_path)

    sql_script = Path(__file__).parent / "schema.sql"

    with open(sql_script, "r", encoding="utf-8") as f:
        sql_script = f.read()

    con.executescript(sql_script)

    con.commit()
    con.close()

def save_to_db(db_path, repo):
    print("Saving repo to db: " + repo.repository_name)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    insert_repository(cur, repo.repository_name)
    con.commit()
    insert_test_files(cur, repo)
    con.commit()
    insert_test_file_commits(cur, repo.test_files, repo.repository_name)
    con.commit()
    insert_git_commits(cur, repo)
    con.commit()
    insert_locator_breaks(cur, repo)
    con.commit()

    con.close()

def insert_repository(cur, repository_name):
    try:
        cur.execute("INSERT INTO repository (name) VALUES (?)", (repository_name,))
    except sqlite3.IntegrityError:
        print(f"Repository '{repository_name}' already exists.")

def insert_test_files(cur, repo):
    test_file_tuples = [(test_file.test_path, test_file.number_of_tests, repo.repository_name) for test_file in repo.test_files]

    cur.executemany("INSERT OR IGNORE INTO test_file (file_path, number_of_tests, repository_name) VALUES (?, ?, ?)", test_file_tuples)

def insert_test_file_commits(cur, test_files, repository_name):
    test_file_commit_tuples = []
    for test_file in test_files:
        for commit in test_file.commits:
            test_file_commit_tuples.append((test_file.test_path, commit.fix_commit, repository_name))

    cur.executemany("INSERT OR IGNORE INTO test_file_commit (test_file_path, commit_sha, repository_name) VALUES (?, ?, ?)", test_file_commit_tuples)

def insert_git_commits(cur, repo):
    git_commit_tuples = [(commit.sha, commit.commit_date, commit.previous_sha, repo.repository_name) for commit in repo.commits]

    cur.executemany("INSERT OR IGNORE INTO git_commit (sha, commit_date, previous_sha, repository_name) VALUES (?, ?, ?, ?)", git_commit_tuples)

def insert_locator_breaks(cur, repo):
    locator_break_tuples = [(lb.new_locator, lb.old_locator, repo.repository_name, lb.test_file_path, lb.commit_pair.fix_commit, lb.line_no, lb.framework) for lb in repo.locator_breaks]
    cur.executemany("INSERT OR IGNORE INTO locator_change (new_locator, old_locator, repository_name, test_file_path, commit_sha, line_no, framework) VALUES (?, ?, ?, ?, ?, ?, ?)", locator_break_tuples)

def get_framework_for_repo(db_path, repo_name):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    query = "SELECT DISTINCT framework FROM test_file WHERE repository_name = ?"
    args = (repo_name,)
    cur.execute(query, args)

    frameworks = cur.fetchall()

    return [framework[0] for framework in frameworks]


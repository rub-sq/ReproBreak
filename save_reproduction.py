import sqlite3
import json
import os

from config import LB_PATH, REPRODUCTION_PATH

def store_reproduction_in_db(repo):
    """Stores reproducible locator breaks in database
    Sorts results folders then iterates them.
    For each folder the reproduction files are stores in the db.
    Stores each reproducible locator break with the id of the corresponding reproduce files
    """
    con = sqlite3.connect(LB_PATH)
    cur = con.cursor()

    repo_name = repo.split("/")[-1]
    reproduce_results_path = f'{REPRODUCTION_PATH}/repos/{repo_name}/results'

    folders = sorted(
        [f for f in os.listdir(reproduce_results_path) if os.path.isdir(os.path.join(reproduce_results_path, f))],
        key=lambda x: int(x)
    )


    for folder in folders:
        folder_path = os.path.join(reproduce_results_path, folder)
        result_path = os.path.join(folder_path, "results.json")

        with open(result_path, "r") as file:
            result = json.load(file)

        reproduction_files = read_files_to_json(folder_path)
        reproduction_file_id = insert_reproduction_files(con, cur, reproduction_files)

        reproducable_locator_breaks = []
        for commit, commit_info in result.items():
            for file_path, file_info in commit_info["test_files"].items():
                for potential_break in file_info["potential_breaks"]:
                    if potential_break["is_reproducible_break"]:
                        locator_change_id = get_locator_change_id(cur, repo, commit, file_path, potential_break["old_locator"], potential_break["new_locator"], potential_break["line_no"])
                        reproducable_locator_breaks.append(locator_change_id)
        store_locator_breaks(cur, reproduction_file_id, reproducable_locator_breaks)

    con.close()

def get_locator_change_id(cur, repo, commit, file_path, old_locator, new_locator, line_no):
    query = """SELECT id from locator_change
        WHERE repository_name = ? AND commit_sha = ? AND test_file_path = ? AND old_locator = ? AND new_locator = ? AND line_no = ?
    """

    cur.execute(query, (repo, commit, file_path, old_locator, new_locator, line_no))

    return cur.fetchone()[0]

def read_files_to_json(files_path):
    files_dict = {}

    for filename in os.listdir(files_path):
        if filename == "results.json":
            continue
        file_path = os.path.join(files_path, filename)
        if os.path.isdir(file_path):
            continue
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            files_dict[filename] = content

    return json.dumps(files_dict)

def insert_reproduction_files(con, cur, json_files):
    cur.execute("INSERT INTO reproduce_files (json) VALUES (?)", (json.dumps(json_files),))
    reproduce_files_id = cur.lastrowid
    con.commit()

    return reproduce_files_id

def store_locator_breaks(cur, reproduction_files_id, locator_change_ids):
    locator_breaks = [(reproduction_files_id, locator_change_id) for locator_change_id in locator_change_ids]

    query = """
        INSERT INTO locator_break (reproduce_files_id, locator_change_id)
        VALUES (?, ?)
    """

    cur.executemany(query, locator_breaks)
    cur.connection.commit()
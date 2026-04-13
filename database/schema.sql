PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reproduce_files(
    id INTEGER PRIMARY KEY,
    json TEXT NOT NULL,
    instructions TEXT
);

CREATE TABLE IF NOT EXISTS locator_change(
    id INTEGER PRIMARY KEY,
    new_locator TEXT NOT NULL,
    old_locator TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    test_file_path TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    framework TEXT,
    FOREIGN KEY (repository_name) REFERENCES repository(name),
    FOREIGN KEY (commit_sha, repository_name) REFERENCES git_commit(sha, repository_name),
    FOREIGN KEY (test_file_path, repository_name) REFERENCES test_file(file_path, repository_name)
);

CREATE TABLE IF NOT EXISTS git_commit(
    sha TEXT NOT NULL,
    commit_date TEXT NOT NULL,
    previous_sha TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    PRIMARY KEY (sha, repository_name),
    FOREIGN KEY (repository_name) REFERENCES repository(name)
);

CREATE TABLE IF NOT EXISTS test_file(
    file_path TEXT NOT NULL,
    number_of_tests INT NOT NULL,
    repository_name TEXT NOT NULL,
    PRIMARY KEY (file_path, repository_name),
    FOREIGN KEY (repository_name) REFERENCES repository(name)
);

CREATE TABLE IF NOT EXISTS repository(
    name TEXT PRIMARY KEY NOT NULL
);

CREATE TABLE IF NOT EXISTS test_file_commit(
    test_file_path TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    PRIMARY KEY (test_file_path, commit_sha, repository_name),
    FOREIGN KEY (test_file_path, repository_name) REFERENCES test_file(file_path, repository_name),
    FOREIGN KEY (commit_sha, repository_name) REFERENCES git_commit(sha, repository_name)
);

CREATE TABLE IF NOT EXISTS locator_break(
    locator_change_id INTEGER NOT NULL,
    reproduce_files_id INTERGER NOT NULL,
    PRIMARY KEY (locator_change_id, reproduce_files_id),
    FOREIGN KEY (locator_change_id) REFERENCES locator_change(id),
    FOREIGN KEY (reproduce_files_id) REFERENCES reproduce_files(id)
);

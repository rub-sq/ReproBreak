class RepositoryTest:
    def __init__(self, repository_name):
        self.repository_name = repository_name
        self.test_files = []
        self.commits = []
        self.locator_breaks = []

    def __str__(self):
        tests = ""
        for test_file in self.test_files:
            tests += f'\n\t{test_file}'
        return f'{self.repository_name}: {tests}'

    def get_test_case_amount(self):
        return sum(test_file.number_of_tests for test_file in self.test_files)

    def get_test_file_changes_amount(self):
        return sum(len(test_file.commits) for test_file in self.test_files)

class TestFile:
    def __init__(self, test_path, number_of_tests):
        self.test_path = test_path
        self.number_of_tests = number_of_tests
        self.commits = []

    @classmethod
    def detailed(cls, test_path, number_of_tests, language, framework):
        test_file = TestFile(test_path, number_of_tests)
        test_file.language = language
        test_file.framework = framework
        return test_file

    def __str__(self):
        commits = ""
        for commit in self.commits:
            commits += f'\n\t\t{commit}'
        return f'{self.test_path}: {self.number_of_tests} tests: {commits}'

class CommitPair:
    def __init__(self, fix_commit, previous_commit):
        self.fix_commit = fix_commit
        self.previous_commit = previous_commit

    def __str__(self):
        return f'{self.fix_commit}, Previous: {self.previous_commit}'

class Commit:
    def __init__(self, sha, commit_date, previous_sha):
        self.sha = sha
        self.commit_date = commit_date
        self.previous_sha = previous_sha

    def __str__(self):
        return f'{self.sha}, Commit: {self.commit_date}, Previous: {self.previous_sha}'

class LocatorBreak:
    def __init__(self, new_locator, old_locator, line_no, commit_pair, test_file):
        self.new_locator = new_locator
        self.old_locator = old_locator
        self.commit_pair = commit_pair
        self.test_file_path = test_file
        self.line_no = line_no
        self.test_case = None

    def __str__(self):
        return f'{self.test_file_path}: {self.commit_pair}\n\t{self.old_locator} -> {self.new_locator}'
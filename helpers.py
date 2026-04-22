import re
import os
import shutil
import subprocess
from git import Repo
from pathlib import Path
from unidiff import PatchSet

from analyze_locator_changes import strip_assertions
from repository_model import CommitPair, TestFile, RepositoryTest, Commit, LocatorBreak

repos_path = Path(__file__).parent / "repos"


# function
def get_repo_with_tests(repo_name):
    if not os.path.exists("repos"):
        os.makedirs("repos")

    clone_repo(repo_name)
    repo_tests = get_tests(repo_name)
    repo = RepositoryTest(repo_name)
    repo.test_files = repo_tests

    return repo


# helper
def detect_language_from_extension(filename):
    """
    Return 'java', 'js', 'ts', or 'py' based on file extension.
    (.tsx is treated as 'ts' here.)
    """
    if filename.endswith(".java"):
        return "java"
    elif filename.endswith(".js") or filename.endswith(".jsx"):
        return "js"
    elif filename.endswith(".ts") or filename.endswith(".tsx"):
        return "ts"
    elif filename.endswith(".py"):
        return "py"
    return None


# helper
def count_tests_in_text(text, language):
    """
    Count individual test cases by language:
    - Java: count '@Test'
    - JS/TS: count 'it(' or 'test(' only (not 'describe(')
    - Python: count 'def test_'
    """
    if not text:
        return 0

    if language == "java":
        return len(re.findall(r'@Test\b', text))

    elif language in ["js", "ts"]:
        # Only count test( or it(, not describe(
        return len(re.findall(r'\b(it|test)\s*\(', text))

    elif language == "py":
        return len(re.findall(r'\bdef\s+test_', text))

    return 0


# helper
def detect_framework_from_text(text, language):
    """
    Detect a web-testing framework usage inside text.
    Returns 'playwright', 'puppeteer' or  'cypress' (or None).
    Only returns non-None if both a framework import and at least one test indicator exist.
    """
    if not text:
        return None

    framework = None
    is_test = False

    if language == "java":
        if re.search(r'@Test\b', text):
            is_test = True
        if re.search(r'import\s+com\.microsoft\.playwright\b', text):
            framework = "playwright"

    elif language == "js":
        if re.search(r'\b(it|test|describe)\s*\(', text):
            is_test = True

        # Cypress
        if re.search(r"require\(['\"]cypress['\"]\)", text) or \
           re.search(r'from\s+[\'"]cypress[\'"]', text) or \
           re.search(r'import\s+.*[\'"]cypress[\'"]', text) or \
           re.search(r'///\s*<reference\s+types\s*=\s*["\']cypress["\']\s*/>', text) or \
           re.search(r'\bcy\.\w', text):
            framework = "cypress"

        # Puppeteer
        elif re.search(r"require\(['\"]puppeteer['\"]\)", text) or \
                re.search(r'from\s+[\'"]puppeteer[\'"]', text) or \
                re.search(r'import\s+.*[\'"]puppeteer[\'"]', text) or \
                re.search(r'\bpuppeteer\b', text):
            framework = "puppeteer"

        # Playwright
        elif re.search(r"require\(['\"]@playwright/test['\"]\)", text) or \
             re.search(r'from\s+[\'"]@playwright/test[\'"]', text) or \
             re.search(r'import\s+.*[\'"]@playwright/test[\'"]', text) or \
             re.search(r'\bplaywright\b', text):
            framework = "playwright"

    elif language == "ts":
        if re.search(r'\b(it|test|describe)\s*\(', text):
            is_test = True

        # Cypress
        if re.search(r"require\(['\"]cypress['\"]\)", text) or \
           re.search(r'from\s+[\'"]cypress[\'"]', text) or \
           re.search(r'import\s+.*[\'"]cypress[\'"]', text) or \
           re.search(r'///\s*<reference\s+types\s*=\s*["\']cypress["\']\s*/>', text) or \
           re.search(r'\bcy\.\w', text):
            framework = "cypress"

        # Puppeteer
        elif re.search(r"require\(['\"]puppeteer['\"]\)", text) or \
                re.search(r'from\s+[\'"]puppeteer[\'"]', text) or \
                re.search(r'import\s+.*[\'"]puppeteer[\'"]', text) or \
                re.search(r'\bpuppeteer\b', text):
            framework = "puppeteer"

        # Playwright
        elif re.search(r"require\(['\"]@playwright/test['\"]\)", text) or \
             re.search(r'from\s+[\'"]@playwright/test[\'"]', text) or \
             re.search(r'import\s+.*[\'"]@playwright/test[\'"]', text) or \
             re.search(r'\bplaywright\b', text):
            framework = "playwright"

    elif language == "py":
        if re.search(r'\bdef\s+test_', text):
            is_test = True

        # Playwright-Python
        if re.search(r'import\s+playwright\b', text) or \
           re.search(r'from\s+playwright\b', text):
            framework = "playwright"

        # Puppeteer-Python
        if re.search(r'import\s+puppeteer\b', text) or \
           re.search(r'from\s+puppeteer\b', text):
            framework = "puppeteer"

    return framework if (framework and is_test) else None


# def detect_locator_breaks(patch_text, language):
#     """
#     Determine if a diff patch contains a LOCATOR break:
#       - JS/TS/Cypress/Playwright: patterns like cy.get(...), page.locator(...), page.$(...), etc.
#       - Python/Playwright: page.query_selector, etc.
#     Returns True if any locator‐like string is present in the patch.
#     """
#     if not patch_text:
#         return False

#     patterns = [
#         r"cy\.get\s*\(",
#         r"page\.(locator|\$)\s*\(",
#         r"document\.querySelector",
#         r"document\.querySelectorAll",
#         r"page\.query_selector",
#         r"locator\s*\("               # generic locator usage
#     ]
#     for pat in patterns:
#         if re.search(pat, patch_text):
#             return True
#     return False


def clone_repo(repo_name, path=None):
    """Clones or updates the repo

    Parameters:
    repo_name: name of the repo
    path: path to clone to

    """
    print("Cloning repo: " + repo_name)
    repo_path = path if path else f'{repos_path}/{repo_name}'
    if not os.path.exists(repo_path):
        repo_link = f'https://github.com/{repo_name}.git'
        subprocess.call(["git", "clone", repo_link, repo_path])
    else:
        subprocess.call(["git", "-C", repo_path, "pull"])


def delete_repo(repo_name):
    print("Deleting repo: " + repo_name)
    repo_path = f'{repos_path}/{repo_name}'
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)


def get_commits(repo):
    """Gets commits from repo and stores which test files are edit in each commit

    Parameters:
    repo: RepositoryTest

    """
    print("Getting commits from repo:", repo.repository_name)
    repo_path = f'{repos_path}/{repo.repository_name}'

    commit_history = subprocess.run(
        ["git", "-C", repo_path, "log", "--name-status", "--pretty=format:hash:%H%ndate:%as", "--no-renames"],
        capture_output=True, text=True, check=True)

    file_commits = {}
    file_paths = [test_file.test_path for test_file in repo.test_files]
    for file_path in file_paths:
        file_commits[file_path] = []
    current_commit_hash = None
    previous_commit_hash = None
    flags = []
    commit_date = None

    for line in commit_history.stdout.splitlines():
        if not line.strip():
            continue

        if line.startswith("hash:"):
            previous_commit_hash = current_commit_hash
            current_commit_hash = line.removeprefix("hash:")
            commit_pair = CommitPair(previous_commit_hash, current_commit_hash)
            if commit_date is not None:
                commit = Commit(previous_commit_hash, commit_date, current_commit_hash)
                repo.commits.append(commit)
            for file_path in flags:
                file_commits[file_path].append(commit_pair)
            flags = []
        elif line.startswith("date:"):
            commit_date = line.removeprefix("date:")
        else:
            status, file_path = line.split(maxsplit=1)
            if status == "M" and file_path in file_paths:
                flags.append(file_path)
    for file_path in flags:
        commit_pair = CommitPair(previous_commit_hash, current_commit_hash)
        file_commits[file_path].append(commit_pair)

    for test_file in repo.test_files:
        test_file.commits = file_commits[test_file.test_path]


def get_all_repo_files(repo_name):
    """Get all repo files

    Parameters:
    repo_name: name of the repo

    """
    repo_path = f'{repos_path}/{repo_name}'
    repo = Repo(repo_path)
    all_repo_paths = [file.path for file in repo.tree().traverse() if file.type == "blob"]
    return all_repo_paths


def get_tests(repo_name):
    """Get all test files for repo
    All files are iterated
    First the language of the file is detected.
    If the file is python, js, ts or java, file endings are checked if it is a test file.


    Parameters:
    repo_name: name of the repo
    """
    print("Getting tests for repo: " + repo_name)
    files = get_all_repo_files(repo_name)
    test_files = []
    for path in files:
        lang = detect_language_from_extension(path)
        if not lang:
            continue

        # 1) Filename-based rules first. Only count if framework+test verified:
        if lang == "js":
            if path.endswith(".spec.js") or path.endswith(".test.js") \
                    or path.endswith(".spec.jsx") or path.endswith(".test.jsx"):
                content = get_file_content(repo_name, path)
                framework = detect_framework_from_text(content, lang)
                if framework:
                    cnt = count_tests_in_text(content, lang)
                    test_file = TestFile.detailed(path, cnt, lang, framework)
                    test_files.append(test_file)
                continue

        elif lang == "ts":
            if path.endswith(".spec.ts") or path.endswith(".test.ts") \
                    or path.endswith(".spec.tsx") or path.endswith(".test.tsx"):
                content = get_file_content(repo_name, path)
                framework = detect_framework_from_text(content, lang)
                if framework:
                    cnt = count_tests_in_text(content, lang)
                    test_file = TestFile.detailed(path, cnt, lang, framework)
                    test_files.append(test_file)
                continue

        elif lang == "java":
            if path.endswith("Test.java") or path.endswith("Tests.java"):
                content = get_file_content(repo_name, path)
                framework = detect_framework_from_text(content, lang)
                if framework:
                    cnt = count_tests_in_text(content, lang)
                    test_file = TestFile.detailed(path, cnt, lang, framework)
                    test_files.append(test_file)
                continue

        elif lang == "py":
            if os.path.basename(path).startswith("test_") and path.endswith(".py"):
                content = get_file_content(repo_name, path)
                framework = detect_framework_from_text(content, lang)
                if framework:
                    cnt = count_tests_in_text(content, lang)
                    test_file = TestFile.detailed(path, cnt, lang, framework)
                    test_files.append(test_file)
                continue

        # 2) Fallback: any other file—only if framework imported + test found
        content = get_file_content(repo_name, path)
        framework = detect_framework_from_text(content, lang)
        if framework:
            cnt = count_tests_in_text(content, lang)
            test_file = TestFile.detailed(path, cnt, lang, framework)
            test_files.append(test_file)

    return test_files


def get_file_content(repo_name, file_path):
    full_path = f'{repos_path}/{repo_name}/{file_path}'
    content = Path(full_path).read_text()

    return content


def get_locator_breaks(repo):
    """Get all locator breaks
    Iterates all test files and commit pairs
    Detects locator breaks through regex

    Parameters:
    repo: RepositoryTest

    """
    print("Getting locator breaks for repo:", repo.repository_name)
    for test_file in repo.test_files:
        for commit_pair in test_file.commits:
            repo.locator_breaks.extend(get_locator_break_for_commit_in_file(repo.repository_name, test_file.test_path, commit_pair))


patterns = [
    re.compile(r"cy\.get\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"cy\.contains\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"cy\.find\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"cy\.getByTestId\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.locator\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.getByText\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.getByTestId\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.getByRole\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.\$\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.\$\$\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.\$eval\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.waitForSelector\((.+?)\)(?=[;.\s]|$)"),
    re.compile(r"page\.click\((.+?)\)(?=[;.\s]|$)"),
]


def get_potential_locator_from_line(line):
    for pattern in patterns:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def get_locator_break_for_commit_in_file(repo_name, file_path, commit):
    """Get locator breaks for commit in file
    First gets the patchset of testfile for the commit and the commit before
    Goes through each hunk line by line.
    Finds a locator by checking if first a line containing a locator is removed and then a line containing a locator is added

    Parameters:
    repo_name: Name of repository
    file_path: Path to test file relative to repo
    commit: Commit that fixed the locator

    Returns: List of LocatorBreaks
    """
    patchset = get_patchset_for_commit_pair_in_file(repo_name, file_path, commit)
    locator_breaks = []

    for patchedFile in patchset:
        lang = detect_language_from_extension(patchedFile.path)
        content = get_file_content(repo_name, patchedFile.path)
        framework = detect_framework_from_text(content, lang)
        for hunk in patchedFile:
            invalid = False
            old_locator = None
            for line in hunk:
                if invalid:
                   if line.is_added:
                       invalid = False
                else:
                    potential_locator = get_potential_locator_from_line(line.value.strip())
                    if potential_locator:
                        if old_locator is not None and line.is_added and old_locator != potential_locator:
                            if strip_assertions(old_locator) != strip_assertions(potential_locator):
                                locator_breaks.append(LocatorBreak(potential_locator, old_locator, line.target_line_no, commit, file_path, framework))
                            old_locator = None
                        elif line.is_removed:
                            if old_locator is None:
                                old_locator = potential_locator
                            else:
                                invalid = True
                        else:
                            old_locator = None
                    else:
                        old_locator = None

    return locator_breaks


def get_patchset_for_commit_pair_in_file(repo_name, file_path, commit):
    repo_path = f'repos/{repo_name}'
    #git returns the diff for the commit and the commit before for a filepath
    diff = subprocess.run(
        ["git", "-C", repo_path, "diff", f'{commit.fix_commit}~', commit.fix_commit, file_path],
        capture_output=True,
        text=True,
        check=True
    )

    return PatchSet(diff.stdout)

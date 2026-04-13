from unidiff import PatchSet
import subprocess
import re

from helpers import detect_language_from_extension, get_file_content, detect_framework_from_text
from repository_model import LocatorBreak

CHAIN_PATTERN = r"(?:\.(?:contains|find|closest|filter|children|parent|siblings|first|last|eq|next|prev|within)\(.*?\))*"


patterns = [
    re.compile(r"cy\.get\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"cy\.contains\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"cy\.find\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"cy\.getByTestId\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),

    re.compile(r"page\.locator\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.getByText\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.getByTestId\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.getByRole\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),

    re.compile(r"page\.\$\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.\$\$\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.\$eval\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.waitForSelector\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)"),
    re.compile(r"page\.click\((.+?)\)" + CHAIN_PATTERN + r"(?=[;.\s]|$)")
]

def get_locator_break_for_commit_in_file(repo_name, file_path, commit):
    patchset = get_patchset_for_commit_pair_in_file(repo_name, file_path, commit)
    locator_breaks = []

    for patchedFile in patchset:
        lang = detect_language_from_extension(patchedFile)
        content = get_file_content(repo_name, patchedFile)
        framework = detect_framework_from_text(content, lang)
        for hunk in patchedFile:
            old_locator = None
            for line in hunk:
                potential_locator = get_potential_locator_from_line(line.value.strip())
                if potential_locator:
                    if old_locator is not None and line.is_added and old_locator != potential_locator:
                        locator_breaks.append(LocatorBreak(potential_locator, old_locator, line.target_line_no, commit, file_path))
                        old_locator = None
                    elif line.is_removed:
                        old_locator = potential_locator
                    else:
                        old_locator = None
                else:
                    old_locator = None

    return locator_breaks


def get_patchset_for_commit_pair_in_file(repo_name, file_path, commit):
    repo_path = f'repos/{repo_name}'
    diff = subprocess.run(
        ["git", "-C", repo_path, "diff", f'{commit.fix_commit}~', commit.fix_commit, file_path],
        capture_output=True,
        text=True,
        check=True
    )

    return PatchSet(diff.stdout)

def get_potential_locator_from_line(line):
    for pattern in patterns:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None
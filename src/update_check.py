"""Checks GitHub for a newer release of Mantella when it starts.

Someone on a normal release is only told about newer normal releases. Someone on a pre-release (eg 0.17.0-alpha.3) is
told about anything newer, pre-releases included. Only GitHub's public list of releases is requested, nothing is sent along."""
import re
import threading
from dataclasses import dataclass
import requests
import src.utils as utils

logger = utils.get_logger()

GITHUB_REPOSITORY = 'wheat32/Mantella'
RELEASES_URL = f'https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=50'
REQUEST_TIMEOUT_SECONDS = 5.0
REQUEST_HEADERS = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Mantella-update-check'}

_VERSION_PATTERN = re.compile(r'^v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$')


@dataclass
class NewRelease:
    version: str # eg "0.17.0" or "0.17.0-beta.1"
    url: str # the release's page on GitHub
    is_prerelease: bool


def parse_version(text: str) -> tuple | None:
    """A key that sorts versions the way semantic versioning does: 0.16.0 < 0.17.0-alpha.1 < 0.17.0-alpha.2 < 0.17.0-beta.1 < 0.17.0.
    None if the text is not a version"""
    match = _VERSION_PATTERN.match(str(text or '').strip())
    if not match:
        return None
    core = (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))
    prerelease = match.group(4)
    if not prerelease:
        return core + (1, ()) # a release comes after all of its pre-releases
    identifiers = tuple((0, int(part), '') if part.isdigit() else (1, 0, part.lower()) for part in prerelease.split('.'))
    return core + (0, identifiers)


def is_prerelease_version(version: str) -> bool:
    key = parse_version(version)
    return key is not None and key[3] == 0


def find_newer_release(current_version: str, releases: list[dict]) -> NewRelease | None:
    """The newest release on GitHub that is newer than the version in use, of the kinds the user is told about

    Args:
        current_version: the version in use, eg "0.17.0-alpha.3"
        releases: GitHub's list of releases (each with tag_name, prerelease, draft and html_url)
    """
    current_key = parse_version(current_version)
    if current_key is None:
        return None
    include_prereleases = is_prerelease_version(current_version)
    newest: tuple[tuple, NewRelease] | None = None
    for release in releases:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        is_prerelease = bool(release.get('prerelease'))
        if is_prerelease and not include_prereleases:
            continue
        tag = str(release.get('tag_name') or '')
        key = parse_version(tag)
        if key is None or key <= current_key:
            continue
        if newest is None or key > newest[0]:
            newest = (key, NewRelease(tag.lstrip('v'), str(release.get('html_url') or f'https://github.com/{GITHUB_REPOSITORY}/releases'), is_prerelease))
    return newest[1] if newest else None


class UpdateCheck:
    """Asks GitHub once, in the background, so that starting Mantella is not held up by it"""
    def __init__(self) -> None:
        self.__thread: threading.Thread | None = None
        self.__result: NewRelease | None = None

    def start(self, current_version: str) -> None:
        if self.__thread is not None:
            return
        self.__thread = threading.Thread(target=self.__check, args=(current_version,), daemon=True)
        self.__thread.start()

    def __check(self, current_version: str) -> None:
        try:
            response = requests.get(RELEASES_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            releases = response.json()
            if not isinstance(releases, list):
                return
            self.__result = find_newer_release(current_version, releases)
            if self.__result:
                kind = 'pre-release' if self.__result.is_prerelease else 'version'
                logger.log(24, f'A new {kind} of Mantella is available: {self.__result.version} (this is {current_version}). Get it here: {self.__result.url}')
        except Exception as e:
            logger.debug(f'Could not check for a new version of Mantella: {e}')

    def get_result(self, wait_seconds: float = 0) -> NewRelease | None:
        """The newer release found, if any. Waits up to the given time for the check to finish"""
        if self.__thread is not None and wait_seconds > 0:
            self.__thread.join(wait_seconds)
        return self.__result


_update_check = UpdateCheck()


def get_update_check() -> UpdateCheck:
    return _update_check

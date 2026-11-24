"""Checks behind the `Test` buttons of the settings page. Each returns (success, message) and never raises."""
import requests


def check_xtts_url(url: str, timeout: float = 5) -> tuple[bool, str]:
    """Checks whether an XTTS API server answers at the given URL.

    Args:
        url: The value of the `XTTS URL` setting
        timeout: Seconds to wait for the server

    Returns:
        Whether the server answered like an XTTS server, and a message for the user
    """
    url = str(url or '').strip().rstrip('/')
    if not url:
        return False, 'No XTTS URL is set.'
    if not url.lower().startswith(('http://', 'https://')):
        return False, f"'{url}' is not a URL. It has to start with http:// or https://"

    try:
        response = requests.get(f'{url}/speakers_list', timeout=timeout)
    except requests.exceptions.Timeout:
        return False, f'No answer from {url} within {timeout:g} seconds.'
    except requests.exceptions.ConnectionError:
        return False, f'Could not connect to {url}. Is the XTTS server running, and are the address and port right?'
    except requests.exceptions.RequestException as e:
        return False, f'Could not connect to {url}: {e}'

    if response.status_code != 200:
        return False, f'{url} answered with HTTP status {response.status_code}. Something is running there, but it does not look like an XTTS server.'
    try:
        speakers = response.json()
    except ValueError:
        return False, f'{url} answered, but not like an XTTS server. Check the address and port.'
    if not isinstance(speakers, dict):
        return False, f'{url} answered, but not like an XTTS server. Check the address and port.'

    voice_count = 0
    for language in speakers.values():
        if isinstance(language, dict) and isinstance(language.get('speakers'), list):
            voice_count += len(language['speakers'])

    message = f'Connected to XTTS at {url}: {voice_count} voice(s) in {len(speakers)} language(s).'
    try:
        models = requests.get(f'{url}/get_models_list', timeout=timeout)
        if models.status_code == 200 and isinstance(models.json(), list):
            message += f' {len(models.json())} model(s).'
    except (requests.exceptions.RequestException, ValueError):
        pass # the server is reachable, the model list is only extra information
    return True, message

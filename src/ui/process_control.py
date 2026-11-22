import os
import subprocess
import sys
import threading
import src.utils as utils

logger = utils.get_logger()

RESTARTED_ENV_VAR = 'MANTELLA_RESTARTED'


def was_restarted_from_ui() -> bool:
    """Whether this process was started by the restart button of the web UI (which is then already open in the browser)"""
    return os.environ.get(RESTARTED_ENV_VAR) == '1'


def get_restart_command() -> list[str]:
    """The command that starts Mantella the same way the current process was started"""
    if getattr(sys, 'frozen', False): # running as exe
        return [sys.executable] + sys.argv[1:]
    # The working directory may have changed since startup, so a relative script path can no longer be relied on
    main_script = getattr(sys.modules.get('__main__'), '__file__', None) or sys.argv[0]
    return [sys.executable, os.path.abspath(main_script)] + sys.argv[1:]


def _exit_soon(delay: float = 0.5):
    """Ends the process after a short delay, giving the web UI the time to receive a response first"""
    def _exit():
        logger.log(24, 'Mantella stopped via the web UI')
        for handler in logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        os._exit(0)
    timer = threading.Timer(delay, _exit)
    timer.daemon = True
    timer.start()


def stop_mantella() -> str:
    logger.log(24, 'Stopping Mantella...')
    _exit_soon()
    return 'Mantella is stopping. Restart the game (or run Mantella again) to start it back up.'


def restart_mantella() -> str:
    logger.log(24, 'Restarting Mantella...')
    try:
        environment = os.environ.copy()
        environment[RESTARTED_ENV_VAR] = '1'
        creationflags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0) # give the new process its own console window on Windows
        subprocess.Popen(get_restart_command(), cwd=os.getcwd(), env=environment, creationflags=creationflags, close_fds=True)
    except Exception as e:
        logger.error(f'Could not restart Mantella: {e}')
        return f'Could not restart Mantella: {e}'
    # The new process only starts listening once it has finished loading, by which time this process has freed the port
    _exit_soon()
    return 'Mantella is restarting. This page will reconnect once it is back up.'

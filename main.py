from src.wine import apply_wine_workarounds
apply_wine_workarounds() # Must run before any native libraries (onnxruntime, ctranslate2) are loaded
import onnxruntime # Ensure onnxruntime is imported before anything else to avoid pyinstaller DLL load issues
from src.http.http_server import http_server
import sys
import traceback
from src.http.routes.routeable import routeable
from src.http.routes.mantella_route import mantella_route
from src.setup import MantellaSetup
from src.ui.start_ui import StartUI
import src.utils as utils

def main():
    if '--smoke-test' in sys.argv:
        # Used by the build to check that the executable contains everything it needs: getting here means that all of
        # the imports above could be loaded. Libraries that are only imported when they are first used are loaded here
        import importlib
        lazily_imported = ['anthropic', 'cv2', 'gradio', 'mss', 'sounddevice', 'soundfile', 'tiktoken_ext.openai_public', 'silero_vad_lite']
        if getattr(sys, 'frozen', False):
            lazily_imported += ['moonshine_onnx', 'win32gui'] # part of every build of the executable
        missing = []
        for module in lazily_imported:
            try:
                importlib.import_module(module)
            except Exception as e:
                missing.append(f'{module} ({type(e).__name__}: {e})')
        if missing:
            print('Mantella is missing libraries:\n  ' + '\n  '.join(missing))
            sys.exit(1)
        print(f'Mantella {utils.get_version(default="?")}: all libraries loaded')
        return
    logger = utils.get_logger() # assigned before the try block so that startup errors can be logged
    try:
        mantella_version = utils.get_version(default='0.14')
        config, language_info = MantellaSetup().initialise(
            config_file='config.ini',
            logging_file='logging.log', 
            language_file='data/language_support.csv',
            mantella_version=mantella_version)

        logger = utils.get_logger()

        logger.log(24, f'\nMantella v{mantella_version}')

        mantella_http_server = http_server()

        conversation = mantella_route(
            config=config,
            language_info=language_info,
        )
        ui = StartUI(config)
        routes: list[routeable] = [conversation, ui]
        
        mantella_http_server.start(int(config.port), routes, config.play_startup_sound, config.show_http_debug_messages)

    except Exception as e:
        logger.error("".join(traceback.format_exception(e)))
        input("Press Enter to exit.")

if __name__ == '__main__':
    main()

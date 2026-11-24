from datetime import datetime
import base64
import os
import src.utils as utils
import numpy as np
import mss
import cv2
import ctypes
from pathlib import Path
from src.config.definitions.game_definitions import GameEnum
import platform
from src.wine import is_running_under_wine, to_host_path
import time

if platform.system() == "Windows":
    import win32gui


logger = utils.get_logger()


class ImageManager:
    '''
    Manages game window capture and image processing
    '''

    @utils.time_it
    def __init__(self,
                 game: GameEnum,
                 save_folder: str,
                 save_screenshot: bool,
                 image_quality: int,
                 low_resolution_mode: bool,
                 resize_method: str,
                 capture_offset: dict[str, int],
                 use_game_screenshots: bool,
                 game_image_path: str | None,
                 use_frame_capture: bool = False) -> None:

        WINDOW_TITLES = {
            GameEnum.SKYRIM: 'Skyrim Special Edition',
            GameEnum.SKYRIM_VR: 'Skyrim VR',
            GameEnum.FALLOUT4: 'Fallout4',
            GameEnum.FALLOUT4_VR: 'Fallout4VR'
        }
        # Get window title from game enum, or as a last resort try using the display name
        self.__window_title: str = WINDOW_TITLES.get(game, game.display_name)
        self.__save_screenshot: bool = save_screenshot
        self.__image_quality: int = image_quality
        self.__capture_offset: dict[str, int] = capture_offset
        self.__low_resolution_mode: bool = low_resolution_mode

        RESIZING_METHODS = {
            'Nearest': cv2.INTER_NEAREST,
            'Linear': cv2.INTER_LINEAR,
            'Cubic': cv2.INTER_CUBIC,
            'Lanczos': cv2.INTER_LANCZOS4
        }
        self.__resize_method: int = RESIZING_METHODS.get(resize_method, cv2.INTER_NEAREST)

        self.__use_game_screenshots: bool = use_game_screenshots
        self.__game_image_file_path = None
        if game_image_path:
            self.__game_image_file_path: str = str(Path(game_image_path) / "Mantella_Vision.jpg")
            if self.__use_game_screenshots:
                if os.path.exists(self.__game_image_file_path):
                    logger.log(23, f'Removing leftover in-game vision screenshot from previous run...')
                    os.remove(self.__game_image_file_path)

        if self.__save_screenshot:
            self.__image_path: str = str(Path(save_folder) / 'data' / 'tmp' / 'images')
            os.makedirs(self.__image_path, exist_ok=True)

        self.__capture_params = None
        self.__has_black_screenshot_warning_happened: bool = False
        self.__has_game_screenshot_warning_happened: bool = False
        # Experimental (Skyrim): the SKSE_HTTP plugin copies the frame instead of the game taking a screenshot of itself
        self.__use_frame_capture: bool = use_frame_capture
        self.__frame_capture_file_path: str = str(Path(save_folder) / 'data' / 'tmp' / self.FRAME_CAPTURE_FILE_NAME)
        self.__has_frame_capture_warning_happened: bool = False
        self.__is_skyrim: bool = game.base_game == GameEnum.SKYRIM
        # Fallout 4: the mod saves a screenshot for Mantella to pick up.
        # Skyrim: Mantella presses the game's own screenshot key and picks up the file the game saves to its folder
        self.__game_folder: str | None = game_image_path
        self.__game_screenshots_supported: bool = game.base_game == GameEnum.FALLOUT4 or (self.__is_skyrim and bool(game_image_path))

        if platform.system() != "Windows":
            return

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            logger.warning('Failed to read monitor DPI. Images may not be saved in the correct dimensions.')


    @property
    def capture_params(self):
        if self.__capture_params is None:
            self.__capture_params = self._calculate_capture_params()
        return self.__capture_params


    def reset_capture_params(self):
        self.__capture_params = None


    @utils.time_it
    def _calculate_capture_params(self) -> dict[str, int]:
        '''Calculate the capture parameters / coordinates of the game window

        Returns:
            dict[str,int]: A dictionary containing window locations and their coordinates
        '''
        hwnd = win32gui.FindWindow(None, self.__window_title)
        if not hwnd:
            # Check if the game version is GOG
            gog_title = self.__window_title + ' GOG'
            hwnd = win32gui.FindWindow(None, gog_title)
            if not hwnd:
                logger.error(f"Window '{self.__window_title}' not found")
                self.__capture_params = None
                return None

        window_rect = win32gui.GetWindowRect(hwnd)
        client_rect = win32gui.GetClientRect(hwnd)
        client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))

        left_border = client_left - window_rect[0]
        top_border = client_top - window_rect[1]

        capture_left = max(window_rect[0] + left_border + self.__capture_offset.get('left', 0), 0)
        capture_top = max(window_rect[1] + top_border + self.__capture_offset.get('top', 0), 0)
        capture_width = client_rect[2] + self.__capture_offset.get('right', 0)
        capture_height = client_rect[3] + self.__capture_offset.get('bottom', 0)

        return {"left": capture_left, "top": capture_top, "width": capture_width, "height": capture_height}


    @utils.time_it
    def _resize_image(self, image: np.ndarray, width: int, height: int) -> np.ndarray:
        '''Resize the image to the target resolution specified here:
        https://platform.openai.com/docs/guides/vision/managing-images

        In summary:
            "low" detail images should have a resolution of 512x512
            "high" detail images should have a maximum length of 768 for the short side and 2048 for the long side

        Args:
            image (numpy.ndarray): The image to resize
            width (int): The width of the screenshot
            height (int): The height of the screenshot

        Returns:
            numpy.ndarray: The resized image
        '''

        if self.__low_resolution_mode:
            target_size = 512
            if height < width:
                scale_factor = target_size / height
                new_height = target_size
                new_width = int(width * scale_factor)
            else:
                scale_factor = target_size / width
                new_width = target_size
                new_height = int(height * scale_factor)

            resized_image = cv2.resize(image, (new_width, new_height), interpolation=self.__resize_method)

            start_x = (new_width - target_size) // 2
            start_y = (new_height - target_size) // 2

            cropped_image = resized_image[start_y:start_y + target_size, start_x:start_x + target_size]

            return cropped_image
        else:
            max_short_side = 768
            max_long_side = 2_000

            short_side = min(height, width)
            long_side = max(height, width)
            
            if short_side <= max_short_side and long_side <= max_long_side:
                return image
            
            scale_factor = min(max_short_side / short_side, max_long_side / long_side)
            
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            resized_image = cv2.resize(image, (new_width, new_height), interpolation=self.__resize_method)
            
            return resized_image
    

    @utils.time_it
    def _take_screenshot(self, params: dict[str, int]) -> tuple[np.ndarray, int, int]:
        '''Take a screenshot within the area specified by params

        Args:
            params (dict[str, int]): The capture parameters

        Returns:
            image (numpy.ndarray): The captured screenshot as a numpy array
            width (int): The width of the screenshot
            height (int): The height of the screenshot
        '''
        with mss.mss() as sct:
            screenshot = sct.grab(params)
        return np.array(screenshot), screenshot.width, screenshot.height
    

    @staticmethod
    def _is_blank(image: np.ndarray, brightness_threshold: int = 16, max_bright_fraction: float = 0.001) -> bool:
        '''Check whether an image is (nearly) all black, as returned when a window cannot be captured

        Args:
            image (numpy.ndarray): The captured image (BGR or BGRA)
            brightness_threshold (int): The value above which a color channel counts as lit
            max_bright_fraction (float): The fraction of lit values up to which the image still counts as blank

        Returns:
            bool: Whether the image contains no meaningful content
        '''
        if image is None or image.size == 0:
            return True
        color_channels = image[..., :3] if image.ndim == 3 else image # ignore the alpha channel
        return np.count_nonzero(color_channels > brightness_threshold) <= color_channels.size * max_bright_fraction


    @utils.time_it
    def _get_screenshot(self) -> tuple[np.ndarray, int, int]:
        '''Search for saved screenshots that have been taken in-game, removing them once loaded

        Returns:
            image (numpy.ndarray): The saved screenshot as a numpy array
            width (int): The width of the screenshot
            height (int): The height of the screenshot
        '''
        screenshot = cv2.imread(self.__game_image_file_path)
        os.remove(self.__game_image_file_path)

        height, width = screenshot.shape[:2]
        return np.array(screenshot), width, height
    

    SKYRIM_SCREENSHOT_EXTENSIONS = ('.png', '.bmp', '.jpg', '.tga')

    def _find_skyrim_screenshots(self) -> set[str]:
        """The screenshots (ScreenShot<number>.png by default) currently in the game folder"""
        try:
            return {os.path.join(self.__game_folder, f) for f in os.listdir(self.__game_folder)
                    if f.lower().startswith('screenshot') and f.lower().endswith(self.SKYRIM_SCREENSHOT_EXTENSIONS)}
        except OSError:
            return set()

    @staticmethod
    def _press_screenshot_key() -> None:
        """Presses the Print Screen key, which Skyrim takes a screenshot on"""
        VK_SNAPSHOT, DIK_SYSRQ, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x2C, 0xB7, 0x1, 0x2
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_SNAPSHOT, DIK_SYSRQ, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_SNAPSHOT, DIK_SYSRQ, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

    # Shared with the SKSE_HTTP plugin (skse/SKSE_HTTP/src/FrameCapture.cpp)
    FRAME_CAPTURE_EVENT_NAME = 'Local\\MantellaCaptureFrame'
    FRAME_CAPTURE_FILE_NAME = 'mantella_frame.bmp'

    @staticmethod
    def _request_frame_capture() -> bool:
        """Asks the SKSE_HTTP plugin to save the frame the game is showing

        Returns:
            bool: False if the plugin cannot be reached (an older SKSE_HTTP.dll, or the game is not running)
        """
        EVENT_MODIFY_STATE = 0x0002
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenEventW.restype = ctypes.c_void_p
        kernel32.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, 0, ImageManager.FRAME_CAPTURE_EVENT_NAME)
        if not handle:
            return False
        try:
            return bool(kernel32.SetEvent(handle))
        finally:
            kernel32.CloseHandle(handle)

    def __warn_about_frame_capture(self, reason: str) -> None:
        if not self.__has_frame_capture_warning_happened:
            self.__has_frame_capture_warning_happened = True
            logger.warning(f'`Fast Game Screenshots` did not work ({reason}), so the game\'s own screenshot is used instead. If this keeps happening, disable `Vision`->`Fast Game Screenshots (Experimental)` in the Mantella UI')

    @utils.time_it
    def _capture_skyrim_frame(self, timeout: float = 1.5) -> tuple[np.ndarray, int, int] | None:
        '''Experimental: has the SKSE_HTTP plugin copy the frame the game is showing, and loads it.
        Unlike the game's own screenshot (see _take_skyrim_screenshot) this does not make the game freeze for a moment

        Returns:
            The frame as a numpy array with its width and height, or None if it could not be captured
        '''
        try:
            if os.path.exists(self.__frame_capture_file_path):
                os.remove(self.__frame_capture_file_path) # left over from an earlier request that came too late
            if not self._request_frame_capture():
                self.__warn_about_frame_capture('the SKSE_HTTP plugin of the running game does not offer it')
                return None

            frame = None
            deadline = time.time() + timeout
            while time.time() < deadline and frame is None:
                time.sleep(0.02)
                if os.path.exists(self.__frame_capture_file_path):
                    frame = cv2.imread(self.__frame_capture_file_path)
            if frame is None:
                self.__warn_about_frame_capture(f'no frame was saved to "{to_host_path(self.__frame_capture_file_path)}" in time')
                return None
            try:
                os.remove(self.__frame_capture_file_path)
            except OSError as e:
                logger.debug(f'Could not remove captured frame: {e}')
            if self._is_blank(frame):
                self.__warn_about_frame_capture('the captured frame is blank')
                return None
            height, width = frame.shape[:2]
            return np.array(frame), width, height
        except Exception as e:
            self.__warn_about_frame_capture(str(e))
            return None

    @utils.time_it
    def _take_skyrim_screenshot(self, timeout: float = 2.0) -> tuple[np.ndarray, int, int] | None:
        '''Has Skyrim take a screenshot of itself and loads it, removing the file afterward.
        Unlike capturing the game window from the outside, this also works where the window cannot be captured (eg under Wine / Proton)

        Returns:
            The screenshot as a numpy array with its width and height, or None if the game did not save a screenshot in time
        '''
        existing_screenshots = self._find_skyrim_screenshots()
        self._press_screenshot_key()

        new_screenshot: str | None = None
        deadline = time.time() + timeout
        while time.time() < deadline and not new_screenshot:
            time.sleep(0.05)
            new_files = self._find_skyrim_screenshots() - existing_screenshots
            if new_files:
                new_screenshot = max(new_files, key=os.path.getmtime)

        if not new_screenshot:
            if not self.__has_game_screenshot_warning_happened:
                self.__has_game_screenshot_warning_happened = True
                logger.warning(f'Skyrim did not save a screenshot to "{to_host_path(self.__game_folder)}" after the Print Screen key was pressed, so no image will be sent to the LLM. Make sure the game window is focused and that screenshots are enabled in the game (bAllowScreenShot=1 under [Display] in Skyrim.ini). If this keeps happening, disable `Vision`->`Use Game Screenshots` in the Mantella UI')
            return None

        # wait until the game has finished writing the file
        screenshot = None
        while time.time() < deadline + 1.0:
            screenshot = cv2.imread(new_screenshot)
            if screenshot is not None:
                break
            time.sleep(0.05)
        try:
            os.remove(new_screenshot)
        except OSError as e:
            logger.debug(f'Could not remove screenshot {new_screenshot}: {e}')
        if screenshot is None:
            return None

        height, width = screenshot.shape[:2]
        return screenshot, width, height


    @utils.time_it
    def _encode_image_to_jpeg(self, screenshot):
        return cv2.imencode('.jpg', screenshot, [cv2.IMWRITE_JPEG_QUALITY, self.__image_quality])[1]
    

    @utils.time_it
    def get_image(self) -> str | None:
        '''Capture, process, and encode an image of the game window

        Returns:
            str: Base64 encoded JPEG image, or None if capture fails
        '''

        if platform.system() != "Windows":
            logger.warning("Vision LLM is supported only on Windows")
            return None

        try:
            # Capture
            if self.__use_game_screenshots and self.__is_skyrim and self.__game_folder:
                captured = self._capture_skyrim_frame() if self.__use_frame_capture else None
                if captured is None:
                    captured = self._take_skyrim_screenshot()
                if captured is None:
                    return None
                screenshot, width, height = captured
            elif self.__use_game_screenshots and self.__game_image_file_path is not None:
                if os.path.exists(self.__game_image_file_path):
                    screenshot, width, height = self._get_screenshot()
                else:
                    return None
            else:
                params = self.capture_params
                if not params:
                    return None
                screenshot, width, height = self._take_screenshot(params)
                if self._is_blank(screenshot):
                    # A blank capture tells the LLM nothing, and can lead to NPCs commenting on the "black screen"
                    if self.__game_image_file_path is not None and os.path.exists(self.__game_image_file_path):
                        logger.log(23, 'Captured image of the game window is blank. Using the in-game screenshot instead')
                        screenshot, width, height = self._get_screenshot()
                    else:
                        if not self.__has_black_screenshot_warning_happened:
                            self.__has_black_screenshot_warning_happened = True
                            hint = ' This is common when running under Wine / Proton.' if is_running_under_wine() else ''
                            if self.__game_screenshots_supported:
                                advice = 'try enabling `Vision`->`Use Game Screenshots` in the Mantella UI'
                            else:
                                advice = 'try running the game in windowed / borderless mode and make sure the game window is not covered by other windows'
                            logger.warning(f'Captured image of the game window is blank, so it will not be sent to the LLM.{hint} If this keeps happening, {advice}')
                        return None

            # Process
            screenshot = self._resize_image(screenshot, width, height)

            # Encode
            buffer = self._encode_image_to_jpeg(screenshot)
            img_str = base64.b64encode(buffer).decode()

            # Optionally, save the image to disk
            if self.__save_screenshot:
                self._save_screenshot_to_file(buffer)
            
            return img_str
        
        except Exception as e:
            utils.play_error_sound()
            logger.error(f"An error occurred: {e}")
            self.reset_capture_params() # reset the window capture coordinates
            return None
        

    @utils.time_it
    def _save_screenshot_to_file(self, screenshot: bytes):
        '''Save the screenshot to a file
        
        Args:
            screenshot (bytes): The screenshot data to save
        '''
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.__image_path}/{self.__window_title.replace(' ', '_')}_{timestamp}.jpg"

        with open(filename, 'wb') as f:
            f.write(screenshot)

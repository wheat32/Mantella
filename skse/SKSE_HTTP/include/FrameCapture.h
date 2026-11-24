#pragma once

// Experimental: lets Mantella get a picture of the game without the freeze of the game's own screenshot.
// Mantella signals a named event. The current frame is then copied on the graphics card and read back in the game's
// main thread (which owns the graphics device), and saved as a .bmp file by a background thread.
namespace FrameCapture
{
// Starts the background thread that waits for capture requests. Called once when the plugin is loaded
void Start();
} // namespace FrameCapture

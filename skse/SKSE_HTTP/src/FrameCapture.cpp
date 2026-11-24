#include <windows.h>
#include <ShlObj.h>
#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <FrameCapture.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>
#include <vector>

namespace
{
// Shared with Mantella (src/image/image_manager.py)
constexpr wchar_t CAPTURE_EVENT_NAME[] = L"Local\\MantellaCaptureFrame";
constexpr wchar_t CAPTURE_FOLDER[] = L"My Games\\Mantella\\data\\tmp";
constexpr wchar_t CAPTURE_FILE_NAME[] = L"mantella_frame.bmp";
constexpr wchar_t CAPTURE_TEMPORARY_FILE_NAME[] = L"mantella_frame.bmp.tmp";

// The picture is made smaller while it is read: Mantella scales it down anyway, and less data is read in the game's thread
constexpr std::uint32_t MAX_OUTPUT_WIDTH = 1280;
constexpr std::uint32_t BACK_BUFFER_INDEX = 0;
constexpr std::uint32_t SINGLE_SAMPLE_COUNT = 1;
constexpr std::uint32_t SINGLE_MIP_LEVEL = 1;
constexpr std::uint32_t SINGLE_ARRAY_SLICE = 1;

// Reading the copy back is tried without waiting for the graphics card, so that the game's thread is never held up
constexpr int MAX_READ_ATTEMPTS = 20;
constexpr std::chrono::milliseconds READ_RETRY_DELAY{15};
constexpr std::chrono::milliseconds TASK_TIMEOUT{2000};
constexpr REX::W32::HRESULT STILL_DRAWING = static_cast<REX::W32::HRESULT>(0x887A000AL); // DXGI_ERROR_WAS_STILL_DRAWING

constexpr std::uint32_t BYTES_PER_SOURCE_PIXEL = 4;
constexpr std::uint32_t BYTES_PER_OUTPUT_PIXEL = 3;
constexpr std::uint32_t BMP_ROW_ALIGNMENT = 4;
constexpr std::uint32_t BMP_FILE_HEADER_SIZE = 14;
constexpr std::uint32_t BMP_INFO_HEADER_SIZE = 40;
constexpr std::uint16_t BMP_SIGNATURE = 0x4D42; // "BM"
constexpr std::uint16_t BMP_PLANES = 1;
constexpr std::uint16_t BMP_BITS_PER_PIXEL = 24;

// 10 bit color channels (R10G10B10A2) are reduced to 8 bit
constexpr std::uint32_t TEN_BIT_MASK = 0x3FF;
constexpr std::uint32_t TEN_BIT_GREEN_SHIFT = 10;
constexpr std::uint32_t TEN_BIT_BLUE_SHIFT = 20;
constexpr std::uint32_t TEN_TO_EIGHT_BIT_SHIFT = 2;

// Positions of the color channels within a pixel of four bytes
constexpr std::uint32_t FIRST_CHANNEL = 0;
constexpr std::uint32_t SECOND_CHANNEL = 1;
constexpr std::uint32_t THIRD_CHANNEL = 2;

enum class PixelLayout
{
    Unsupported,
    RGBA8,
    BGRA8,
    RGB10A2
};

enum class CaptureStep
{
    Waiting,  // the task in the game's thread has not finished yet
    Copied,   // the frame has been copied, it can be read back
    NotReady, // the graphics card has not finished the copy yet
    Read,     // the pixels are in the picture
    Failed
};

struct Picture
{
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::vector<std::uint8_t> pixels; // blue, green, red per pixel, rows from top to bottom
};

std::mutex stepMutex;
std::condition_variable stepChanged;
CaptureStep step = CaptureStep::Waiting;
Picture picture;

// Only used in the game's main thread
REX::W32::ID3D11Texture2D* stagingTexture = nullptr;
REX::W32::D3D11_TEXTURE2D_DESC stagingDescription{};

PixelLayout GetPixelLayout(REX::W32::DXGI_FORMAT format)
{
    switch (format)
    {
        case REX::W32::DXGI_FORMAT_R8G8B8A8_TYPELESS:
        case REX::W32::DXGI_FORMAT_R8G8B8A8_UNORM:
        case REX::W32::DXGI_FORMAT_R8G8B8A8_UNORM_SRGB:
            return PixelLayout::RGBA8;

        case REX::W32::DXGI_FORMAT_B8G8R8A8_UNORM:
        case REX::W32::DXGI_FORMAT_B8G8R8X8_UNORM:
        case REX::W32::DXGI_FORMAT_B8G8R8A8_TYPELESS:
        case REX::W32::DXGI_FORMAT_B8G8R8A8_UNORM_SRGB:
            return PixelLayout::BGRA8;

        case REX::W32::DXGI_FORMAT_R10G10B10A2_TYPELESS:
        case REX::W32::DXGI_FORMAT_R10G10B10A2_UNORM:
            return PixelLayout::RGB10A2;

        default:
            return PixelLayout::Unsupported;
    }
}

void SetStep(CaptureStep newStep)
{
    {
        std::lock_guard<std::mutex> lock(stepMutex);
        step = newStep;
    }
    stepChanged.notify_all();
}

// Game's main thread: copies the frame that is on screen into a texture that can be read by the processor.
// This only queues the copy on the graphics card, it does not wait for it
void CopyFrame()
{
    REX::W32::ID3D11Device* device = RE::BSGraphics::Renderer::GetDevice();
    RE::BSGraphics::RendererWindow* window = RE::BSGraphics::Renderer::GetCurrentRenderWindow();
    if (device == nullptr || window == nullptr || window->swapChain == nullptr)
    {
        SKSE::log::warn("Frame capture: the game's graphics device is not available");
        SetStep(CaptureStep::Failed);
        return;
    }

    REX::W32::ID3D11Texture2D* backBuffer = nullptr;
    REX::W32::HRESULT result = window->swapChain->GetBuffer(BACK_BUFFER_INDEX, REX::W32::IID_ID3D11Texture2D, reinterpret_cast<void**>(&backBuffer));
    if (result < 0 || backBuffer == nullptr)
    {
        SKSE::log::warn("Frame capture: the frame could not be accessed ({:x})", static_cast<std::uint32_t>(result));
        SetStep(CaptureStep::Failed);
        return;
    }

    REX::W32::D3D11_TEXTURE2D_DESC description{};
    backBuffer->GetDesc(&description);
    if (description.sampleDesc.count != SINGLE_SAMPLE_COUNT || GetPixelLayout(description.format) == PixelLayout::Unsupported)
    {
        SKSE::log::warn("Frame capture: the frame has a format that is not supported (format {}, {} samples)", static_cast<int>(description.format), description.sampleDesc.count);
        backBuffer->Release();
        SetStep(CaptureStep::Failed);
        return;
    }

    bool sizeChanged = stagingTexture == nullptr || stagingDescription.width != description.width || stagingDescription.height != description.height || stagingDescription.format != description.format;
    if (sizeChanged == true)
    {
        if (stagingTexture != nullptr)
        {
            stagingTexture->Release();
            stagingTexture = nullptr;
        }
        stagingDescription = description;
        stagingDescription.mipLevels = SINGLE_MIP_LEVEL;
        stagingDescription.arraySize = SINGLE_ARRAY_SLICE;
        stagingDescription.usage = REX::W32::D3D11_USAGE_STAGING;
        stagingDescription.bindFlags = 0;
        stagingDescription.cpuAccessFlags = REX::W32::D3D11_CPU_ACCESS_READ;
        stagingDescription.miscFlags = 0;
        result = device->CreateTexture2D(&stagingDescription, nullptr, &stagingTexture);
        if (result < 0 || stagingTexture == nullptr)
        {
            SKSE::log::warn("Frame capture: no texture could be created for the copy ({:x})", static_cast<std::uint32_t>(result));
            stagingTexture = nullptr;
            backBuffer->Release();
            SetStep(CaptureStep::Failed);
            return;
        }
    }

    REX::W32::ID3D11DeviceContext* context = nullptr;
    device->GetImmediateContext(&context);
    if (context == nullptr)
    {
        backBuffer->Release();
        SetStep(CaptureStep::Failed);
        return;
    }
    context->CopyResource(stagingTexture, backBuffer);
    context->Release();
    backBuffer->Release();
    SetStep(CaptureStep::Copied);
}

// Game's main thread: reads the copied frame into the picture, taking every n-th pixel
void ReadFrame(bool waitForGraphicsCard)
{
    REX::W32::ID3D11Device* device = RE::BSGraphics::Renderer::GetDevice();
    if (device == nullptr || stagingTexture == nullptr)
    {
        SetStep(CaptureStep::Failed);
        return;
    }
    REX::W32::ID3D11DeviceContext* context = nullptr;
    device->GetImmediateContext(&context);
    if (context == nullptr)
    {
        SetStep(CaptureStep::Failed);
        return;
    }

    std::uint32_t mapFlags = waitForGraphicsCard == true ? 0 : static_cast<std::uint32_t>(REX::W32::D3D11_MAP_FLAG_DO_NOT_WAIT);
    REX::W32::D3D11_MAPPED_SUBRESOURCE mapped{};
    REX::W32::HRESULT result = context->Map(stagingTexture, 0, REX::W32::D3D11_MAP_READ, mapFlags, &mapped);
    if (result == STILL_DRAWING)
    {
        context->Release();
        SetStep(CaptureStep::NotReady);
        return;
    }
    if (result < 0 || mapped.data == nullptr)
    {
        SKSE::log::warn("Frame capture: the copy of the frame could not be read ({:x})", static_cast<std::uint32_t>(result));
        context->Release();
        SetStep(CaptureStep::Failed);
        return;
    }

    PixelLayout layout = GetPixelLayout(stagingDescription.format);
    std::uint32_t pixelStep = (stagingDescription.width + MAX_OUTPUT_WIDTH - 1) / MAX_OUTPUT_WIDTH;
    if (pixelStep == 0)
    {
        pixelStep = 1;
    }
    Picture newPicture;
    newPicture.width = stagingDescription.width / pixelStep;
    newPicture.height = stagingDescription.height / pixelStep;
    newPicture.pixels.resize(static_cast<std::size_t>(newPicture.width) * newPicture.height * BYTES_PER_OUTPUT_PIXEL);

    const std::uint8_t* source = static_cast<const std::uint8_t*>(mapped.data);
    std::uint8_t* target = newPicture.pixels.data();
    for (std::uint32_t y = 0; y < newPicture.height; ++y)
    {
        const std::uint8_t* row = source + static_cast<std::size_t>(y) * pixelStep * mapped.rowPitch;
        for (std::uint32_t x = 0; x < newPicture.width; ++x)
        {
            const std::uint8_t* pixel = row + static_cast<std::size_t>(x) * pixelStep * BYTES_PER_SOURCE_PIXEL;
            switch (layout)
            {
                case PixelLayout::RGBA8:
                    target[FIRST_CHANNEL] = pixel[THIRD_CHANNEL];
                    target[SECOND_CHANNEL] = pixel[SECOND_CHANNEL];
                    target[THIRD_CHANNEL] = pixel[FIRST_CHANNEL];
                    break;

                case PixelLayout::RGB10A2:
                {
                    std::uint32_t value = 0;
                    std::memcpy(&value, pixel, sizeof(value));
                    target[THIRD_CHANNEL] = static_cast<std::uint8_t>((value & TEN_BIT_MASK) >> TEN_TO_EIGHT_BIT_SHIFT);
                    target[SECOND_CHANNEL] = static_cast<std::uint8_t>(((value >> TEN_BIT_GREEN_SHIFT) & TEN_BIT_MASK) >> TEN_TO_EIGHT_BIT_SHIFT);
                    target[FIRST_CHANNEL] = static_cast<std::uint8_t>(((value >> TEN_BIT_BLUE_SHIFT) & TEN_BIT_MASK) >> TEN_TO_EIGHT_BIT_SHIFT);
                    break;
                }

                default: // BGRA8, which is the order of the picture
                    target[FIRST_CHANNEL] = pixel[FIRST_CHANNEL];
                    target[SECOND_CHANNEL] = pixel[SECOND_CHANNEL];
                    target[THIRD_CHANNEL] = pixel[THIRD_CHANNEL];
                    break;
            }
            target += BYTES_PER_OUTPUT_PIXEL;
        }
    }
    context->Unmap(stagingTexture, 0);
    context->Release();

    {
        std::lock_guard<std::mutex> lock(stepMutex);
        picture = std::move(newPicture);
        step = CaptureStep::Read;
    }
    stepChanged.notify_all();
}

// Background thread: has a task run in the game's main thread and waits for the step it ends with
CaptureStep RunInGameThread(std::function<void()> task)
{
    {
        std::lock_guard<std::mutex> lock(stepMutex);
        step = CaptureStep::Waiting;
    }
    SKSE::GetTaskInterface()->AddTask(std::move(task));
    std::unique_lock<std::mutex> lock(stepMutex);
    bool finished = stepChanged.wait_for(lock, TASK_TIMEOUT, []()
                                         {
                                             return step != CaptureStep::Waiting;
                                         });
    if (finished == false)
    {
        return CaptureStep::Failed;
    }
    return step;
}

template <class T>
void WriteValue(std::ofstream& file, T value)
{
    file.write(reinterpret_cast<const char*>(&value), sizeof(value));
}

// Background thread: saves the picture where Mantella looks for it
bool SavePicture(const Picture& saved, const std::filesystem::path& folder)
{
    std::error_code error;
    std::filesystem::create_directories(folder, error);
    std::filesystem::path temporaryPath = folder / CAPTURE_TEMPORARY_FILE_NAME;
    std::filesystem::path finalPath = folder / CAPTURE_FILE_NAME;

    std::uint32_t rowSize = saved.width * BYTES_PER_OUTPUT_PIXEL;
    std::uint32_t padding = (BMP_ROW_ALIGNMENT - rowSize % BMP_ROW_ALIGNMENT) % BMP_ROW_ALIGNMENT;
    std::uint32_t dataSize = (rowSize + padding) * saved.height;
    std::uint32_t headerSize = BMP_FILE_HEADER_SIZE + BMP_INFO_HEADER_SIZE;

    {
        std::ofstream file(temporaryPath, std::ios::binary | std::ios::trunc);
        if (file.is_open() == false)
        {
            return false;
        }

        WriteValue<std::uint16_t>(file, BMP_SIGNATURE);
        WriteValue<std::uint32_t>(file, headerSize + dataSize);
        WriteValue<std::uint32_t>(file, 0); // reserved
        WriteValue<std::uint32_t>(file, headerSize);

        WriteValue<std::uint32_t>(file, BMP_INFO_HEADER_SIZE);
        WriteValue<std::int32_t>(file, static_cast<std::int32_t>(saved.width));
        WriteValue<std::int32_t>(file, static_cast<std::int32_t>(saved.height)); // positive: rows are stored from bottom to top
        WriteValue<std::uint16_t>(file, BMP_PLANES);
        WriteValue<std::uint16_t>(file, BMP_BITS_PER_PIXEL);
        WriteValue<std::uint32_t>(file, 0); // not compressed
        WriteValue<std::uint32_t>(file, dataSize);
        WriteValue<std::int32_t>(file, 0); // resolution and color table: not used
        WriteValue<std::int32_t>(file, 0);
        WriteValue<std::uint32_t>(file, 0);
        WriteValue<std::uint32_t>(file, 0);

        const char paddingBytes[BMP_ROW_ALIGNMENT] = {};
        std::uint32_t row = saved.height;
        while (row > 0)
        {
            --row;
            file.write(reinterpret_cast<const char*>(saved.pixels.data() + static_cast<std::size_t>(row) * rowSize), rowSize);
            file.write(paddingBytes, padding);
        }
        if (file.good() == false)
        {
            return false;
        }
    }

    // Renamed once it is complete, so that Mantella never reads half a file
    return MoveFileExW(temporaryPath.c_str(), finalPath.c_str(), MOVEFILE_REPLACE_EXISTING) != FALSE;
}

bool GetCaptureFolder(std::filesystem::path& folder)
{
    PWSTR documentsPath = nullptr;
    if (FAILED(SHGetKnownFolderPath(FOLDERID_Documents, 0, NULL, &documentsPath)))
    {
        return false;
    }
    folder = std::filesystem::path(documentsPath) / CAPTURE_FOLDER;
    CoTaskMemFree(documentsPath);
    return true;
}

void Capture(const std::filesystem::path& folder)
{
    if (RunInGameThread(CopyFrame) != CaptureStep::Copied)
    {
        return;
    }

    CaptureStep result = CaptureStep::NotReady;
    int attempt = 0;
    while (result == CaptureStep::NotReady && attempt < MAX_READ_ATTEMPTS)
    {
        ++attempt;
        std::this_thread::sleep_for(READ_RETRY_DELAY);
        bool lastAttempt = attempt == MAX_READ_ATTEMPTS;
        result = RunInGameThread([lastAttempt]()
                                 {
                                     ReadFrame(lastAttempt);
                                 });
    }
    if (result != CaptureStep::Read)
    {
        return;
    }

    Picture saved;
    {
        std::lock_guard<std::mutex> lock(stepMutex);
        saved = std::move(picture);
        picture = Picture();
    }
    if (SavePicture(saved, folder) == false)
    {
        SKSE::log::warn("Frame capture: the picture could not be saved");
    }
}

void WaitForRequests(HANDLE captureEvent)
{
    std::filesystem::path folder;
    if (GetCaptureFolder(folder) == false)
    {
        SKSE::log::warn("Frame capture: the Documents folder was not found, so it is not available");
        return;
    }
    while (WaitForSingleObject(captureEvent, INFINITE) == WAIT_OBJECT_0)
    {
        try
        {
            Capture(folder);
        }
        catch (const std::exception& e)
        {
            SKSE::log::warn("Frame capture failed: {}", e.what());
        }
    }
}
} // namespace

namespace FrameCapture
{
void Start()
{
    // Reset automatically after each request. Mantella opens the event by its name and signals it
    HANDLE captureEvent = CreateEventW(nullptr, FALSE, FALSE, CAPTURE_EVENT_NAME);
    if (captureEvent == nullptr)
    {
        SKSE::log::warn("Frame capture: could not be set up, so it is not available");
        return;
    }
    std::thread(WaitForRequests, captureEvent).detach();
}
} // namespace FrameCapture

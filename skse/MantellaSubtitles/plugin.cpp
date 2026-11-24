#include <stddef.h>
#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/msvc_sink.h>

#include "Papyrus.h"
#include "InjectTopic.h"

void InitializeLogging()
{
    std::optional<std::filesystem::path> path = SKSE::log::log_directory();
    if (path.has_value() == false)
    {
        SKSE::stl::report_and_fail("Unable to lookup SKSE logs directory.");
    }
    *path /= SKSE::PluginDeclaration::GetSingleton()->GetName();
    *path += L".log";

    std::shared_ptr<spdlog::logger> log;
    if (IsDebuggerPresent() != 0)
    {
        log = std::make_shared<spdlog::logger>(
            "Global", std::make_shared<spdlog::sinks::msvc_sink_mt>());
    }
    else
    {
        log = std::make_shared<spdlog::logger>(
            "Global", std::make_shared<spdlog::sinks::basic_file_sink_mt>(path->string(), true));
    }

    log->set_level(spdlog::level::debug);
    log->flush_on(spdlog::level::debug);

    spdlog::set_default_logger(std::move(log));
    spdlog::set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%n] [%l] [%t] [%s:%#] %v");
}

/*
We have to manually offset this struct ourselves since the def isn't actually
in commonlibsse-ng. Assume the layout is the same, except with 64-bit pointers.
Oldrim def below for reference.

    struct RE::TESTopicInfoEvent
    {
        RE::Actor   * speaker;      // 00 - NiTPointer<Actor>
        void    * unk04;        // 08 - BSTSmartPointer<REFREventCallbacks::IEventCallback>
        RE::FormID  topicInfoID;    // 10
        bool    flag;           // 18

        inline bool IsStarting() {
            return !flag;
        }
        inline bool IsStopping() {
            return flag;
        }
    };
*/

namespace
{
// Position of topicInfoID in RE::TESTopicInfoEvent, counted in pointer-sized slots
constexpr int TOPIC_INFO_ID_POINTER_SLOT = 2;
// A negative display time: the subtitle is not removed by a timer
constexpr int32_t NO_SUBTITLE_TIMEOUT = -1;
} // namespace

class OurEventSink : public RE::BSTEventSink<RE::TESTopicInfoEvent>
{
    OurEventSink() = default;
    OurEventSink(const OurEventSink&) = delete;
    OurEventSink(OurEventSink&&) = delete;
    OurEventSink& operator=(const OurEventSink&) = delete;
    OurEventSink& operator=(OurEventSink&&) = delete;

public:
    static OurEventSink* GetSingleton()
    {
        static OurEventSink singleton;
        return &singleton;
    }

    RE::BSEventNotifyControl ProcessEvent(const RE::TESTopicInfoEvent* event,
                                          RE::BSTEventSource<RE::TESTopicInfoEvent>*)
    {
        // topicInfoId is the third item in the struct, after two pointers.
        // Unfortunately we have to do it this way because commonlibsse-ng
        // doesn't seem to know the layout of this struct.
        RE::FormID eventTopicInfoId = *(RE::FormID*)((void**)event + TOPIC_INFO_ID_POINTER_SLOT);

        SKSE::log::debug("Received event, topic info ID is {:x}", eventTopicInfoId);

        if (injectSpeaker != nullptr && InjectTopicContainsInfoId(eventTopicInfoId))
        {
            MantellaSubtitles::AddSubtitleForSpeaker(injectSpeaker, injectSubtitle, NO_SUBTITLE_TIMEOUT);
        }
        else
        {
            SKSE::log::debug("Didn't inject subtitle");
        }
        return RE::BSEventNotifyControl::kContinue;
    }
};

void InitializePapyrus()
{
    SKSE::log::debug("Initializing Papyrus binding...");
    if (SKSE::GetPapyrusInterface()->Register(MantellaSubtitles::RegisterFns))
    {
        SKSE::log::debug("Papyrus functions bound.");
    }
    else
    {
        SKSE::stl::report_and_fail("Failure to register Papyrus bindings.");
    }
}

void InitializeEventHandlers()
{
    OurEventSink* eventSink = OurEventSink::GetSingleton();

    // ScriptSource
    RE::ScriptEventSourceHolder* eventSourceHolder = RE::ScriptEventSourceHolder::GetSingleton();
    eventSourceHolder->AddEventSink<RE::TESTopicInfoEvent>(eventSink);

    // auto* skyrimVmSource = RE::SkyrimVM::GetSingleton();
    // skyrimVmSource->AddEventSink<RE::TESTopicInfoEvent>(eventSink);
}

SKSEPluginLoad(const SKSE::LoadInterface* skse)
{
    InitializeLogging();

    const SKSE::PluginDeclaration* plugin = SKSE::PluginDeclaration::GetSingleton();
    REL::Version version = plugin->GetVersion();
    SKSE::log::info("{} {} is loading...", plugin->GetName(), version);

    SKSE::Init(skse);

    InitializePapyrus();
    InitializeEventHandlers();

    // Once all plugins and mods are loaded, then the ~ console is ready and can
    // be printed to
    // SKSE::GetMessagingInterface()->RegisterListener([](SKSE::MessagingInterface::Message *message) {
    //    if (message->type == SKSE::MessagingInterface::kDataLoaded) {
    //        RE::ConsoleLog::GetSingleton()->Print("Hello, world!");
    //  }
    //});

    return true;
}
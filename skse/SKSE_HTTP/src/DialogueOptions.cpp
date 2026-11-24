#include <windows.h>
#include <ShlObj.h>
#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <DialogueOptions.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace
{
constexpr wchar_t DUMP_FOLDER[] = L"My Games\\Mantella";
constexpr wchar_t DUMP_FILE_NAME[] = L"dialogue_options.txt";
constexpr int DUMP_FAILED = -1;

struct Option
{
    std::string quest;
    std::string prompt;
    RE::FormID topicId = 0;
    RE::FormID infoId = 0;
    bool said = false;
    bool sayOnce = false;
    std::vector<std::string> responses;
};

// Conditions are a list in which consecutive entries marked "or" form a group. The groups all have to be true.
// The quest is passed along, as conditions on quest aliases cannot be checked without it
bool AreConditionsTrue(const RE::TESCondition& conditions, RE::TESObjectREFR* speaker, RE::TESObjectREFR* player, RE::TESQuest* quest)
{
    RE::ConditionCheckParams parameters(speaker, player);
    parameters.quest = quest;

    bool groupIsTrue = false;
    bool insideGroup = false;
    const RE::TESConditionItem* item = conditions.head;
    while (item != nullptr)
    {
        bool itemIsTrue = item->IsTrue(parameters);
        if (item->data.flags.isOR == true)
        {
            groupIsTrue = groupIsTrue || itemIsTrue;
            insideGroup = true;
        }
        else
        {
            bool result = insideGroup == true ? (groupIsTrue || itemIsTrue) : itemIsTrue;
            if (result == false)
            {
                return false;
            }
            groupIsTrue = false;
            insideGroup = false;
        }
        item = item->next;
    }
    if (insideGroup == true && groupIsTrue == false)
    {
        return false;
    }
    return true;
}

// The response of a topic is the first of its entries whose conditions are met for the speaker
RE::TESTopicInfo* FindResponse(RE::TESTopic* topic, RE::Actor* speaker, RE::PlayerCharacter* player)
{
    if (topic->topicInfos == nullptr)
    {
        return nullptr;
    }
    for (std::uint32_t i = 0; i < topic->numTopicInfos; ++i)
    {
        RE::TESTopicInfo* info = topic->topicInfos[i];
        if (info == nullptr || info->IsDeleted() == true || info->IsIgnored() == true)
        {
            continue;
        }
        bool sayOnce = info->data.flags.any(RE::TOPIC_INFO_DATA::TOPIC_INFO_FLAGS::kSayOnce);
        if (sayOnce == true && info->saidOnce == true)
        {
            continue;
        }
        if (AreConditionsTrue(info->objConditions, speaker, player, topic->ownerQuest) == true)
        {
            return info;
        }
    }
    return nullptr;
}

std::vector<Option> FindOptions(RE::Actor* speaker)
{
    std::vector<Option> options;
    RE::TESDataHandler* dataHandler = RE::TESDataHandler::GetSingleton();
    RE::PlayerCharacter* player = RE::PlayerCharacter::GetSingleton();
    if (dataHandler == nullptr || player == nullptr)
    {
        return options;
    }

    // The options the dialogue menu starts with are the starting topics of the top-level branches of running quests
    for (RE::BGSDialogueBranch* branch : dataHandler->GetFormArray<RE::BGSDialogueBranch>())
    {
        if (branch == nullptr || branch->IsDeleted() == true)
        {
            continue;
        }
        if (branch->flags.any(RE::BGSDialogueBranch::Flag::kTopLevel) == false)
        {
            continue;
        }
        if (branch->type != RE::DIALOGUE_TYPES::kPlayerDialogue)
        {
            continue;
        }
        RE::TESQuest* quest = branch->quest;
        RE::TESTopic* topic = branch->startingTopic;
        if (quest == nullptr || topic == nullptr || quest->IsRunning() == false)
        {
            continue;
        }
        if (AreConditionsTrue(quest->objConditions, speaker, player, quest) == false)
        {
            continue;
        }

        RE::TESTopicInfo* info = FindResponse(topic, speaker, player);
        if (info == nullptr)
        {
            continue;
        }

        Option option;
        const char* questName = quest->GetFormEditorID();
        const char* prompt = topic->GetFullName();
        option.quest = questName != nullptr ? questName : "";
        option.prompt = prompt != nullptr ? prompt : "";
        option.topicId = topic->GetFormID();
        option.infoId = info->GetFormID();
        option.said = info->saidOnce;
        option.sayOnce = info->data.flags.any(RE::TOPIC_INFO_DATA::TOPIC_INFO_FLAGS::kSayOnce);

        // The game builds the lines the speaker would say, with names and other text already filled in
        RE::DialogueItem item = info->GetDialogueData(speaker);
        for (RE::DialogueResponse* response : item.responses)
        {
            if (response != nullptr && response->text.empty() == false)
            {
                option.responses.push_back(response->text.c_str());
            }
        }
        options.push_back(std::move(option));
    }
    return options;
}

bool GetDumpPath(std::filesystem::path& path)
{
    PWSTR documentsPath = nullptr;
    if (FAILED(SHGetKnownFolderPath(FOLDERID_Documents, 0, NULL, &documentsPath)))
    {
        return false;
    }
    path = std::filesystem::path(documentsPath) / DUMP_FOLDER / DUMP_FILE_NAME;
    CoTaskMemFree(documentsPath);
    return true;
}
} // namespace

namespace DialogueOptions
{
int Dump(RE::StaticFunctionTag*, RE::Actor* speaker)
{
    if (speaker == nullptr)
    {
        return DUMP_FAILED;
    }
    try
    {
        std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
        std::vector<Option> options = FindOptions(speaker);
        long long milliseconds = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();

        std::filesystem::path path;
        if (GetDumpPath(path) == false)
        {
            return DUMP_FAILED;
        }
        std::ofstream file(path, std::ios::trunc);
        if (file.is_open() == false)
        {
            return DUMP_FAILED;
        }

        const char* speakerName = speaker->GetDisplayFullName();
        file << "Dialogue options of " << (speakerName != nullptr ? speakerName : "?") << " (" << std::format("{:08X}", speaker->GetFormID()) << "): "
             << options.size() << " found in " << milliseconds << " ms\n";
        for (const Option& option : options)
        {
            file << "\n[" << option.quest << "] \"" << option.prompt << "\"\n";
            file << "    topic " << std::format("{:08X}", option.topicId) << ", response " << std::format("{:08X}", option.infoId)
                 << ", said before: " << (option.said == true ? "yes" : "no") << ", say once: " << (option.sayOnce == true ? "yes" : "no") << "\n";
            for (const std::string& response : option.responses)
            {
                file << "    -> " << response << "\n";
            }
        }
        return static_cast<int>(options.size());
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("Dialogue options could not be worked out: {}", e.what());
        return DUMP_FAILED;
    }
}
} // namespace DialogueOptions

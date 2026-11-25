#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <NearbyObjects.h>
#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <string_view>

namespace
{
constexpr float GAME_UNITS_PER_METER = 71.021f; // as the mod's scripts convert them
constexpr float MAX_SEARCH_METERS = 50.0f;

// Unnamed objects are recognized by their model (eg "Clutter\WoodFires\Campfire01LandBurning.nif"). The first entry whose text
// is part of the model's path, and none of whose exclusions are, gives the description
struct ModelRule
{
    std::string_view contains;
    std::string_view excludes;
    std::string_view description;
};

constexpr ModelRule MODEL_RULES[] = {
    {"\\signage\\", "", ""}, // shop signs: "Frozen Hearth" is not a hearth
    {"giantcampfire", "off", "a large burning campfire"},
    {"giantcampfire", "", "a large campfire that has gone out"},
    {"campfire", "off", "a burning campfire"},
    {"campfire", "", "a campfire that has gone out"},
    {"fireplacewood", "off", "a fire burning in the fireplace"},
    {"fireplacewood", "", "a fireplace with no fire in it"},
    {"firepit", "", "a fire pit"},
    {"hearth", "", "a hearth"},
    {"brazier", "", "a brazier"},
    {"spitpot", "", "a cooking pot over the fire"},
    {"cookingspit", "", "a cooking spit"},
    {"cookingstand", "", "a cooking stand"},
    {"\\tents\\", "", "a tent"},
    {"bedroll", "", "a bedroll"},
    {"handcart", "wheel", "a cart"},
    {"vendorcart", "", "a vendor's cart"},
    {"rowboat", "", "a rowboat"},
    {"longboat", "", "a boat"},
};

// Parts of objects that share a model rule's text but are not the object itself (eg a cart's wheel or its crate)
constexpr std::string_view EXCLUDED_PARTS[] = {"wheel", "crate", "canopy", "loose"};

std::string ToLower(std::string_view text)
{
    std::string result(text);
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c)
                   {
                       return static_cast<char>(std::tolower(c));
                   });
    return result;
}

std::string_view GetModelDescription(RE::TESBoundObject* base)
{
    RE::TESModel* model = skyrim_cast<RE::TESModel*>(base);
    if (model == nullptr)
    {
        return {};
    }
    const char* modelPath = model->GetModel();
    if (modelPath == nullptr || modelPath[0] == '\0')
    {
        return {};
    }
    std::string path = ToLower(modelPath);
    for (const std::string_view& part : EXCLUDED_PARTS)
    {
        if (path.find(part) != std::string::npos)
        {
            return {};
        }
    }
    for (const ModelRule& rule : MODEL_RULES)
    {
        if (path.find(rule.contains) == std::string::npos)
        {
            continue;
        }
        if (rule.excludes.empty() == false && path.find(rule.excludes) != std::string::npos)
        {
            continue;
        }
        return rule.description;
    }
    return {};
}

// Named furniture that tells something about a place: crafting stations (a forge, a cooking pot, an alchemy lab, ...) and beds
std::string GetFurnitureDescription(RE::TESBoundObject* base)
{
    RE::TESFurniture* furniture = base->As<RE::TESFurniture>();
    if (furniture == nullptr)
    {
        return {};
    }
    const char* name = furniture->GetName();
    if (name == nullptr || name[0] == '\0')
    {
        return {};
    }
    std::string lowerName = ToLower(name);
    bool isWorkbench = furniture->workBenchData.benchType.get() != RE::TESFurniture::WorkBenchData::BenchType::kNone;
    bool isBed = lowerName.find("bed") != std::string::npos;
    if (isWorkbench == false && isBed == false)
    {
        return {};
    }
    bool startsWithVowel = std::string_view("aeiou").find(lowerName[0]) != std::string_view::npos;
    return std::string(startsWithVowel == true ? "an " : "a ") + lowerName;
}

std::string GetDescription(RE::TESObjectREFR* reference)
{
    RE::TESBoundObject* base = reference->GetBaseObject();
    if (base == nullptr)
    {
        return {};
    }
    std::string furniture = GetFurnitureDescription(base);
    if (furniture.empty() == false)
    {
        return furniture;
    }
    return std::string(GetModelDescription(base));
}
} // namespace

namespace NearbyObjects
{
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* center, float maxDistanceMeters, std::int32_t maxCount)
{
    std::vector<std::string> result;
    if (center == nullptr || maxDistanceMeters <= 0 || maxCount <= 0)
    {
        return result;
    }
    RE::TES* tes = RE::TES::GetSingleton();
    if (tes == nullptr)
    {
        return result;
    }
    float radius = std::min(maxDistanceMeters, MAX_SEARCH_METERS) * GAME_UNITS_PER_METER;
    try
    {
        // nearest distance per kind of object
        std::map<std::string, float> nearest;
        RE::NiPoint3 centerPosition = center->GetPosition();
        tes->ForEachReferenceInRange(center, radius, [&](RE::TESObjectREFR* reference)
                                     {
                                         if (reference == nullptr || reference == center || reference->IsDisabled() == true || reference->IsDeleted() == true)
                                         {
                                             return RE::BSContainer::ForEachResult::kContinue;
                                         }
                                         std::string description = GetDescription(reference);
                                         if (description.empty() == true)
                                         {
                                             return RE::BSContainer::ForEachResult::kContinue;
                                         }
                                         float distance = reference->GetPosition().GetDistance(centerPosition);
                                         std::map<std::string, float>::iterator found = nearest.find(description);
                                         if (found == nearest.end() || distance < found->second)
                                         {
                                             nearest[description] = distance;
                                         }
                                         return RE::BSContainer::ForEachResult::kContinue;
                                     });

        std::vector<std::pair<float, std::string>> sorted;
        for (const auto& [description, distance] : nearest)
        {
            sorted.emplace_back(distance, description);
        }
        std::sort(sorted.begin(), sorted.end());
        for (const std::pair<float, std::string>& entry : sorted)
        {
            if (static_cast<std::int32_t>(result.size()) >= maxCount)
            {
                break;
            }
            long meters = std::max(1L, std::lround(entry.first / GAME_UNITS_PER_METER));
            result.push_back(entry.second + " (" + std::to_string(meters) + " m)");
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The objects around a character could not be worked out: {}", e.what());
    }
    return result;
}
} // namespace NearbyObjects

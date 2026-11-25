#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <OwnedItems.h>
#include <algorithm>
#include <cctype>
#include <functional>
#include <map>

namespace
{
constexpr float GAME_UNITS_PER_METER = 71.021f; // as the mod's scripts convert them
constexpr float MAX_SEARCH_METERS = 50.0f;
constexpr std::int32_t SINGLE_ITEM = 1;

std::string ToLower(std::string text)
{
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c)
                   {
                       return static_cast<char>(std::tolower(c));
                   });
    return text;
}

bool IsOwnedBy(RE::TESObjectREFR* reference, RE::Actor* owner)
{
    RE::TESForm* referenceOwner = reference->GetOwner();
    if (referenceOwner == nullptr)
    {
        return false;
    }
    if (referenceOwner == owner->GetActorBase() || referenceOwner == owner->GetTemplateBase())
    {
        return true;
    }
    RE::TESFaction* faction = referenceOwner->As<RE::TESFaction>();
    return faction != nullptr && owner->IsInFaction(faction);
}

// Calls the visitor for every item lying or hanging within the distance of the owner that belongs to them
void ForEachOwnedItem(RE::Actor* owner, float maxDistanceMeters, const std::function<void(RE::TESObjectREFR*, const std::string&, float)>& visit)
{
    RE::TES* tes = RE::TES::GetSingleton();
    if (tes == nullptr || owner == nullptr || maxDistanceMeters <= 0)
    {
        return;
    }
    float radius = std::min(maxDistanceMeters, MAX_SEARCH_METERS) * GAME_UNITS_PER_METER;
    RE::NiPoint3 ownerPosition = owner->GetPosition();
    tes->ForEachReferenceInRange(owner, radius, [&](RE::TESObjectREFR* reference)
                                 {
                                     if (reference == nullptr || reference->IsDisabled() == true || reference->IsDeleted() == true)
                                     {
                                         return RE::BSContainer::ForEachResult::kContinue;
                                     }
                                     RE::TESBoundObject* base = reference->GetBaseObject();
                                     if (base == nullptr || base->IsInventoryObject() == false || IsOwnedBy(reference, owner) == false)
                                     {
                                         return RE::BSContainer::ForEachResult::kContinue;
                                     }
                                     const char* name = reference->GetDisplayFullName();
                                     if (name == nullptr || name[0] == '\0')
                                     {
                                         return RE::BSContainer::ForEachResult::kContinue;
                                     }
                                     visit(reference, name, reference->GetPosition().GetDistance(ownerPosition));
                                     return RE::BSContainer::ForEachResult::kContinue;
                                 });
}

std::int32_t GetItemCount(RE::TESObjectREFR* reference)
{
    std::int32_t count = reference->extraList.GetCount();
    return count > 0 ? count : SINGLE_ITEM;
}
} // namespace

namespace OwnedItems
{
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* owner, float maxDistanceMeters, std::int32_t maxCount)
{
    std::vector<std::string> result;
    if (owner == nullptr || maxCount <= 0)
    {
        return result;
    }
    try
    {
        std::map<std::string, std::pair<float, std::int32_t>> items; // name -> nearest distance, count
        ForEachOwnedItem(owner, maxDistanceMeters, [&](RE::TESObjectREFR* reference, const std::string& name, float distance)
                         {
                             std::map<std::string, std::pair<float, std::int32_t>>::iterator found = items.find(name);
                             if (found == items.end())
                             {
                                 items[name] = {distance, GetItemCount(reference)};
                             }
                             else
                             {
                                 found->second.first = std::min(found->second.first, distance);
                                 found->second.second += GetItemCount(reference);
                             }
                         });
        std::vector<std::pair<float, std::string>> sorted;
        for (const auto& [name, details] : items)
        {
            std::string text = details.second > SINGLE_ITEM ? name + " (" + std::to_string(details.second) + ")" : name;
            sorted.emplace_back(details.first, text);
        }
        std::sort(sorted.begin(), sorted.end());
        for (const std::pair<float, std::string>& entry : sorted)
        {
            if (static_cast<std::int32_t>(result.size()) >= maxCount)
            {
                break;
            }
            result.push_back(entry.second);
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The items belonging to a character could not be worked out: {}", e.what());
    }
    return result;
}

std::int32_t AllowTaking(RE::StaticFunctionTag*, RE::Actor* owner, std::vector<std::string> itemNames, float maxDistanceMeters)
{
    RE::PlayerCharacter* player = RE::PlayerCharacter::GetSingleton();
    if (owner == nullptr || player == nullptr || itemNames.empty() == true)
    {
        return 0;
    }
    std::vector<std::string> wanted;
    for (const std::string& itemName : itemNames)
    {
        wanted.push_back(ToLower(itemName));
    }
    std::int32_t allowed = 0;
    try
    {
        std::vector<RE::TESObjectREFR*> references;
        ForEachOwnedItem(owner, maxDistanceMeters, [&](RE::TESObjectREFR* reference, const std::string& name, float)
                         {
                             std::string lowerName = ToLower(name);
                             if (std::find(wanted.begin(), wanted.end(), lowerName) != wanted.end())
                             {
                                 references.push_back(reference);
                             }
                         });
        // ownership is changed once the search is over, as changing it affects what the search finds
        for (RE::TESObjectREFR* reference : references)
        {
            reference->SetOwner(player->GetActorBase());
            allowed += GetItemCount(reference);
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The player could not be allowed to take a character's items: {}", e.what());
    }
    return allowed;
}
} // namespace OwnedItems

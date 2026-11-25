#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <Theft.h>
#include <map>
#include <mutex>

namespace
{
constexpr RE::FormID GOLD_FORM_ID = 0xF;
constexpr RE::FormID JEWELRY_KEYWORD_ID = 0x8F95A;          // VendorItemJewelry
constexpr RE::FormID CLOTHING_JEWELRY_KEYWORD_ID = 0x6BBE9; // ArmorJewelry
constexpr std::int32_t VALUABLE_ITEM_VALUE = 500;
constexpr std::int32_t SINGLE_ITEM = 1;

struct TakenItem
{
    RE::TESBoundObject* item = nullptr;
    std::int32_t count = 0;
    std::int32_t value = 0; // of all of them
};

std::mutex stateMutex;
std::map<RE::FormID, std::map<RE::TESBoundObject*, std::int32_t>> rememberedInventories; // owner -> item -> count
std::map<RE::FormID, std::vector<TakenItem>> takenItems;                                 // owner -> what the player took

bool HasKeyword(RE::TESBoundObject* item, RE::FormID keywordId)
{
    RE::BGSKeywordForm* keywords = item->As<RE::BGSKeywordForm>();
    return keywords != nullptr && keywords->HasKeywordID(keywordId) == true;
}

std::string Describe(const TakenItem& taken, const std::string& preciousReason)
{
    const char* name = taken.item->GetName();
    std::string text = taken.count > SINGLE_ITEM ? std::to_string(taken.count) + " " + name : std::string(name);
    if (taken.item->GetFormID() == GOLD_FORM_ID)
    {
        return std::to_string(taken.count) + " gold";
    }
    text += " (worth " + std::to_string(taken.value);
    if (preciousReason.empty() == false)
    {
        text += ", precious: " + preciousReason;
    }
    return text + ")";
}
} // namespace

namespace Theft
{
std::string GetPreciousReason(RE::TESBoundObject* item, RE::InventoryEntryData* entry, std::int32_t value)
{
    if (item == nullptr)
    {
        return {};
    }
    if (entry != nullptr && entry->IsQuestObject() == true)
    {
        return "important";
    }
    if (HasKeyword(item, JEWELRY_KEYWORD_ID) == true || HasKeyword(item, CLOTHING_JEWELRY_KEYWORD_ID) == true)
    {
        return "jewelry";
    }
    if (value >= VALUABLE_ITEM_VALUE)
    {
        return "valuable";
    }
    return {};
}

bool IsPrecious(RE::TESBoundObject* item, RE::InventoryEntryData* entry, std::int32_t value)
{
    return GetPreciousReason(item, entry, value).empty() == false;
}

void RememberInventory(RE::StaticFunctionTag*, RE::Actor* owner)
{
    if (owner == nullptr)
    {
        return;
    }
    try
    {
        std::map<RE::TESBoundObject*, std::int32_t> counts;
        for (const auto& [item, count] : owner->GetInventoryCounts())
        {
            if (item != nullptr && count > 0)
            {
                counts[item] = count;
            }
        }
        std::lock_guard<std::mutex> lock(stateMutex);
        rememberedInventories[owner->GetFormID()] = std::move(counts);
        takenItems.erase(owner->GetFormID());
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The inventory of a character could not be noted: {}", e.what());
    }
}

std::vector<std::string> GetTakenItems(RE::StaticFunctionTag*, RE::Actor* owner)
{
    std::vector<std::string> result;
    if (owner == nullptr)
    {
        return result;
    }
    try
    {
        std::map<RE::TESBoundObject*, std::int32_t> before;
        {
            std::lock_guard<std::mutex> lock(stateMutex);
            std::map<RE::FormID, std::map<RE::TESBoundObject*, std::int32_t>>::iterator found = rememberedInventories.find(owner->GetFormID());
            if (found == rememberedInventories.end())
            {
                return result;
            }
            before = std::move(found->second);
            rememberedInventories.erase(found);
        }
        RE::TESObjectREFR::InventoryItemMap now = owner->GetInventory();
        std::vector<TakenItem> taken;
        for (const auto& [item, count] : before)
        {
            RE::TESObjectREFR::InventoryItemMap::iterator current = now.find(item);
            std::int32_t countNow = current != now.end() ? current->second.first : 0;
            if (countNow >= count)
            {
                continue;
            }
            TakenItem entry;
            entry.item = item;
            entry.count = count - countNow;
            entry.value = item->GetGoldValue() * entry.count;
            taken.push_back(entry);
            RE::InventoryEntryData* data = current != now.end() ? current->second.second.get() : nullptr;
            result.push_back(Describe(entry, GetPreciousReason(item, data, item->GetGoldValue())));
        }
        std::lock_guard<std::mutex> lock(stateMutex);
        takenItems[owner->GetFormID()] = std::move(taken);
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("What was taken from a character could not be worked out: {}", e.what());
    }
    return result;
}

std::int32_t ReportTheft(RE::StaticFunctionTag*, RE::Actor* owner)
{
    RE::PlayerCharacter* player = RE::PlayerCharacter::GetSingleton();
    if (owner == nullptr || player == nullptr)
    {
        return 0;
    }
    std::vector<TakenItem> taken;
    {
        std::lock_guard<std::mutex> lock(stateMutex);
        std::map<RE::FormID, std::vector<TakenItem>>::iterator found = takenItems.find(owner->GetFormID());
        if (found == takenItems.end())
        {
            return 0;
        }
        taken = std::move(found->second);
        takenItems.erase(found);
    }
    std::int32_t total = 0;
    try
    {
        for (const TakenItem& item : taken)
        {
            // as when the game sees the player take something that is not theirs: the owner is the one who saw it
            player->StealAlarm(owner, item.item, item.count, item.value, owner->GetActorBase(), false);
            total += item.value;
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("A theft could not be reported: {}", e.what());
    }
    return total;
}

bool IsItemOwnedBy(RE::StaticFunctionTag*, RE::TESForm* item, RE::Actor* owner)
{
    RE::PlayerCharacter* player = RE::PlayerCharacter::GetSingleton();
    RE::TESBoundObject* boundItem = item != nullptr ? item->As<RE::TESBoundObject>() : nullptr;
    if (player == nullptr || boundItem == nullptr || owner == nullptr)
    {
        return false;
    }
    try
    {
        RE::TESObjectREFR::InventoryItemMap inventory = player->GetInventory([boundItem](RE::TESBoundObject& candidate)
                                                                             {
                                                                                 return &candidate == boundItem;
                                                                             });
        for (auto& [candidate, data] : inventory)
        {
            RE::InventoryEntryData* entry = data.second.get();
            // items without an owner are the player's: they do not belong to the actor
            if (entry != nullptr && entry->GetOwner() != nullptr && entry->IsOwnedBy(owner, false) == true)
            {
                return true;
            }
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The owner of an item could not be worked out: {}", e.what());
    }
    return false;
}
} // namespace Theft

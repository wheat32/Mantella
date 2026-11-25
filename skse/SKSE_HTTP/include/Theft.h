#pragma once

#include "RE/Skyrim.h"
#include <string>
#include <vector>

// What the player takes from an NPC's inventory once the NPC opens it to them, and reporting it as theft. The game does not count
// taking things from an inventory that was opened to the player as stealing: the NPC decides whether they mind
namespace Theft
{
// Notes what the actor carries, before their inventory is opened to the player
void RememberInventory(RE::StaticFunctionTag*, RE::Actor* owner);

// What the player took since RememberInventory, eg "a Silver Ring (worth 60, precious: jewelry)". Kept for ReportTheft
std::vector<std::string> GetTakenItems(RE::StaticFunctionTag*, RE::Actor* owner);

// Reports what the player last took from the actor as theft, the way the game does when it sees the player steal: the actor is
// the witness, so the bounty goes to the hold even without a guard nearby, and is gone if the witness dies before reporting it.
// Returns the value of what was reported
std::int32_t ReportTheft(RE::StaticFunctionTag*, RE::Actor* owner);

// Whether an item the player carries (eg one just picked up) belongs to the given actor, or to a faction they are in
bool IsItemOwnedBy(RE::StaticFunctionTag*, RE::TESForm* item, RE::Actor* owner);

// Whether an item counts as precious to its owner: jewelry, quest items, or anything very valuable
bool IsPrecious(RE::TESBoundObject* item, RE::InventoryEntryData* entry, std::int32_t value);

// Why an item is precious ("jewelry", "important", "valuable"), "" if it is not
std::string GetPreciousReason(RE::TESBoundObject* item, RE::InventoryEntryData* entry, std::int32_t value);
} // namespace Theft

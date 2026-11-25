#pragma once

#include "RE/Skyrim.h"
#include <string>
#include <vector>

// Items lying or hanging around a character that belong to them (or to a faction they are in), which the player would steal by
// taking them. With the character's permission, the player becomes their owner
namespace OwnedItems
{
// Returns the names of the items within the given distance (in meters) that belong to the owner, nearest first, with how many
// there are if more than one, eg "Salmon Meat (3)"
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* owner, float maxDistanceMeters, std::int32_t maxCount);

// Makes the player the owner of the owner's items within the given distance whose names are listed (without the count), so that
// taking them is no longer stealing. Returns how many items the player may now take
std::int32_t AllowTaking(RE::StaticFunctionTag*, RE::Actor* owner, std::vector<std::string> itemNames, float maxDistanceMeters);
} // namespace OwnedItems

#pragma once

#include "RE/Skyrim.h"
#include <string>
#include <vector>

// The notable things a character carries, for NPCs to possibly bring up in conversation
namespace NotableItems
{
// Returns the names of the notable things the carrier has with them, the most interesting first: a lot of gold, notes and
// maps (with what the game says about them), keys, valuable items and books. What is worn or wielded is left out
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* carrier, std::int32_t minimumGold, std::int32_t minimumItemValue, std::int32_t maximumItems);
} // namespace NotableItems

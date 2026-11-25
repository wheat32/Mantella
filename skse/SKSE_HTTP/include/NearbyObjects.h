#pragma once

#include "RE/Skyrim.h"
#include <string>
#include <vector>

// The notable objects around a character (a burning campfire, a tent, a forge, ...), so that NPCs know what is around them
namespace NearbyObjects
{
// Returns descriptions of the notable objects within the given distance (in meters) of the center, nearest first, eg
// "a burning campfire (3 m)". Each kind of object is listed once, at its nearest
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* center, float maxDistanceMeters, std::int32_t maxCount);
} // namespace NearbyObjects

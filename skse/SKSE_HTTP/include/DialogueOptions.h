#pragma once

#include "RE/Skyrim.h"

// Research for letting the player choose the game's own dialogue options by voice: works out which dialogue options an NPC
// currently offers the player, without the dialogue menu being open.
namespace DialogueOptions
{
// Writes the dialogue options of the speaker to a text file in Documents/My Games/Mantella.
// Returns the number of options found, or a negative number if they could not be worked out
int Dump(RE::StaticFunctionTag*, RE::Actor* speaker);
} // namespace DialogueOptions

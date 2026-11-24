#pragma once

#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include "REL/Relocation.h"
#include "SKSE/Trampoline.h"
#include "SKSE/Logger.h"

// CommonLibSSE
#include "RE/T/TESObjectREFR.h"
#include "RE/T/TESForm.h"
#include "RE/B/BGSBaseAlias.h"
#include "RE/B/BSFixedString.h"
#include "RE/B/BSTEvent.h"
#include "RE/S/SubtitleManager.h"

// Standard
#include <string>
#include <array>

#ifdef SKYRIM_AE
#define OFFSET(se, ae) ae
#else
#define OFFSET(se, ae) se
#endif

// Address Library

namespace stl
{
using namespace SKSE::stl;

namespace Detail
{
constexpr std::size_t TRAMPOLINE_ALLOC_SIZE = 64;
constexpr std::size_t CALL_INSTRUCTION_SIZE = 5;
} // namespace Detail

template <class T>
void write_thunk_call(std::uintptr_t a_src)
{
    SKSE::Trampoline& trampoline = SKSE::GetTrampoline();
    SKSE::AllocTrampoline(Detail::TRAMPOLINE_ALLOC_SIZE);
    T::func = trampoline.write_call<Detail::CALL_INSTRUCTION_SIZE>(a_src, T::thunk);
}
} // namespace stl

using namespace std::literals;
using namespace SKSE::log;

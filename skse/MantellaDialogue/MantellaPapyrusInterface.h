#pragma once
#include <string> // For std::string

namespace MantellaPapyrusInterface
{

namespace Detail
{
constexpr RE::FormID MANTELLA_INTERFACE_QUEST_FORM_ID = 0x03D41A;
constexpr RE::FormID MANTELLA_REPOSITORY_QUEST_FORM_ID = 0xD62;
constexpr int INVALID_SERVER_PORT = -1;
} // namespace Detail

static inline std::string PreviousSentEvent = "";

void AddMantellaEvent(std::string msg, bool deduplicate = true)
{
    if (deduplicate && msg == PreviousSentEvent)
    {
        logger::debug("Skipping duplicate event: {}", msg);
        return;
    }
    PreviousSentEvent = msg;

    const char* targetFunction = "AddMantellaEvent";
    RE::BSScript::Internal::VirtualMachine* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
    RE::TESQuest* mantellaQuest = RE::TESDataHandler::GetSingleton()->LookupForm<RE::TESQuest>(Detail::MANTELLA_INTERFACE_QUEST_FORM_ID, "Mantella.esp");
    RE::VMHandle questHandle = vm->GetObjectHandlePolicy()->GetHandleForObject(mantellaQuest->GetFormType(), mantellaQuest);
    RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> callback;
    RE::BSTSmartPointer<RE::BSScript::Object> script = nullptr;
    if (vm->FindBoundObject(questHandle, "MantellaInterface", script))
    {
        RE::BSScript::IFunctionArguments* args = RE::MakeFunctionArguments(std::move(msg));
        vm->DispatchMethodCall1(script, targetFunction, args, callback);
    }
    else
    {
        logger::error("!!! Failed to find MantellaInterface script");
    }
}

RE::VMHandle GetMantellaRepositoryHandle()
{
    RE::BSScript::Internal::VirtualMachine* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
    RE::TESQuest* mantellaQuest = RE::TESDataHandler::GetSingleton()->LookupForm<RE::TESQuest>(Detail::MANTELLA_REPOSITORY_QUEST_FORM_ID, "Mantella.esp");
    RE::VMHandle questHandle = vm->GetObjectHandlePolicy()->GetHandleForObject(mantellaQuest->GetFormType(), mantellaQuest);
    return questHandle;
}

bool GetMantellaMcmSetting(std::string propertyName, RE::BSScript::Variable& a_getVal)
{
    RE::VMHandle questHandle = GetMantellaRepositoryHandle();
    RE::BSScript::Internal::VirtualMachine* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
    RE::BSTSmartPointer<RE::BSScript::Object> script = nullptr;
    if (vm->FindBoundObject(questHandle, "MantellaRepository", script))
    {
        RE::BSScript::Variable* propertyPointer = script->GetProperty(propertyName);
        if (propertyPointer == nullptr)
        {
            logger::error("!!! Failed to get Mantella setting {}", propertyName);
            return false;
        }
        a_getVal = *propertyPointer;
        return true;
    }
    logger::error("!!! Failed to find MantellaRepository script");
    return false;
}

bool GetMantellaEnableVanillaDialogueAwareness()
{
    RE::BSScript::Variable property;
    bool result = GetMantellaMcmSetting("enableVanillaDialogueAwareness", property);

    if (result && property.IsBool())
    {
        return property.GetBool();
    }
    else
    {
        logger::error("!!! Failed to get Mantella setting enableVanillaDialogueAwareness");
    }
    return true;
}

/// <returns>The port the mantella server is reachable under (From the Mcm)</returns>
int GetMantellaServerPort()
{
    RE::BSScript::Variable property;
    bool result = GetMantellaMcmSetting("HttpPort", property);
    if (result && property.IsInt())
    {
        int port = property.GetSInt();
        return port;
    }
    return Detail::INVALID_SERVER_PORT;
}

} // namespace MantellaPapyrusInterface

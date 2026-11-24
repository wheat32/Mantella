#include "InjectTopic.h"

RE::Actor* injectSpeaker = nullptr;
RE::BSString injectSubtitle = "";
RE::TESTopic* injectTopic = nullptr;

bool InjectTopicContainsInfoId(RE::FormID topicInfoID)
{
    if (injectTopic == nullptr)
    {
        return false;
    }

    SKSE::log::debug("Checking if topic {:x} contains topicInfo {:x}", injectTopic->GetFormID(), topicInfoID);
    for (uint32_t i = 0; i < injectTopic->numTopicInfos; i++)
    {
        SKSE::log::debug("Checking if topic {:x}'s topicInfo {:x} == {:x}", injectTopic->GetFormID(), injectTopic->topicInfos[i]->GetFormID(), topicInfoID);
        if (topicInfoID == injectTopic->topicInfos[i]->GetFormID())
        {
            return true;
        }
    }
    return false;
}
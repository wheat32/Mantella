#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <NotableItems.h>
#include <algorithm>

namespace
{
constexpr RE::FormID GOLD_FORM_ID = 0xF;
constexpr std::uint32_t ITEM_CARD_DESCRIPTION_FIELD = 'MANC'; // the CNAM field of a book, as the game asks for it
constexpr std::int32_t SINGLE_ITEM = 1;

// The order in which notable items are passed on, as only a few of them are
enum class Interest
{
    NoteOrMap,
    Key,
    Valuable,
    Book
};

struct NotableItem
{
    Interest interest = Interest::Book;
    std::int32_t value = 0;
    std::string text;
};

std::string GetItemCardDescription(RE::TESObjectBOOK* book)
{
    RE::BSString description;
    book->itemCardDescription.GetDescription(description, book, ITEM_CARD_DESCRIPTION_FIELD);
    return description.empty() == true ? std::string() : std::string(description.c_str());
}

std::string GetItemText(const char* name, std::int32_t count, const std::string& description)
{
    std::string text = count > SINGLE_ITEM ? std::to_string(count) + " " + name : std::string(name);
    if (description.empty() == false)
    {
        text += " (" + description + ")";
    }
    return text;
}
} // namespace

namespace NotableItems
{
std::vector<std::string> Get(RE::StaticFunctionTag*, RE::Actor* carrier, std::int32_t minimumGold, std::int32_t minimumItemValue, std::int32_t maximumItems)
{
    std::vector<std::string> result;
    if (carrier == nullptr || maximumItems <= 0)
    {
        return result;
    }

    try
    {
        std::vector<NotableItem> items;
        std::int32_t gold = 0;
        RE::TESObjectREFR::InventoryItemMap inventory = carrier->GetInventory();
        for (const auto& [item, data] : inventory)
        {
            std::int32_t count = data.first;
            const std::unique_ptr<RE::InventoryEntryData>& entry = data.second;
            if (item == nullptr || count <= 0)
            {
                continue;
            }
            if (item->GetFormID() == GOLD_FORM_ID)
            {
                gold = count;
                continue;
            }
            if (entry != nullptr && entry->IsWorn() == true)
            {
                continue;
            }
            const char* name = item->GetName();
            if (name == nullptr || name[0] == '\0')
            {
                continue;
            }

            NotableItem notable;
            notable.value = item->GetGoldValue();
            std::string description;
            if (item->Is(RE::FormType::Book) == true)
            {
                RE::TESObjectBOOK* book = item->As<RE::TESObjectBOOK>();
                bool isSpellTome = book != nullptr && book->TeachesSpell() == true;
                if (book != nullptr && isSpellTome == false)
                {
                    description = GetItemCardDescription(book);
                }
                if (book != nullptr && isSpellTome == false && (book->IsNoteScroll() == true || description.empty() == false))
                {
                    notable.interest = Interest::NoteOrMap;
                }
                else if (notable.value >= minimumItemValue)
                {
                    notable.interest = Interest::Valuable;
                }
                else if (isSpellTome == true)
                {
                    continue; // a cheap spell tome is nothing special
                }
                else
                {
                    notable.interest = Interest::Book;
                }
            }
            else if (item->Is(RE::FormType::KeyMaster) == true)
            {
                notable.interest = Interest::Key;
            }
            else if (notable.value >= minimumItemValue)
            {
                notable.interest = Interest::Valuable;
            }
            else
            {
                continue;
            }
            notable.text = GetItemText(name, count, description);
            items.push_back(std::move(notable));
        }

        std::stable_sort(items.begin(), items.end(), [](const NotableItem& a, const NotableItem& b)
                         {
                             if (a.interest != b.interest)
                             {
                                 return a.interest < b.interest;
                             }
                             return a.value > b.value;
                         });

        if (gold >= minimumGold && minimumGold > 0)
        {
            result.push_back(std::to_string(gold) + " gold");
        }
        for (const NotableItem& notable : items)
        {
            if (static_cast<std::int32_t>(result.size()) >= maximumItems)
            {
                break;
            }
            result.push_back(notable.text);
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The notable items of a character could not be worked out: {}", e.what());
    }
    return result;
}
} // namespace NotableItems

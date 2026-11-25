#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include <NotableItems.h>
#include <Theft.h>
#include <algorithm>
#include <optional>

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

namespace
{
// The kinds of things a character can carry, in the order they are listed in
enum class Kind
{
    Gold,
    Food,
    Potions,
    Poisons,
    Ingredients,
    Ammunition,
    Weapons,
    Clothing,
    SoulGems,
    Scrolls,
    Books,
    Keys,
    OddsAndEnds,
    Count
};

constexpr const char* KIND_NAMES[] = {"gold", "food", "potions", "poisons", "ingredients", "arrows or bolts", "spare weapons", "spare clothing or armor", "soul gems", "scrolls", "books or notes", "keys", "odds and ends"};
static_assert(sizeof(KIND_NAMES) / sizeof(KIND_NAMES[0]) == static_cast<std::size_t>(Kind::Count));

std::optional<Kind> GetKind(RE::TESBoundObject* item)
{
    switch (item->GetFormType())
    {
        case RE::FormType::AlchemyItem:
        {
            RE::AlchemyItem* potion = item->As<RE::AlchemyItem>();
            if (potion == nullptr)
            {
                return std::nullopt;
            }
            if (potion->IsFood() == true)
            {
                return Kind::Food;
            }
            if (potion->IsPoison() == true)
            {
                return Kind::Poisons;
            }
            return Kind::Potions;
        }

        case RE::FormType::Ingredient:
            return Kind::Ingredients;

        case RE::FormType::Ammo:
            return Kind::Ammunition;

        case RE::FormType::Weapon:
            return Kind::Weapons;

        case RE::FormType::Armor:
            return Kind::Clothing;

        case RE::FormType::SoulGem:
            return Kind::SoulGems;

        case RE::FormType::Scroll:
            return Kind::Scrolls;

        case RE::FormType::Book:
            return Kind::Books;

        case RE::FormType::KeyMaster:
            return Kind::Keys;

        case RE::FormType::Misc:
            return Kind::OddsAndEnds;

        default:
            return std::nullopt;
    }
}
} // namespace

namespace NotableItems
{
std::vector<std::string> GetKinds(RE::StaticFunctionTag*, RE::Actor* carrier)
{
    std::vector<std::string> result;
    if (carrier == nullptr)
    {
        return result;
    }
    try
    {
        bool found[static_cast<std::size_t>(Kind::Count)] = {};
        RE::TESObjectREFR::InventoryItemMap inventory = carrier->GetInventory();
        for (const auto& [item, data] : inventory)
        {
            std::int32_t count = data.first;
            const std::unique_ptr<RE::InventoryEntryData>& entry = data.second;
            if (item == nullptr || count <= 0)
            {
                continue;
            }
            if (entry != nullptr && entry->IsWorn() == true)
            {
                continue;
            }
            std::optional<Kind> kind = item->GetFormID() == GOLD_FORM_ID ? std::optional<Kind>(Kind::Gold) : GetKind(item);
            if (kind.has_value() == true)
            {
                found[static_cast<std::size_t>(kind.value())] = true;
            }
        }
        for (std::size_t i = 0; i < static_cast<std::size_t>(Kind::Count); ++i)
        {
            if (found[i] == true)
            {
                result.push_back(KIND_NAMES[i]);
            }
        }
    }
    catch (const std::exception& e)
    {
        SKSE::log::warn("The kinds of things a character carries could not be worked out: {}", e.what());
    }
    return result;
}

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
            std::string preciousReason = Theft::GetPreciousReason(item, entry.get(), item->GetGoldValue());
            if (preciousReason.empty() == false)
            {
                notable.text += " (precious: " + preciousReason + ")";
            }
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

scriptName SKSE_HTTP hidden

function sendLocalhostHttpRequest(int typedDictionaryHandle, int port, string route, int timeout = 0) global native

function raiseOnHttpReplyReceived(int typedDictionaryHandle) global
    int handle = ModEvent.Create("SKSE_HTTP_OnHttpReplyReceived")
    if (handle)
        ModEvent.PushInt(handle, typedDictionaryHandle)
        ModEvent.Send(handle)
    endIf    
endFunction

function raiseOnHttpErrorReceived(int typedDictionaryHandle) global
    int handle = ModEvent.Create("SKSE_HTTP_OnHttpErrorReceived")
    if (handle)
        ModEvent.PushInt(handle, typedDictionaryHandle)
        ModEvent.Send(handle)
    endIf    
endFunction

; Dictionary

Int function createDictionary() global native
function clearAllDictionaries() global native

;/  Returns the value associated with the @key. If not, returns @default value
/;
String function getString(Int object, String key, String default="") global native
Int function getInt(Int object, String key, Int default=0) global native
Float function getFloat(Int object, String key, Float default=0.0) global native
Bool function getBool(Int object, String key, Bool default=false) global native
Int function getNestedDictionary(Int object, String key, Int default=0) global native
Int[] function getIntArray(Int object, String key) global native
Float[] function getFloatArray(Int object, String key) global native
String[] function getStringArray(Int object, String key) global native
Bool[] function getBoolArray(Int object, String key) global native
Int[] function getNestedDictionariesArray(Int object, String key) global native

;/  Inserts @key: @value pair. Replaces existing pair with the same @key
/;
Bool function setString(Int object, String key, String value) global native
function setInt(Int object, String key, Int value) global native
function setFloat(Int object, String key, Float value) global native
function setBool(Int object, String key, Bool value) global native
function setNestedDictionary(Int object, String key, Int value) global native
function setIntArray(Int object, String key, Int[] value) global native
function setFloatArray(Int object, String key, Float[] value) global native
Bool function setStringArray(Int object, String key, String[] value) global native
function setBoolArray(Int object, String key, Bool[] value) global native
function setNestedDictionariesArray(Int object, String key, Int[] value) global native

;/  Returns true, if the container has @key: value pair
/;
Bool function hasKey(Int object, String key) global native

;/  Returns type of the value associated with the @key.
    0 - no value, 1 - none, 2 - int, 3 - float, 4 - form, 5 - object, 6 - string
/;
Int function valueType(Int object, String key) global native

Function TakeScreenshot() global native
Function RenameScreenshot(String filename) global native
; Hides or shows the game's "ScreenShot: File '...' created." message
Function SetScreenshotMessageVisible(Bool visible) global native
; Research: writes the dialogue options the actor currently offers the player to Documents/My Games/Mantella/dialogue_options.txt.
; Returns how many were found, or a negative number on failure
Int Function DumpDialogueOptions(Actor speaker) global native
; The notable things the actor carries, the most interesting first: a lot of gold, notes and maps (with their description),
; keys, valuable items and books. What is worn or wielded is left out
String[] Function GetNotableItems(Actor carrier, Int minimumGold, Int minimumItemValue, Int maximumItems) global native
; The kinds of things the actor carries besides what they wear and wield ("food", "potions", "gold", ...). Empty if nothing
String[] Function GetCarriedItemKinds(Actor carrier) global native
; The notable objects within the distance (in meters) of the actor, nearest first, eg "a burning campfire (3 m)"
String[] Function GetNearbyObjects(Actor center, Float maxDistanceMeters, Int maxCount) global native
; The items within the distance (in meters) of the actor that belong to them (or their faction), eg "Salmon Meat (3)"
String[] Function GetOwnedItemsNearby(Actor owner, Float maxDistanceMeters, Int maxCount) global native
; Makes the player the owner of the actor's items within the distance whose names are listed, so that taking them is not stealing.
; Returns how many items the player may now take
Int Function AllowTakingOwnedItems(Actor owner, String[] itemNames, Float maxDistanceMeters) global native
; Notes what the actor carries, before their inventory is opened to the player (see GetTakenItems)
Function RememberInventory(Actor owner) global native
; What the player took from the actor since RememberInventory, eg "a Silver Ring (worth 60, precious: jewelry)"
String[] Function GetTakenItems(Actor owner) global native
; Reports what the player last took from the actor as theft, as the game does when it sees the player steal (the actor is the witness).
; Returns the value reported
Int Function ReportTheft(Actor owner) global native
; Whether an item the player carries belongs to the actor (or a faction they are in)
Bool Function IsItemOwnedBy(Form item, Actor owner) global native
VoiceType Function GetVoiceType(Actor actor) global native
Function SetVoiceType(Actor actor, VoiceType voice) global native
VoiceType Function GetRaceDefaultVoiceType(Actor actor) global native
Function SetRaceDefaultVoiceType(Actor actor, VoiceType voice) global native

;/  Stops/fades out the voice line currently playing on the actor.
    Returns true if a playing voice sound was stopped.
/;
Bool Function StopVoiceLine(Actor actor, Int fadeMs = 150) global native

; Returns the actors loaded around center within radius (in game units), nearest first, at most maxCount
Actor[] Function GetNearbyActors(Actor center, Float radius, Int maxCount) global native

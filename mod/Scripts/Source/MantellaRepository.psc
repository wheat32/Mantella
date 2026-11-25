Scriptname MantellaRepository extends Quest Conditional

Actor Property PlayerRef Auto

Spell property MantellaSpell auto
Spell property MantellaRemoveNpcSpell auto
Spell Property MantellaEndSpell auto
;Faction Property giafac_Sitters  Auto ;gia
;Faction Property giafac_Sleepers  Auto ;gia
;Faction Property giafac_talktome  Auto ;gia
Faction Property giafac_AllowFollower  Auto ;gia
Faction Property giafac_AllowAnger  Auto ;gia
Faction Property fac_AllowInventory  Auto
Faction Property giafac_AllowDialogue  Auto ;gia
Faction Property giafac_Following  Auto ;gia
Faction Property giafac_Mantella  Auto ;gia
Faction Property MantellaCombatTeamA  Auto
Faction Property MantellaCombatTeamB  Auto
quest property gia_FollowerQst auto ;gia
MantellaListenerScript Property ListenerScript Auto


bool property microphoneEnabled auto
bool property useHotkeyToStartMic auto
float property MantellaEffectResponseTimer auto
bool property showReminderMessages auto

int property MantellaStartHotkey auto
int property MantellaListenerTextHotkey auto
int property MantellaEndHotkey auto
int property MantellaToggleHotkey auto
int property MantellaEndConversationHotkey auto
int property MantellaFreeFlowHotkey auto ; no longer used: free-flow uses MantellaPushToTalkHotkey. Kept for saves made with version 8
int property MantellaPushToTalkHotkey auto
bool property pushToTalkEnabled auto
; When the free-flow talk key last started a conversation (real time in seconds). Kept here rather than on the conversation quest,
; whose script variables are reset when the quest is started
float property playerSpeaksFirstRequestTime auto
; A new random number each time a save is loaded (or a new game is started). Sent with every conversation, so that Mantella can tell
; that a save was loaded during a conversation: that conversation belongs to the game that was left, and is not remembered
int property playSessionId auto
float property conversationLeaveDistance auto ; meters, 0 = NPCs never leave because of distance
bool property noticeObjectsEnabled auto
; NPCs traveling with the player for a purpose, and the place where it is met (see SetCompanionDestination)
Actor[] companionActors
string[] companionDestinations
float property objectNoticeDistance auto ; meters

Function StartNewPlaySession()
    playSessionId = Utility.RandomInt(1, 2147483646)
EndFunction
bool property freeFlowUseNearest auto
bool property freeFlowEnabled auto
bool property showScreenshotMessages auto
bool property showNpcConversationMessages auto
bool property notableItemsEnabled auto
float property freeFlowDistance auto
bool property freeFlowIncludeCreatures auto
int property awarenessMaxCharacters auto
float property awarenessDistance auto
int property MantellaCustomGameEventHotkey auto
int property MantellaRadiantHotkey auto

bool property showDialogueItems auto Conditional

bool property radiantEnabled auto
bool property approachEnabled auto
float property radiantDistance auto
float property radiantFrequency auto
int property triggerRatio auto
bool property showRadiantDialogueMessages auto

string property playerCharacterDescription1 auto
string property playerCharacterDescription2 auto
bool property playerCharacterUsePlayerDescription2 auto
bool property playerCharacterVoicePlayerInput auto
string property playerCharacterVoiceModel auto
bool property playerTrackingUsePCName auto


bool property playerTrackingOnItemAdded auto
bool property playerTrackingOnItemRemoved auto
bool property playerTrackingOnSpellCast auto
bool property playerTrackingOnHit auto
bool property playerTrackingOnObjectEquipped auto
bool property playerTrackingOnObjectUnequipped auto
bool property playerTrackingOnPlayerBowShot auto
bool property playerTrackingOnSit auto
bool property playerTrackingOnGetUp auto

bool property playerTrackingOnLocationChange auto
bool property playerTrackingOnTimeChange auto
bool property playerTrackingOnWeatherChange auto


bool property playerEquipmentBody auto
bool property playerEquipmentHead auto
bool property playerEquipmentHands auto
bool property playerEquipmentFeet auto
bool property playerEquipmentAmulet auto
bool property playerEquipmentRightHand auto
bool property playerEquipmentLeftHand auto

int property worldID auto


bool property targetTrackingItemAdded auto 
bool property targetTrackingItemRemoved auto
bool property targetTrackingOnSpellCast auto
bool property targetTrackingOnHit auto
bool property targetTrackingOnCombatStateChanged auto
bool property targetTrackingOnObjectEquipped auto
bool property targetTrackingOnObjectUnequipped auto
bool property targetTrackingOnSit auto
bool property targetTrackingOnGetUp auto
bool property targetTrackingAngerState auto

bool property targetEquipmentBody auto
bool property targetEquipmentHead auto
bool property targetEquipmentHands auto
bool property targetEquipmentFeet auto
bool property targetEquipmentAmulet auto
bool property targetEquipmentRightHand auto
bool property targetEquipmentLeftHand auto

bool property enableVanillaDialogueAwareness auto
;bool property followingNPCsit auto ;gia
;bool property followingNPCsleep auto ;gia
;bool property NPCstopandTalk auto ;gia
bool property NPCPackage auto Conditional
;bool property NPCForgive auto ;gia
bool property NPCDialogue auto ;gia

bool property NPCdebugSelectModeEnabled auto
; bool restartMantellaExe = False
int property HttpPort auto


event OnInit()
    assignDefaultSettings(0, true)
    ; end any existing conversation that may still be running on the Mantella server when the mod is loaded
    (Quest.GetQuest("MantellaConversation") as MantellaConversation).EndConversation() 
endEvent

; event OnUpdate()
;     If (restartMantellaExe)
;         restartMantellaExe = false
;         MantellaLauncher.LaunchMantellaExe()
;     EndIf
; endEvent

; lastVersion is the previous MCM version number defined in 'MantellaMCM.psc' before the new update is applied.
; Whenever a new repository value OR a new MCM setting is added, up the MCM version number returned by `ManatellaMCM.GetVersion()`
; and add the corresponding default value here in a block corresponding to the version number like the examples below
; Doing it like this will only assign the defaul values to settings that haven't been initialized prior.
function assignDefaultSettings(int lastVersion, bool isFirstInit = false)
    If (lastVersion < 12 || isFirstInit)
        noticeObjectsEnabled = true
        objectNoticeDistance = 10
    EndIf
    If (lastVersion < 11 || isFirstInit)
        conversationLeaveDistance = 20
    EndIf
    If (lastVersion < 10 || isFirstInit)
        showNpcConversationMessages = false
        notableItemsEnabled = true
    EndIf
    If (lastVersion < 9 || isFirstInit)
        ; The push-to-talk key is set here, in the game, and reported to Mantella. V (47) by default.
        ; A key that was bound as the free-flow talk key in version 8 is carried over
        freeFlowEnabled = true
        pushToTalkEnabled = true
        MantellaPushToTalkHotkey = 47
        If (lastVersion >= 8 && !isFirstInit && MantellaFreeFlowHotkey > 0)
            MantellaPushToTalkHotkey = MantellaFreeFlowHotkey
        EndIf
        RegisterForKey(MantellaPushToTalkHotkey)
        showScreenshotMessages = false
    EndIf
    If (lastVersion < 8 || isFirstInit)
        MantellaToggleHotkey = -1
        MantellaEndConversationHotkey = -1
        freeFlowUseNearest = true
        freeFlowDistance = 5
        freeFlowIncludeCreatures = false
        awarenessMaxCharacters = 10
        awarenessDistance = 150
    EndIf
    If (lastVersion < 7 || isFirstInit)
        enableVanillaDialogueAwareness = true
    EndIf
    If (lastVersion < 5 || isFirstInit)
        showReminderMessages = true
    EndIf
    If (lastVersion < 4 || isFirstInit)
        playerTrackingOnTimeChange = true
        playerTrackingOnWeatherChange = true
    EndIf
    If (lastVersion < 3 || isFirstInit)
        worldID = 1
    EndIf
    If (lastVersion < 2 || isFirstInit)
        showRadiantDialogueMessages = true
    EndIf
    If (lastVersion < 1 || isFirstInit)
        microphoneEnabled = true
        useHotkeyToStartMic = false
        MantellaEffectResponseTimer = 180

        MantellaStartHotkey = -1
        MantellaListenerTextHotkey = 35
        BindPromptHotkey(MantellaListenerTextHotkey)
        MantellaEndHotkey = -1
        MantellaCustomGameEventHotkey = -1
        MantellaRadiantHotkey = -1

        showDialogueItems = true

        radiantEnabled = false
        approachEnabled = false
        radiantDistance = 20
        radiantFrequency = 10
        triggerRatio = 50


        playerCharacterDescription1 = ""
        playerCharacterDescription2 = ""
        playerCharacterUsePlayerDescription2 = false
        playerCharacterVoicePlayerInput = false
        playerCharacterVoiceModel = ""
        playerTrackingUsePCName = true

        
        playerTrackingOnItemAdded = true
        playerTrackingOnItemRemoved = true
        playerTrackingOnSpellCast = true
        playerTrackingOnHit = true
        playerTrackingOnLocationChange = true
        playerTrackingOnObjectEquipped = true
        playerTrackingOnObjectUnequipped = true
        playerTrackingOnPlayerBowShot = true
        playerTrackingOnSit = true
        playerTrackingOnGetUp = true

        playerEquipmentBody = true
        playerEquipmentHead = true
        playerEquipmentHands = true
        playerEquipmentFeet = true
        playerEquipmentAmulet = true
        playerEquipmentRightHand = true
        playerEquipmentLeftHand = true


        targetTrackingItemAdded = true
        targetTrackingItemRemoved = true
        targetTrackingOnSpellCast = true
        targetTrackingOnHit = true
        targetTrackingOnCombatStateChanged = true
        targetTrackingOnObjectEquipped = true
        targetTrackingOnObjectUnequipped = true
        targetTrackingOnSit = true
        targetTrackingOnGetUp = true
        targetTrackingAngerState = true

        targetEquipmentBody = true
        targetEquipmentHead = true
        targetEquipmentHands = true
        targetEquipmentFeet = true
        targetEquipmentAmulet = true
        targetEquipmentRightHand = true
        targetEquipmentLeftHand = true
        

	;followingNPCsit = false ;gia
	;followingNPCsleep = false ;gia
	;NPCstopandTalk = false ;gia
    NPCPackage = true
	;NPCForgive = false ;gia
	NPCDialogue = True ;gia
    
    NPCdebugSelectModeEnabled = false

        HttpPort = 4999
    EndIf
endFunction

function BindStartAddHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the start hotkey KeyMapChange
    UnregisterForKey(MantellaStartHotkey)
    MantellaStartHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

function BindPromptHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the prompt hotkey KeyMapChange
    UnregisterForKey(MantellaListenerTextHotkey)
    MantellaListenerTextHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

function BindEndHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the end hotkey KeyMapChange
    UnregisterForKey(MantellaEndHotkey)
    MantellaEndHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

function BindToggleHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the toggle hotkey KeyMapChange
    UnregisterForKey(MantellaToggleHotkey)
    MantellaToggleHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

function BindEndConversationHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the end conversation hotkey KeyMapChange
    UnregisterForKey(MantellaEndConversationHotkey)
    MantellaEndConversationHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

; Remembers where an NPC who follows the player is going with them. When the player gets there, the NPC parts ways
Function SetCompanionDestination(Actor companion, string destination)
    if !companion
        return
    endIf
    if !companionActors
        companionActors = new Actor[10]
        companionDestinations = new string[10]
    endIf
    int freeSlot = -1
    int i = 0
    while i < companionActors.Length
        if companionActors[i] == companion
            companionDestinations[i] = destination
            return
        elseIf freeSlot < 0 && (!companionActors[i] || companionDestinations[i] == "")
            freeSlot = i
        endIf
        i += 1
    endWhile
    if freeSlot >= 0
        companionActors[freeSlot] = companion
        companionDestinations[freeSlot] = destination
    endIf
EndFunction

; The companion still following the player whose destination is the given location, if any. They are forgotten after this,
; so that arriving is noticed once
Actor Function TakeArrivedCompanion(string locationName)
    if !companionActors || locationName == ""
        return None
    endIf
    int i = 0
    while i < companionActors.Length
        Actor companion = companionActors[i]
        string destination = companionDestinations[i]
        if companion && destination != "" && (StringUtil.Find(locationName, destination) >= 0 || StringUtil.Find(destination, locationName) >= 0)
            companionActors[i] = None
            companionDestinations[i] = ""
            if companion.IsInFaction(giafac_following) && !companion.IsDead()
                return companion
            endIf
        endIf
        i += 1
    endWhile
    return None
EndFunction

; Registers every key that is bound to one of the mod's controls. A key that is unregistered because one control no longer uses it
; would otherwise also stop working for another control that shares it
Function RegisterAllHotkeys()
    int[] keys = new int[9]
    keys[0] = MantellaStartHotkey
    keys[1] = MantellaListenerTextHotkey
    keys[2] = MantellaEndHotkey
    keys[3] = MantellaToggleHotkey
    keys[4] = MantellaEndConversationHotkey
    keys[5] = MantellaCustomGameEventHotkey
    keys[6] = MantellaRadiantHotkey
    keys[7] = MantellaPushToTalkHotkey
    keys[8] = -1
    int i = 0
    while i < keys.Length
        if keys[i] > 0
            RegisterForKey(keys[i])
        endIf
        i += 1
    endWhile
EndFunction

; Whether the key is (also) bound to one of the other controls of the mod, which then has to keep receiving it
bool function IsOtherHotkey(int keyCode)
    return keyCode == MantellaStartHotkey || keyCode == MantellaListenerTextHotkey || keyCode == MantellaEndHotkey || keyCode == MantellaToggleHotkey || keyCode == MantellaEndConversationHotkey || keyCode == MantellaCustomGameEventHotkey || keyCode == MantellaRadiantHotkey
endfunction

function BindPushToTalkHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the push-to-talk hotkey KeyMapChange
    if MantellaPushToTalkHotkey > 0 && !IsOtherHotkey(MantellaPushToTalkHotkey)
        UnregisterForKey(MantellaPushToTalkHotkey)
    endIf
    MantellaPushToTalkHotkey = keyCode
    if keyCode > 0
        RegisterForKey(keyCode)
    endIf
    ; Mantella is the one listening for the key while the player speaks, so it is told about the new key
    (Quest.GetQuest("MantellaConversation") as MantellaConversation).SendPushToTalkSettings()
endfunction

; The NPC the player is talking to when the free-flow talk key is pressed: the one under the crosshair, or else
; (if enabled in the MCM) the closest one within the configured distance who is on screen
Actor Function GetFreeFlowTarget()
    Actor target = (Game.GetCurrentCrosshairRef() as Actor)
    if !target
        if !freeFlowUseNearest
            return None
        endIf
        target = Game.FindClosestActorFromRef(PlayerRef, freeFlowDistance * 71.0210) ; meters to game units
        if !target || target == PlayerRef || !PlayerRef.HasLOS(target)
            return None
        endIf
        Keyword npcKeyword = Keyword.GetKeyword("ActorTypeNPC")
        if !freeFlowIncludeCreatures && npcKeyword && !target.HasKeyword(npcKeyword)
            return None
        endIf
    endIf
    if target == PlayerRef || target.IsDead() || target.IsHostileToActor(PlayerRef)
        return None
    endIf
    return target
EndFunction

function BindCustomGameEventHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the custom game event hotkey KeyMapChange
    UnregisterForKey(MantellaCustomGameEventHotkey)
    MantellaCustomGameEventHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

function BindRadiantHotkey(int keyCode)
    ;used by the MCM_GeneralSettings when updating the prompt hotkey KeyMapChange
    UnregisterForKey(MantellaRadiantHotkey)
    MantellaRadiantHotkey=keyCode
    RegisterForKey(keyCode)
    RegisterAllHotkeys()
endfunction

bool Function IsVR()
    return Debug.GetVersionNumber() == "1.4.15.0"
EndFunction

bool function restartMantellaExe()
    ; restartMantellaExe = true
    ; RegisterForSingleUpdate(1)
    MantellaLauncher.LaunchMantellaExe() 
    ;Note: If you need to debug this call to the SKSE plugin, you need to call it from the commented out single update above instead
    ;      or the VS debugger will crash (due to being called from the MCM thread?).
    ;      Check the corresponding commented out OnUpdate at the beginning of the script.
EndFunction

Event OnKeyDown(int KeyCode)
    ;this function was previously in MantellaListener Script back in Mantella 0.9.2
	;this ensures the right key is pressed and only activated while not in menu mode
    if !utility.IsInMenuMode()
        if KeyCode == MantellaPushToTalkHotkey && pushToTalkEnabled
            (Quest.GetQuest("MantellaConversation") as MantellaConversation).OnPushToTalkPressed()
        endIf
        if KeyCode == MantellaStartHotkey
            Actor targetRef = (Game.GetCurrentCrosshairRef() as actor)            
            if (targetRef) ;If we have a target under the crosshair, cast sepll on it
                MantellaSpell.cast(PlayerRef, targetRef)
                ;Utility.Wait(0.5)
            Else
                ListenerScript.StartGroupConversation()
            endIf        
        elseIf KeyCode == MantellaListenerTextHotkey
            If(!microphoneEnabled) ;Otherwise, try to open player text input if microphone is off
                MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
                if(conversation.IsRunning())
                    conversation.GetPlayerTextInput()
                endIf
            elseIf (useHotkeyToStartMic)
                MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
                if(conversation.IsRunning())
                    conversation.sendRequestForVoiceTranscribe()
                endIf
            endIf
        elseIf KeyCode == MantellaEndHotkey
            Actor targetRef = (Game.GetCurrentCrosshairRef() as actor)            
            if (targetRef) ;If we have a target under the crosshair, cast sepll on it
                MantellaRemoveNpcSpell.cast(PlayerRef, targetRef)
            else
                MantellaEndSpell.cast(PlayerRef)
            endIf
        elseIf KeyCode == MantellaToggleHotkey
            ; One key for both directions: an NPC who is not in the conversation is added to it (starting one if needed),
            ; an NPC who is in the conversation is removed from it. Without an NPC under the crosshair the key does nothing
            Actor targetRef = (Game.GetCurrentCrosshairRef() as actor)
            if (targetRef)
                MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
                if (conversation.IsRunning() && conversation.IsActorInConversation(targetRef))
                    MantellaRemoveNpcSpell.cast(PlayerRef, targetRef)
                else
                    MantellaSpell.cast(PlayerRef, targetRef)
                endIf
            endIf
        elseIf KeyCode == MantellaPushToTalkHotkey && freeFlowEnabled && pushToTalkEnabled
            ; Free-flow: meant to share its key with push-to-talk. Talking at an NPC who is not in the conversation brings them into it
            Actor targetRef = GetFreeFlowTarget()
            if (targetRef)
                MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
                if (!conversation.IsRunning())
                    conversation.SetPlayerSpeaksFirst(true)
                    MantellaSpell.cast(PlayerRef, targetRef)
                elseIf (!conversation.IsActorInConversation(targetRef))
                    MantellaSpell.cast(PlayerRef, targetRef)
                endIf
            endIf
        elseIf KeyCode == MantellaEndConversationHotkey
            ; Ends the whole conversation, no matter what is under the crosshair
            MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
            if (conversation.IsRunning())
                MantellaEndSpell.cast(PlayerRef)
            endIf
        elseIf KeyCode == MantellaCustomGameEventHotkey
            MantellaConversation conversation = Quest.GetQuest("MantellaConversation") as MantellaConversation
            if(conversation.IsRunning())
                UIExtensions.InitMenu("UITextEntryMenu")
                UIExtensions.OpenMenu("UITextEntryMenu")
                string gameEventEntry = UIExtensions.GetMenuResultString("UITextEntryMenu")
                if (gameEventEntry && gameEventEntry != "")
                    gameEventEntry = gameEventEntry+"\n"
                    conversation.AddIngameEvent(gameEventEntry)
                endIf
            endIf
        elseIf KeyCode == MantellaRadiantHotkey
            radiantEnabled =! radiantEnabled
            if radiantEnabled == True
                Debug.Notification("Radiant Dialogue enabled.")
            else
                Debug.Notification("Radiant Dialogue disabled.")
            endIf
        endIf
    endIf
endEvent
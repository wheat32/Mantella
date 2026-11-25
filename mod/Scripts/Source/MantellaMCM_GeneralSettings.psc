Scriptname MantellaMCM_GeneralSettings  Hidden

function Render(MantellaMCM mcm, MantellaRepository Repository) global
    mcm.SetCursorFillMode(mcm.TOP_TO_BOTTOM)
    LeftColumn(mcm, Repository)
    mcm.SetCursorPosition(1)
    RightColumn(mcm, Repository)
endfunction

function LeftColumn(MantellaMCM mcm, MantellaRepository Repository) global
    mcm.AddHeaderOption("Microphone")
    mcm.oid_microphoneEnabledToggle = mcm.AddToggleOption("Enabled", repository.microphoneEnabled)
    mcm.oid_useHotkeyToStartMic = mcm.AddToggleOption("Use Hotkey to Start Mic", repository.useHotkeyToStartMic)
    mcm.oid_pushToTalkEnabled = mcm.AddToggleOption("Push-to-Talk", repository.pushToTalkEnabled)
    mcm.oid_responsetimeslider = mcm.AddSliderOption("Text Response Wait Time", repository.MantellaEffectResponseTimer)
    mcm.oid_showReminderMessages = mcm.AddToggleOption("Show Input Reminder Messages", repository.showReminderMessages)

    mcm.AddHeaderOption("Controls")
    mcm.oid_keymapStartAddHotkey = mcm.AddKeyMapOption("Start Conversation / Add NPC", repository.MantellaStartHotkey)
    mcm.oid_keymapPromptHotkey = mcm.AddKeyMapOption("Open Text Prompt", repository.MantellaListenerTextHotkey)
    mcm.oid_keymapEndHotkey = mcm.AddKeyMapOption("End Conversation / Remove NPC", repository.MantellaEndHotkey)
    mcm.oid_keymapToggleHotkey = mcm.AddKeyMapOption("Toggle NPC in Conversation", repository.MantellaToggleHotkey)
    mcm.oid_keymapEndConversationHotkey = mcm.AddKeyMapOption("End Conversation", repository.MantellaEndConversationHotkey)
    mcm.oid_keymapPushToTalkHotkey = mcm.AddKeyMapOption("Push-to-Talk Key", repository.MantellaPushToTalkHotkey)
    mcm.oid_keymapCustomGameEventHotkey = mcm.AddKeyMapOption("Add Custom Game Event", repository.MantellaCustomGameEventHotkey)
    mcm.oid_keymapRadiantHotkey = mcm.AddKeyMapOption("Toggle Radiant Dialogue", repository.MantellaRadiantHotkey) 
endfunction

function RightColumn(MantellaMCM mcm, MantellaRepository Repository) global
    mcm.AddHeaderOption("Dynamic Conversations")
    mcm.oid_radiantenabled = mcm.AddToggleOption("Radiant Dialogue", repository.radiantEnabled)
    mcm.oid_approachenabled = mcm.AddToggleOption("NPCs can Approach Player", repository.approachEnabled)
    mcm.oid_triggerRatio = mcm.AddSliderOption("Trigger Ratio %",repository.triggerRatio)
    mcm.oid_radiantdistance = mcm.AddSliderOption("Trigger Distance",repository.radiantDistance)
    mcm.oid_radiantfrequency = mcm.AddSliderOption("Trigger Frequency",repository.radiantFrequency)
    mcm.oid_showRadiantDialogueMessages = mcm.AddToggleOption("Show Debug Messages", repository.showRadiantDialogueMessages)

    mcm.AddHeaderOption("Free-flow Conversations")
    mcm.oid_freeFlowEnabled = mcm.AddToggleOption("Free-flow Conversations", repository.freeFlowEnabled)
    mcm.oid_freeFlowUseNearest = mcm.AddToggleOption("Talk to Nearest Character", repository.freeFlowUseNearest)
    mcm.oid_freeFlowDistance = mcm.AddSliderOption("Nearest Character Distance", repository.freeFlowDistance)
    mcm.oid_freeFlowIncludeCreatures = mcm.AddToggleOption("Nearest Can Be a Creature", repository.freeFlowIncludeCreatures)

    mcm.AddHeaderOption("Awareness of Surroundings")
    mcm.oid_awarenessMaxCharacters = mcm.AddSliderOption("Max Characters Noticed", repository.awarenessMaxCharacters)
    mcm.oid_awarenessDistance = mcm.AddSliderOption("Notice Distance", repository.awarenessDistance)
    mcm.oid_conversationLeaveDistance = mcm.AddSliderOption("Leave Conversation Distance", repository.conversationLeaveDistance)

    mcm.AddHeaderOption("NPC Inventory")
    mcm.oid_notableItemsEnabled = mcm.AddToggleOption("NPCs Know What They Carry", repository.notableItemsEnabled)

    mcm.AddHeaderOption("NPC Actions")
    mcm.oid_NPCPackageToggle = mcm.AddToggleOption("NPCs Stop to Talk", Repository.NPCPackage)
    mcm.oid_showDialogueItems = mcm.AddToggleOption("Show Dialogue Items", repository.showDialogueItems) 
    mcm.oid_enableVanillaDialogueAwareness = mcm.AddToggleOption("Vanilla Dialogue Awareness", repository.enableVanillaDialogueAwareness)
endfunction

function SliderOptionOpen(MantellaMCM mcm, int optionID, MantellaRepository Repository) global
    ; SliderOptionOpen is used to choose what to display when the user clicks on the slider
    if optionID==mcm.oid_responsetimeslider
        mcm.SetSliderDialogStartValue(repository.MantellaEffectResponseTimer)
        mcm.SetSliderDialogDefaultValue(30)
        mcm.SetSliderDialogRange(0, 5000)
        mcm.SetSliderDialogInterval(1)
    elseIf optionID==mcm.oid_radiantdistance
        mcm.SetSliderDialogStartValue(repository.radiantDistance)
        mcm.SetSliderDialogDefaultValue(20)
        mcm.SetSliderDialogRange(1, 250)
        mcm.SetSliderDialogInterval(1)
    elseIf optionID==mcm.oid_awarenessMaxCharacters
        mcm.SetSliderDialogStartValue(repository.awarenessMaxCharacters)
        mcm.SetSliderDialogDefaultValue(10)
        mcm.SetSliderDialogRange(1, 30)
        mcm.SetSliderDialogInterval(1)
    elseIf optionID==mcm.oid_awarenessDistance
        mcm.SetSliderDialogStartValue(repository.awarenessDistance)
        mcm.SetSliderDialogDefaultValue(150)
        mcm.SetSliderDialogRange(10, 300)
        mcm.SetSliderDialogInterval(10)
    elseIf optionID==mcm.oid_conversationLeaveDistance
        mcm.SetSliderDialogStartValue(repository.conversationLeaveDistance)
        mcm.SetSliderDialogDefaultValue(20)
        mcm.SetSliderDialogRange(0, 100)
        mcm.SetSliderDialogInterval(5)
    elseIf optionID==mcm.oid_freeFlowDistance
        mcm.SetSliderDialogStartValue(repository.freeFlowDistance)
        mcm.SetSliderDialogDefaultValue(5)
        mcm.SetSliderDialogRange(1, 30)
        mcm.SetSliderDialogInterval(1)
    elseIf optionID==mcm.oid_radiantfrequency
        mcm.SetSliderDialogStartValue(repository.radiantFrequency)
        mcm.SetSliderDialogDefaultValue(10)
        mcm.SetSliderDialogRange(5, 300)
        mcm.SetSliderDialogInterval(1)
    elseIf optionID==mcm.oid_triggerRatio
        mcm.SetSliderDialogStartValue(repository.triggerRatio)
        mcm.SetSliderDialogDefaultValue(50)
        mcm.SetSliderDialogRange(0, 100)
        mcm.SetSliderDialogInterval(1)
    endif
endfunction

function SliderOptionAccept(MantellaMCM mcm, int optionID, float value, MantellaRepository Repository) global
    ;SliderOptionAccept is used to update the Repository with the user input (that input will then be used by the Mantella effect script
    If  optionId == mcm.oid_responsetimeslider
        mcm.SetSliderOptionValue(optionId, value)
        Repository.MantellaEffectResponseTimer=value
    elseIf optionId == mcm.oid_radiantdistance
        mcm.SetSliderOptionValue(optionId, value)
        Repository.radiantDistance=value
        debug.MessageBox("Please save and reload for this change to take effect")
    elseIf optionId == mcm.oid_awarenessMaxCharacters
        mcm.SetSliderOptionValue(optionId, value)
        Repository.awarenessMaxCharacters=value as int
    elseIf optionId == mcm.oid_awarenessDistance
        mcm.SetSliderOptionValue(optionId, value)
        Repository.awarenessDistance=value
    elseIf optionId == mcm.oid_conversationLeaveDistance
        mcm.SetSliderOptionValue(optionId, value)
        Repository.conversationLeaveDistance=value
    elseIf optionId == mcm.oid_freeFlowDistance
        mcm.SetSliderOptionValue(optionId, value)
        Repository.freeFlowDistance=value
    elseIf optionId == mcm.oid_radiantfrequency
        mcm.SetSliderOptionValue(optionId, value)
        Repository.radiantFrequency=value
        debug.MessageBox("Please save and reload for this change to take effect")
    elseIf optionId == mcm.oid_triggerRatio
        mcm.SetSliderOptionValue(optionId, value)
        Repository.triggerRatio=value as int
        debug.MessageBox("Please save and reload for this change to take effect")
    EndIf
endfunction


function KeyMapChange(MantellaMCM mcm,Int option, Int keyCode, String conflictControl, String conflictName, MantellaRepository Repository) global
    ;This script is used to check if a key is already used, if it's not it will update to a new value (stored in MantellaRepository) or it will prompt the user to warn him of the conflict. The actual keybind happens in MantellaRepository
    bool isOptionHotkey = option == mcm.oid_keymapStartAddHotkey || option == mcm.oid_keymapPromptHotkey || option == mcm.oid_keymapCustomGameEventHotkey || option == mcm.oid_keymapEndHotkey || option == mcm.oid_keymapToggleHotkey || option == mcm.oid_keymapEndConversationHotkey || option == mcm.oid_keymapPushToTalkHotkey || option == mcm.oid_keymapRadiantHotkey
    if (isOptionHotkey)
        Bool continue = true
        ;below checks if there's already a bound key
        if conflictControl != ""
            String ConflitMessage
            if conflictName != ""
                ConflitMessage = "Key already mapped to:\n'" + conflictControl + "'\n(" + conflictName + ")\n\nAre you sure you want to continue?"
            else
                ConflitMessage = "Key already mapped to:\n'" + conflictControl + "'\n\nAre you sure you want to continue?"
            endIf
            continue = mcm.ShowMessage(ConflitMessage, true, "$Yes", "$No")
        endIf
        if continue
            mcm.SetKeymapOptionValue(option, keyCode)
            ;selector to update the correct hotkey according to oid values
            if option == mcm.oid_keymapStartAddHotkey
                repository.BindStartAddHotkey(keyCode)
            elseIf option == mcm.oid_keymapPromptHotkey 
                repository.BindPromptHotkey(keyCode)
            elseIf option == mcm.oid_keymapEndHotkey
                repository.BindEndHotkey(keyCode)
            elseIf option == mcm.oid_keymapToggleHotkey
                repository.BindToggleHotkey(keyCode)
            elseIf option == mcm.oid_keymapEndConversationHotkey
                repository.BindEndConversationHotkey(keyCode)
            elseIf option == mcm.oid_keymapPushToTalkHotkey
                repository.BindPushToTalkHotkey(keyCode)
            elseIf option == mcm.oid_keymapCustomGameEventHotkey
                repository.BindCustomGameEventHotkey(keyCode)
            elseIf option == mcm.oid_keymapRadiantHotkey
                repository.BindRadiantHotkey(keyCode)
            endif
        endIf
    endIf
endfunction

function OptionUpdate(MantellaMCM mcm, int optionID, MantellaRepository Repository) global
    ;checks option per option what the toggle is and the updates the variable/function repository MantellaRepository so the MantellaEffect and Repository Hotkey function can access it
    if optionID == mcm.oid_microphoneEnabledToggle
        Repository.microphoneEnabled =! Repository.microphoneEnabled
        mcm.SetToggleOptionValue(mcm.oid_microphoneEnabledToggle, Repository.microphoneEnabled)
    elseif optionID == mcm.oid_pushToTalkEnabled
        Repository.pushToTalkEnabled =! Repository.pushToTalkEnabled
        mcm.SetToggleOptionValue(optionID, Repository.pushToTalkEnabled)
        (Quest.GetQuest("MantellaConversation") as MantellaConversation).SendPushToTalkSettings()
    elseif optionID == mcm.oid_useHotkeyToStartMic
        Repository.useHotkeyToStartMic =! Repository.useHotkeyToStartMic
        mcm.SetToggleOptionValue(mcm.oid_useHotkeyToStartMic, Repository.useHotkeyToStartMic)
    elseIf optionID == mcm.oid_showReminderMessages
        repository.showReminderMessages =! repository.showReminderMessages
        mcm.SetToggleOptionValue(optionID, repository.showReminderMessages)
    elseIf optionID == mcm.oid_debugNPCselectMode
        Repository.NPCdebugSelectModeEnabled =! Repository.NPCdebugSelectModeEnabled
        mcm.SetToggleOptionValue(mcm.oid_debugNPCselectMode, Repository.NPCdebugSelectModeEnabled)
    elseIf optionID == mcm.oid_showDialogueItems
        repository.showDialogueItems =! repository.showDialogueItems
        mcm.SetToggleOptionValue(mcm.oid_showDialogueItems, repository.showDialogueItems)
    elseIf optionID == mcm.oid_radiantenabled
        repository.radiantEnabled =! repository.radiantEnabled
        mcm.SetToggleOptionValue(mcm.oid_radiantenabled, repository.radiantEnabled)
    elseIf optionID == mcm.oid_freeFlowEnabled
        repository.freeFlowEnabled =! repository.freeFlowEnabled
        mcm.SetToggleOptionValue(optionID, repository.freeFlowEnabled)
    elseIf optionID == mcm.oid_notableItemsEnabled
        repository.notableItemsEnabled =! repository.notableItemsEnabled
        mcm.SetToggleOptionValue(optionID, repository.notableItemsEnabled)
    elseIf optionID == mcm.oid_freeFlowUseNearest
        repository.freeFlowUseNearest =! repository.freeFlowUseNearest
        mcm.SetToggleOptionValue(optionID, repository.freeFlowUseNearest)
    elseIf optionID == mcm.oid_freeFlowIncludeCreatures
        repository.freeFlowIncludeCreatures =! repository.freeFlowIncludeCreatures
        mcm.SetToggleOptionValue(optionID, repository.freeFlowIncludeCreatures)
    elseIf optionID == mcm.oid_approachenabled
        repository.approachEnabled =! repository.approachEnabled
        mcm.SetToggleOptionValue(mcm.oid_approachenabled, repository.approachEnabled)
    elseIf optionID == mcm.oid_showRadiantDialogueMessages
        repository.showRadiantDialogueMessages =! repository.showRadiantDialogueMessages
        mcm.SetToggleOptionValue(optionID, repository.showRadiantDialogueMessages)
    elseIf optionID == mcm.oid_NPCPackageToggle
        Repository.NPCPackage =! Repository.NPCPackage
        mcm.SetToggleOptionValue(mcm.oid_NPCPackageToggle, Repository.NPCPackage)
    elseIf optionID == mcm.oid_enableVanillaDialogueAwareness
        Repository.enableVanillaDialogueAwareness =! Repository.enableVanillaDialogueAwareness
        mcm.SetToggleOptionValue(mcm.oid_enableVanillaDialogueAwareness, Repository.enableVanillaDialogueAwareness)
    endif
endfunction
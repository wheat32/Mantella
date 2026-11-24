Scriptname MantellaMCM_AdvancedSettings Hidden

function Render(MantellaMCM mcm, MantellaRepository Repository) global
    mcm.SetCursorFillMode(mcm.TOP_TO_BOTTOM)
    LeftColumn(mcm, Repository)
    mcm.SetCursorPosition(1)
    RightColumn(mcm, Repository)
endfunction

function LeftColumn(MantellaMCM mcm, MantellaRepository Repository) global
	mcm.AddHeaderOption("Debug")
    mcm.oid_restartMantellaExe = mcm.AddTextOption("Restart Mantella.exe", "")
	mcm.oid_debugNPCselectMode = mcm.AddToggleOption("NPC Debug Select Mode", Repository.NPCdebugSelectModeEnabled)
    mcm.oid_showScreenshotMessages = mcm.AddToggleOption("Show Screenshot Messages", Repository.showScreenshotMessages)
    mcm.oid_showNpcConversationMessages = mcm.AddToggleOption("Show NPC Conversation Messages", Repository.showNpcConversationMessages)
    mcm.oid_dumpDialogueOptions = mcm.AddTextOption("Dump Dialogue Options", "")
endfunction

function RightColumn(MantellaMCM mcm, MantellaRepository Repository) global
	mcm.AddHeaderOption("HTTP")
    If (Repository.IsVR())
        mcm.oid_httpPort = mcm.AddSliderOption("Port", Repository.HttpPort)
    else
        mcm.oid_httpPort = mcm.AddInputOption("Port", Repository.HttpPort)
    EndIf	
endfunction

function OptionInputUpdate(MantellaMCM mcm, int optionID, string inputText, MantellaRepository Repository) global
	If optionID == mcm.oid_httpPort
		int convertedInput = inputText as int
		if(convertedInput > 0 && convertedInput < 65535)
			Repository.HttpPort = convertedInput
			mcm.SetInputOptionValue(optionID, inputText)
		endIf
	endIf
endfunction

function SliderOptionOpen(MantellaMCM mcm, int optionID, MantellaRepository Repository) global
    ; SliderOptionOpen is used to choose what to display when the user clicks on the slider
    if optionID==mcm.oid_httpPort
        mcm.SetSliderDialogStartValue(repository.HttpPort)
        mcm.SetSliderDialogDefaultValue(4999)
        mcm.SetSliderDialogRange(1, 65535)
        mcm.SetSliderDialogInterval(1)    
    endif
endfunction

function SliderOptionAccept(MantellaMCM mcm, int optionID, float value, MantellaRepository Repository) global
    ;SliderOptionAccept is used to update the Repository with the user input (that input will then be used by the Mantella effect script
    If  optionId == mcm.oid_httpPort
        mcm.SetSliderOptionValue(optionId, value)
        Repository.HttpPort = value as int
    EndIf
endfunction

function OptionUpdate(MantellaMCM mcm, int optionID, MantellaRepository Repository) global
	if optionID == mcm.oid_dumpDialogueOptions
		Actor speaker = Game.GetCurrentCrosshairRef() as Actor
		if !speaker
			speaker = Game.FindClosestActorFromRef(Game.GetPlayer(), 500.0)
		endIf
		if !speaker
			Debug.MessageBox("No character found. Look at a character or stand next to one, then open this menu again.")
		else
			int count = SKSE_HTTP.DumpDialogueOptions(speaker)
			if count < 0
				Debug.MessageBox("The dialogue options of " + speaker.GetDisplayName() + " could not be worked out.")
			else
				Debug.MessageBox(count + " dialogue options of " + speaker.GetDisplayName() + " written to Documents/My Games/Mantella/dialogue_options.txt")
			endIf
		endIf
	elseif optionID == mcm.oid_showNpcConversationMessages
		Repository.showNpcConversationMessages =! Repository.showNpcConversationMessages
		mcm.SetToggleOptionValue(optionID, Repository.showNpcConversationMessages)
	elseif optionID == mcm.oid_showScreenshotMessages
		Repository.showScreenshotMessages =! Repository.showScreenshotMessages
		mcm.SetToggleOptionValue(optionID, Repository.showScreenshotMessages)
		if (Quest.GetQuest("MantellaConversation") as MantellaConversation).IsRunning()
			SKSE_HTTP.SetScreenshotMessageVisible(Repository.showScreenshotMessages)
		endIf
	elseif optionID == mcm.oid_debugNPCselectMode
		Repository.NPCdebugSelectModeEnabled =! Repository.NPCdebugSelectModeEnabled
		mcm.SetToggleOptionValue(mcm.oid_debugNPCselectMode, Repository.NPCdebugSelectModeEnabled)
    elseif optionID == mcm.oid_restartMantellaExe
        Repository.restartMantellaExe()
        Debug.MessageBox("Restarting Mantella.exe... This can take a moment.")
	endIf
endfunction 

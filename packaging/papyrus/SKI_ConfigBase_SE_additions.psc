; ---------------------------------------------------------------------------------------------------------------------
; Text input options, added in SkyUI SE 5.2 (MCM API 4). The source of that version has not been published, so these
; declarations (taken from the function names and parameters in the compiled script) are only here to compile against.
; ---------------------------------------------------------------------------------------------------------------------
int function AddInputOption(string a_text, string a_value, int a_flags = 0)
	return 0
endFunction

function AddInputOptionST(string a_stateName, string a_text, string a_value, int a_flags = 0)
endFunction

function SetInputOptionValue(int a_option, string a_value, bool a_noUpdate = false)
endFunction

function SetInputOptionValueST(string a_value, bool a_noUpdate = false, string a_stateName = "")
endFunction

function SetInputDialogStartText(string a_text)
endFunction

event OnOptionInputOpen(int a_option)
endEvent

event OnOptionInputAccept(int a_option, string a_input)
endEvent

event OnInputOpenST()
endEvent

event OnInputAcceptST(string a_input)
endEvent

Scriptname MantellaEffectScript extends activemagiceffect

MantellaConversation property conversation auto

event OnEffectStart(Actor target, Actor caster)
    ;Utility.Wait(0.5)
    Actor[] actors = new Actor[2]
    actors[0] = caster
    actors[1] = target
    if(!conversation.IsRunning())
        ; A conversation between two NPCs (radiant dialogue) starts quietly, unless its messages are enabled in the mod menu
        Actor player = Game.GetPlayer()
        if caster == player || target == player || conversation.repository.showNpcConversationMessages
            Debug.Notification("Starting conversation...")
        endIf
        conversation.Start()
        conversation.StartConversation(actors)
    Else
        if conversation.IsPlayerInConversation()
            Debug.Notification("Adding "+actors[1].GetDisplayName()+" to conversation...")
        Else
            ; If player is joining what was previously a radiant conversation
            Debug.Notification("Adding player to conversation...")
        endIf
        conversation.AddActorsToConversation(actors)
    endIf
endEvent

// The people of the studio, as the scene draws them. The page (static/app/29-team.js) works out
// who is doing what from the conversation's task; these are the shapes it hands the scene.
// Kept in step with the desktop app's studio/cast.ts.

/** What an agent is doing, by the tool it uses. */
export type ActivityKind = 'thinking' | 'search' | 'read' | 'write' | 'code' | 'delegate' | 'tool'

/** What a person in the studio is doing; the scene turns it into a place and a pose. */
export type ActorState = 'idle' | 'arriving' | 'working' | 'answering' | 'waiting' | 'done' | 'failed' | 'stopped'
/** Where they go: their desk, the bookshelf (looking things up), the terminal (running code),
 * the whiteboard (handing out work) or the meeting table (reviewing together). */
export type Spot = 'desk' | 'shelf' | 'terminal' | 'board' | 'table'

export type HairStyle = 'short' | 'long' | 'bun' | 'spiky' | 'bald'
export type Accessory = 'none' | 'glasses' | 'headset' | 'cap' | 'helmet' | 'tie' | 'scarf' | 'badge'

export interface ActorLook {
  shirt: string
  pants: string
  skin: string
  hair: string
  hairStyle: HairStyle
  accessory: Accessory
}

export interface StudioActor {
  /** 'lead' for the conversation's agent, otherwise the expert's id. */
  id: string
  name: string
  lead: boolean
  state: ActorState
  activity: ActivityKind | null
  spot: Spot
  /** A few words over their head. */
  speech?: string
  look: ActorLook
}

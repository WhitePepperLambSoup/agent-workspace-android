// The people of the studio, as the scene draws them. The page (static/app/29-team.js) works out
// who is doing what from the conversation's task; these are the shapes it hands the scene.
// Kept in step with the desktop app's studio/cast.ts.

/** What an agent is doing, by the tool it uses. */
export type ActivityKind = 'thinking' | 'search' | 'read' | 'write' | 'code' | 'delegate' | 'tool'

/** What a person in the studio is doing; the scene turns it into a place and a pose. */
export type ActorState = 'idle' | 'arriving' | 'working' | 'answering' | 'waiting' | 'done' | 'failed' | 'stopped'
/** Where they go: their desk, the bookshelf (looking things up), the terminal (running commands),
 * the sandbox's glass room (running code in it), the glass door (waiting to be allowed to run or
 * change something), the whiteboard (handing out work), the meeting table (reviewing together),
 * or the window (thinking it over). */
export type Spot = 'desk' | 'shelf' | 'terminal' | 'sandbox' | 'door' | 'board' | 'table' | 'window'

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

/** Hand-made looks for the agent and a few experts; the rest are drawn from their id. The page has
 * the same (29-team.js lookFor), with a library expert in the colour of their field. */
const LOOKS: Record<string, ActorLook> = {
  lead: { shirt: '#2f5d9e', pants: '#2b3140', skin: '#f1c7a5', hair: '#2b211c', hairStyle: 'short', accessory: 'badge' },
  legal: { shirt: '#3e3f55', pants: '#22232c', skin: '#efc6a6', hair: '#1e1a18', hairStyle: 'bun', accessory: 'tie' },
  teacher: { shirt: '#8a8d3b', pants: '#3b3a30', skin: '#d39b78', hair: '#4a4a4a', hairStyle: 'short', accessory: 'glasses' },
}
const SHIRTS = ['#3f88c5', '#d1495b', '#66a182', '#edae49', '#8f6593', '#00798c', '#e76f51']
const HAIRS = ['#2b211c', '#6b3e26', '#a0522d', '#1b1b1b', '#c19a6b']
const STYLES: HairStyle[] = ['short', 'long', 'bun', 'spiky']
const ACCESSORIES: Accessory[] = ['none', 'glasses', 'scarf', 'cap']

function hash(text: string): number {
  let value = 2166136261
  for (const char of text) value = Math.imul(value ^ char.codePointAt(0)!, 16777619)
  return value >>> 0
}

export function lookFor(id: string): ActorLook {
  const made = LOOKS[id]
  if (made) return made
  const seed = hash(id)
  return {
    shirt: SHIRTS[seed % SHIRTS.length]!,
    pants: '#30343e',
    skin: ['#f1c7a5', '#d8a483', '#c99272', '#e9b896'][(seed >> 3) % 4]!,
    hair: HAIRS[(seed >> 5) % HAIRS.length]!,
    hairStyle: STYLES[(seed >> 7) % STYLES.length]!,
    accessory: ACCESSORIES[(seed >> 9) % ACCESSORIES.length]!,
  }
}

export interface StudioActor {
  /** 'lead' for the conversation's agent, otherwise the expert's id or 'helper:<session>'. */
  id: string
  name: string
  lead: boolean
  state: ActorState
  activity: ActivityKind | null
  spot: Spot
  /** A few words over their head. */
  speech?: string
  /** A document just made (the tool's step): they fetch it from the printer once. */
  errand?: string
  /** A sub-agent sent for one task: done, it leaves by the door. */
  leaves?: boolean
  look: ActorLook
}

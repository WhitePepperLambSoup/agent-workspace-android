import type { ActorLook } from '../cast'

/** Someone from the conversation's team at work in the place: an expert or a sub-agent, with their look. */
export interface PlaceVisitorView {
  id: string
  name: string
  stateLabel: string
  look: ActorLook
  pick: string
}

/** What a place's scene is given: its model, the page's words (by the desktop's keys), the agent's name, and visitors. */
export interface PlaceInput<M> {
  model: M
  t: (key: string, values?: Record<string, string | number>) => string
  lead: string
  visitors?: readonly PlaceVisitorView[]
}

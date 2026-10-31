// What each place of the campus is handed. The page (static/app/34-campus.js) works the models out
// from what the phone knows: the knowledge bases, the workspace's files, the scheduled tasks and the
// paired computers. Kept in step with the desktop app's studio/places/models.ts (its model code
// reads the desktop's state; the phone has no server room).

export type PlaceId = 'campus' | 'studio' | 'library' | 'site' | 'duty' | 'desk'

// ---- library ---------------------------------------------------------------------------------

export type BookKind = 'pdf' | 'word' | 'sheet' | 'slides' | 'web' | 'text' | 'image' | 'other'
export type KnowledgeState = 'queued' | 'indexing' | 'ready' | 'failed'

export interface LibraryBook {
  id: string
  title: string
  kind: BookKind
  /** How much there is to it (passages): the spine's thickness. */
  size: number
  state: KnowledgeState
  /** The latest search of the conversation found it. */
  cited: boolean
}

export interface LibraryCase {
  id: string
  name: string
  /** Documents in this knowledge base, also those that do not fit on its shelves. */
  total: number
  books: LibraryBook[]
}

export type LibrarianState = 'idle' | 'searching' | 'reading' | 'adding' | 'papers'

export interface LibraryModel {
  enabled: boolean
  cases: LibraryCase[]
  /** Documents still being read in (or that failed), on the cart by the desk. */
  cart: LibraryBook[]
  /** The phone keeps no list of the reference library's papers: total 0, no sign on their shelf. */
  papers: { total: number; books: LibraryBook[] }
  librarian: { state: LibrarianState; caseId: string | null; cited: number }
  /** Documents are being read in: the clerk at the scanner. */
  clerk: boolean
}

export const LIBRARY_CASES = 5
export const BOOKS_PER_CASE = 72
export const PAPERS_SHOWN = 60

// ---- building site ---------------------------------------------------------------------------

export type BuildingKind = 'code' | 'web' | 'doc' | 'data' | 'config' | 'asset' | 'other'

export interface SiteBuilding {
  path: string
  name: string
  /** 0..1 from the file's size, on a log scale. */
  height: number
  kind: BuildingKind
  /** Written in this conversation (the phone has no Git: nothing is committed or not). */
  changed: boolean
  conflict: boolean
  /** The agent is writing it now. */
  editing: boolean
}

export interface SiteDistrict {
  name: string
  total: number
  buildings: SiteBuilding[]
}

export type WorkerState = 'idle' | 'editing' | 'testing' | 'reading'

export interface SiteModel {
  folder: string | null
  districts: SiteDistrict[]
  files: number
  changed: number
  /** The site office's sign: on the phone the workspace's name. */
  branch: string | null
  ahead: number
  head: string | null
  checks: { running: boolean; failed: string[]; passed: number }
  worker: { state: WorkerState; path: string | null }
}

export const SITE_DISTRICTS = 8
export const SITE_BUILDINGS = 180

// ---- duty room -------------------------------------------------------------------------------

export type OfficerState = 'running' | 'soon' | 'idle' | 'failed' | 'done' | 'off'

export interface DutyOfficer {
  id: string
  title: string
  state: OfficerState
  next: string | null
}

export interface DutyModel {
  officers: DutyOfficer[]
  more: number
  upcoming: Array<{ id: string; title: string; at: string }>
}

export const DUTY_DESKS = 8

// ---- front desk ------------------------------------------------------------------------------

/** On the phone the visitors are the paired computers. */
export interface DeskPhone {
  id: string
  name: string
  online: boolean
  /** What goes on with it now (a key of the page's words), or null. */
  recent: string | null
}

export interface DeskModel {
  enabled: boolean
  running: boolean
  error: boolean
  pairing: boolean
  phones: DeskPhone[]
  /** Tasks this phone handed to a computer, still under way. */
  outgoing: number
}

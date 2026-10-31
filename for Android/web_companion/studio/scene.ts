import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

import type { StudioActor } from './cast'
import {
  BOARD_PLACE,
  DOOR_PLACE,
  ENTRANCE,
  GLASS,
  IDLE_PLACES,
  OUTSIDE,
  PRINTER_PLACE,
  ROOM,
  SANDBOX_PLACES,
  SHELF_PLACES,
  TABLE_PLACES,
  TERMINAL_PLACES,
  WINDOW_PLACES,
  deskSeat,
  obstacles,
  type Place,
  type Point,
} from './layout'
import { Batch, boxShape, createFinishes, cylinderShape, disposeFinishes, dodecaShape, meshesOf, sphereShape } from './mesh-kit'
import { FloorGrid } from './paths'
import { Person, type Action } from './person'
import { buildRoom, createRoomKit, type Room } from './props'

export interface StudioOptions {
  dark: boolean
  reducedMotion: boolean
  accent: string
}

/** An actor with the words the window shows for them. */
export interface StudioActorView extends StudioActor {
  stateLabel: string
  bubble?: string
}

/** One floor: a conversation's team at work, and the words on the sign beside it. */
export interface StudioFloorView {
  id: string
  number: string
  title: string
  summary: string
  busy: boolean
  cast: readonly StudioActorView[]
}

export interface StudioHandlers {
  /** Someone on a floor was clicked. */
  pick(floorId: string, actorId: string): void
  /** A floor of the building was clicked. */
  pickFloor(floorId: string): void
}

/**
 * 'room': the studio page, to look around in. 'backdrop': behind the conversation, under frosted
 * glass: drawn small and seldom, the camera close on the agent and following it, no input.
 */
export type StudioMode = 'room' | 'backdrop'

export interface StudioScene {
  /** The floors, floor 1 first; a single floor is shown as one room. */
  update(floors: readonly StudioFloorView[]): void
  /** Between the frosted backdrop and the room to look around in; the camera flies between them. */
  setMode(mode: StudioMode): void
  /** Stops drawing altogether (another page draws the studio, or the window is hidden). */
  setActive(active: boolean): void
  /** Up close on a floor, or (null) out to the whole building. */
  focus(floorId: string | null): void
  setPaused(paused: boolean): void
  resetView(): void
  /** Draws for this long as while someone walks, whatever the room does: the page times the frames
   * to find a phone too slow for the studio behind the conversation. */
  exercise(ms: number): void
  dispose(): void
}

/**
 * The label (a person's tag or a sign) shown at a point of the screen, the top one first. On the phone
 * the labels let touches through to the view (style.css), so a drag or a pinch that starts on one still
 * turns or zooms it; a tap there is matched here and clicks the label.
 */
export function labelAt(overlay: HTMLElement, x: number, y: number): HTMLElement | null {
  const labels = [...overlay.querySelectorAll<HTMLElement>('.studio-tag, .studio-floor-sign')]
  for (let index = labels.length - 1; index >= 0; index--) {
    const label = labels[index]
    const rect = label.getBoundingClientRect()
    if (!rect.width || x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) continue
    const style = getComputedStyle(label)
    if (style.visibility !== 'hidden' && Number(style.opacity) >= 0.1) return label
  }
  return null
}

const TARGET = new THREE.Vector3(-0.3, 0.5, 0.2)
const FLOOR_ANGLES = { polar: 0.98, azimuth: 0.62 }
const BUILDING_ANGLES = { polar: 1.16, azimuth: 0.72 }
/** The radius around the target the whole room fits in, for framing it at any size. */
const ROOM_RADIUS = 7.1
/** One storey: the room's walls and the slab of the floor above. */
export const STOREY = ROOM.height + 0.4
/** How far the plinth reaches past the rooms on every side, and how deep it goes. */
const PLINTH_MARGIN = 1.2
const PLINTH_BOTTOM = -0.87
/** The top of the roof's antenna, over the top floor's ceiling. */
const ROOF_TOP = 1.75
/** How far the floors over the one in view rise out of the way. */
const LIFT = 16
/** A floor that opens while the building is in view comes down from this far up. */
const ARRIVAL = 7
const MOVE_SECONDS = 1.35
// A phone: 30 frames a second while things move, 20 while people only sway (the desktop draws 60/30).
const FRAME_MS = 1000 / 30
/** How long someone who finished stays at their desk before they wander off. */
const DONE_SECONDS = 20
/** Newcomers appear outside the room's door and walk in. */
const DOOR: Point = { x: OUTSIDE.x, z: OUTSIDE.z }
const DOORWAY: Point = { x: ENTRANCE.x, z: (ENTRANCE.z0 + ENTRANCE.z1) / 2 }
/** Seconds between newcomers sent for at once going in. */
const ENTRY_GAP = 1.5
/** How far the door swings out for someone passing. */
const DOOR_OPEN = 1.35
/** Where the key light comes from, relative to what it lights. */
const SUN = new THREE.Vector3(-5, 11, 8)
/** A sticky note on the whiteboard; its colour is the expert's. */
const NOTE = boxShape(0.01, 0.2, 0.22, 0.004)
/** The middle of the sandbox's doorway. */
const DOOR_CENTER = { x: (GLASS.door.x0 + GLASS.door.x1) / 2, z: GLASS.z }
/** How long someone at the window stands still before they start pacing in front of it. */
const PACE_AFTER = 14
/** At the printer: the pages come out, then they take them back to their desk. */
const PRINT_SECONDS = 1.6
/** Frames a second while nothing walks, turns or flies: idle sways look the same at a lower rate. */
const RESTING_FRAME_MS = 1000 / 12
/** With nobody working, nothing on the way and no touch for this long, drawing stops until something
 * changes (a phone's battery: an unchanging picture needs no frames). */
const SLEEP_AFTER_MS = 4000
/** Behind the conversation: a smaller picture (pixels per CSS pixel), 30 frames a second while
 * someone walks or the view follows them, as on the desktop (18 made the whole picture judder as
 * it panned, and 30 divides 60, 90 and 120 Hz evenly; each frame also has the glass above it drawn
 * again, kept cheap in style.css), one while they only work. */
const BACKDROP_PIXELS = 0.75
const BACKDROP_FRAME_MS = 1000 / 30
const BACKDROP_REST_MS = 1000
const BACKDROP_ANGLES = { polar: 1.02, azimuth: 0.5 }

interface Member {
  person: Person
  actor: StudioActorView
  desk: number
  tag: HTMLButtonElement
  bubble: HTMLDivElement
  since: number
  idleNext: number
  idlePlace: Place | null
  key: string
  /** The tag's full size in pixels (name and state shown), measured when its text changes. */
  tagSize: [number, number] | null
  /** When their spot last changed (the window: pacing after a while). */
  spotSince: number
  /** Documents already fetched from the printer, and the fetch under way. */
  errands: Set<string>
  errand: { phase: 'fetch' | 'carry'; at: number | null } | null
  /** A sub-agent that went out by the door, its task done: not drawn until it has work again. */
  gone: boolean
  /** Several sent for at once come in one after another: this one waits outside until then. */
  enters: number
}

/** A value that eases to a new target over a few frames. */
class Tween {
  private from: number
  private to: number
  private start = 0
  private seconds = 0

  constructor(value: number) {
    this.from = value
    this.to = value
  }

  get target(): number {
    return this.to
  }

  set(to: number, now: number, seconds: number): void {
    if (to === this.to) return
    this.from = this.value(now)
    this.to = to
    this.start = now
    this.seconds = seconds
  }

  value(now: number): number {
    if (this.seconds <= 0) return this.to
    return this.from + (this.to - this.from) * ease(Math.min(1, (now - this.start) / this.seconds))
  }

  done(now: number): boolean {
    return this.seconds <= 0 || now - this.start >= this.seconds
  }
}

interface Floor {
  id: string
  index: number
  view: StudioFloorView
  group: THREE.Group
  room: Room
  /** Posts at the open corners: with them the stacked rooms read as one building. */
  posts: THREE.Group
  members: Map<string, Member>
  /** Before the first update, people start at their desks rather than at the door. */
  first: boolean
  notesSignature: string
  y: Tween
  sign: HTMLButtonElement
  /** The sign's width, measured when its words change, to keep it inside the stage. */
  signWidth: number
}

/** Where the camera looks from: a point it circles and its distance and angles. */
interface View {
  target: THREE.Vector3
  radius: number
  polar: number
  azimuth: number
}

function ease(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

function placeKey(place: Place): string {
  return `${place.x.toFixed(2)},${place.z.toFixed(2)}`
}

function actionFor(member: Member, place: Place): Action {
  const { actor } = member
  if (member.errand) return member.errand.phase === 'carry' ? 'carry' : 'operate'
  if (actor.state === 'waiting') return 'raise'
  if (actor.state === 'failed') return 'slump'
  if (actor.state === 'answering') return 'type'
  if (actor.state === 'working') {
    if (actor.spot === 'shelf') return 'read'
    if (actor.spot === 'terminal' || actor.spot === 'sandbox') return 'operate'
    if (actor.spot === 'board') return 'write'
    if (actor.spot === 'table') return 'talk'
    if (actor.spot === 'window') return 'gaze'
    // At the desk: a web page, a page of a file, or writing.
    if (actor.activity === 'search') return 'browse'
    if (actor.activity === 'read') return 'paper'
    return actor.activity === 'thinking' ? 'think' : 'type'
  }
  if (WINDOW_PLACES.includes(place)) return 'gaze'
  if (place === IDLE_PLACES[0] || (place.x === IDLE_PLACES[1]!.x && place.z === IDLE_PLACES[1]!.z)) return 'sip'
  return 'rest'
}

/**
 * The studio: a small office diorama where the lead and the experts walk to their desks, the
 * bookshelf, the terminal, the whiteboard or the meeting table as their tasks go. When several
 * conversations have their teams at work, each gets a floor of an office building; the camera
 * flies into a floor while the floors above lift away, and back out. Labels, speech bubbles and
 * floor signs are HTML laid over the canvas.
 */
export function createStudioScene(stage: HTMLElement, overlay: HTMLElement, options: StudioOptions, handlers: StudioHandlers, initialMode: StudioMode = 'room'): StudioScene {
  let mode = initialMode
  // A phone's screens have 2.5-3.5 pixels per CSS pixel; 1.25 with antialiasing still reads well.
  const pixelRatio = (): number => (mode === 'backdrop' ? BACKDROP_PIXELS : Math.min(window.devicePixelRatio || 1, 1.25))
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(pixelRatio())
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  // Shadows are drawn again only when something moves or changes (see the loop), not every frame.
  renderer.shadowMap.autoUpdate = false
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = options.dark ? 1.05 : 1.0
  renderer.domElement.classList.add('studio-canvas')
  renderer.domElement.setAttribute('aria-hidden', 'true')
  stage.prepend(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(30, 1, 0.5, 160)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.target.copy(TARGET)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.enablePan = false
  controls.rotateSpeed = 0.6
  controls.zoomSpeed = 0.8
  controls.enabled = mode === 'room'
  stage.dataset.mode = mode

  scene.add(new THREE.HemisphereLight(options.dark ? '#9fb0e0' : '#fff6ea', options.dark ? '#3a3040' : '#b8a48c', options.dark ? 1.35 : 1.5))
  const key = new THREE.DirectionalLight(options.dark ? '#b9c8ff' : '#fff1dc', options.dark ? 1.5 : 2.2)
  key.castShadow = true
  // Half the desktop's: a quarter of the memory and fill work on a phone's GPU.
  key.shadow.mapSize.set(1024, 1024)
  key.shadow.camera.near = 1
  key.shadow.bias = -0.0006
  key.shadow.radius = 3
  scene.add(key, key.target)
  const fill = new THREE.DirectionalLight(options.dark ? '#5b4b8a' : '#cfe3ff', options.dark ? 0.35 : 0.6)
  fill.position.set(9, 5, -3)
  scene.add(fill)

  // One set of finishes and one room kit for every floor: the floors share their buffers.
  const finishes = createFinishes()
  const roomKit = createRoomKit({ dark: options.dark, accent: options.accent }, finishes)

  // What turns a stack of rooms into a building: corner posts on every floor, a roof, a plinth.
  const trim = options.dark ? '#3b4252' : '#d8d2c8'
  const roomWidth = ROOM.x1 - ROOM.x0
  const roomDepth = ROOM.z1 - ROOM.z0
  const postBatch = new Batch()
  for (const [x, z] of [[ROOM.x1 + 0.13, ROOM.z1 + 0.13], [ROOM.x1 + 0.13, ROOM.z0 - 0.05], [ROOM.x0 - 0.05, ROOM.z1 + 0.13]] as const) {
    postBatch.add(boxShape(0.26, ROOM.height, 0.26, 0.03), trim, { x, y: ROOM.height / 2, z }, 'satin')
    postBatch.add(boxShape(0.3, 0.06, 0.3, 0.01), options.dark ? '#4a5263' : '#e6e0d6', { x, y: ROOM.height - 0.03, z }, 'satin', false)
  }
  const postParts = postBatch.build()
  const roofBatch = new Batch()
  roofBatch.add(boxShape(roomWidth + 0.5, 0.36, roomDepth + 0.5), options.dark ? '#2b2f38' : '#e9e4dc', { y: -0.18 }, 'matte', false)
  roofBatch.add(boxShape(roomWidth + 0.3, 0.02, roomDepth + 0.3), options.dark ? '#353a45' : '#d9d3c8', { y: 0.01 }, 'matte', false)
  for (const [w, d, x, z] of [[roomWidth + 0.5, 0.14, 0, ROOM.z0 - 0.18], [roomWidth + 0.5, 0.14, 0, ROOM.z1 + 0.18], [0.14, roomDepth + 0.5, ROOM.x0 - 0.18, 0], [0.14, roomDepth + 0.5, ROOM.x1 + 0.18, 0]] as const) {
    roofBatch.add(boxShape(w, 0.42, d, 0.02), trim, { x, y: 0.21, z }, 'satin')
  }
  // Rooftop units, solar panels and an antenna, so the top reads as a roof from afar.
  roofBatch.add(boxShape(1.6, 0.6, 1.1, 0.04), options.dark ? '#4d5466' : '#c9c3b8', { x: -3.2, y: 0.3, z: -2.6 }, 'satin')
  for (const dx of [-0.45, 0, 0.45]) roofBatch.add(cylinderShape(0.17, 0.17, 0.04, 16), '#2a2d35', { x: -3.2 + dx, y: 0.62, z: -2.6 }, 'metal', false)
  for (let row = 0; row < 2; row += 1) {
    for (let column = 0; column < 3; column += 1) {
      const x = 0.4 + column * 1.25
      const z = 0.6 + row * 1.15
      roofBatch.add(boxShape(1.1, 0.04, 0.9, 0.01), options.dark ? '#1c2a4a' : '#2c4a7a', { x, y: 0.42, z, rx: -0.3 }, 'satin')
      roofBatch.add(boxShape(0.04, 0.32, 0.04), '#8a919c', { x, y: 0.18, z: z - 0.3 }, 'metal', false)
    }
  }
  roofBatch.add(cylinderShape(0.04, 0.05, 1.6, 8), trim, { x: 4.2, y: 0.8, z: -3.4 }, 'metal')
  roofBatch.add(sphereShape(0.09, 10, 8), '#ff3b30', { x: 4.2, y: 1.65, z: -3.4 }, 'glow', false)
  const roof = new THREE.Group()
  for (const mesh of meshesOf(roofBatch.build(), finishes)) roof.add(mesh)
  let roofY = new Tween(0)
  /** Whether the roof is on the building; when it appears it comes down from above. */
  let roofOn = false
  // The plinth: a stone base with a strip of lawn and a path to the door.
  const plinthBatch = new Batch()
  plinthBatch.add(boxShape(roomWidth + 2 * PLINTH_MARGIN, 0.5, roomDepth + 2 * PLINTH_MARGIN, 0.04), options.dark ? '#262a33' : '#cfc8bc', { y: PLINTH_BOTTOM + 0.25 }, 'matte', false)
  plinthBatch.add(boxShape(roomWidth + 2.2, 0.03, roomDepth + 2.2), options.dark ? '#2f4a3a' : '#9cc49a', { y: -0.36 }, 'matte', false)
  plinthBatch.add(boxShape(1.6, 0.035, 1.1), options.dark ? '#3a3f4b' : '#e6e0d6', { x: 4.4, y: -0.355, z: ROOM.z1 + 0.7 }, 'matte', false)
  for (const [x, z] of [[-6.6, 5.2], [6.6, 5.2], [-6.6, -5.0], [6.7, -1.0]] as const) {
    plinthBatch.add(dodecaShape(0.4), '#4f8a5b', { x, y: -0.1, z }, 'matte')
    plinthBatch.add(dodecaShape(0.26), '#6aa86f', { x: x + 0.2, y: 0.1, z: z - 0.1 }, 'matte')
  }
  const plinth = new THREE.Group()
  for (const mesh of meshesOf(plinthBatch.build(), finishes)) plinth.add(mesh)
  scene.add(roof, plinth)
  // A soft shadow on the ground under the room (or the building) so it stands on something instead of
  // floating on the page: one quad with a radial fade, turning with the view (the desktop's studio
  // sits on the window's glass instead).
  const groundCanvas = document.createElement('canvas')
  groundCanvas.width = groundCanvas.height = 128
  const paint = groundCanvas.getContext('2d')
  if (paint) {
    const fade = paint.createRadialGradient(64, 64, 0, 64, 64, 64)
    fade.addColorStop(0, options.dark ? 'rgba(0, 0, 0, 0.55)' : 'rgba(38, 48, 78, 0.28)')
    fade.addColorStop(0.5, options.dark ? 'rgba(0, 0, 0, 0.25)' : 'rgba(38, 48, 78, 0.12)')
    fade.addColorStop(1, 'rgba(0, 0, 0, 0)')
    paint.fillStyle = fade
    paint.fillRect(0, 0, 128, 128)
  }
  const groundTexture = new THREE.CanvasTexture(groundCanvas)
  groundTexture.colorSpace = THREE.SRGBColorSpace
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(roomWidth + 9, roomDepth + 9),
    new THREE.MeshBasicMaterial({ map: groundTexture, transparent: true, depthWrite: false, toneMapped: false }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.26
  ground.renderOrder = -1
  scene.add(ground)

  const grid = new FloorGrid(obstacles())
  const floors = new Map<string, Floor>()
  let ordered: Floor[] = []
  const still = options.reducedMotion
  let paused = false
  let disposed = false
  /** The floor up close; null shows the whole building (with two floors or more). */
  let focused: string | null = null
  let move: { from: View; to: View; start: number } | null = null
  let shadowKey = ''
  let layoutKey = ''
  let viewName = ''
  /** The camera is placed once the stage has a size; until then nothing is drawn to fly from. */
  let framed = false
  /** The floor under the pointer in the building, for its sign. */
  let hovered: string | null = null

  const building = (): boolean => ordered.length >= 2
  const focusFloor = (): Floor | undefined => (focused === null ? undefined : floors.get(focused))
  const overview = (): boolean => building() && focused === null

  // The distance that frames a sphere of this radius, from the narrower of the two fields of view.
  const fitRadius = (radius: number): number => {
    const vertical = THREE.MathUtils.degToRad(camera.fov) / 2
    const horizontal = Math.atan(Math.tan(vertical) * camera.aspect)
    return radius / Math.sin(Math.min(vertical, horizontal))
  }
  // The distance at which the camera, at these angles, has every corner of the box in view.
  const fitBox = (target: THREE.Vector3, polar: number, azimuth: number, min: THREE.Vector3, max: THREE.Vector3): number => {
    const back = new THREE.Vector3().setFromSpherical(new THREE.Spherical(1, polar, azimuth))
    const right = new THREE.Vector3(0, 1, 0).cross(back).normalize()
    const up = back.clone().cross(right)
    const vertical = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)
    const horizontal = vertical * camera.aspect
    const corner = new THREE.Vector3()
    let distance = 0
    for (let index = 0; index < 8; index += 1) {
      corner.set(index & 1 ? max.x : min.x, index & 2 ? max.y : min.y, index & 4 ? max.z : min.z).sub(target)
      const depth = corner.dot(back)
      distance = Math.max(distance, depth + Math.abs(corner.dot(right)) / horizontal, depth + Math.abs(corner.dot(up)) / vertical)
    }
    return distance
  }
  const towerHeight = (): number => ordered.length * STOREY + 0.6
  /**
   * Close on the agent, a little closer while it works, the room's middle kept in the picture;
   * while its team is at work, wide enough for the desks, the board and the table.
   */
  const backdropView = (): View => {
    const room = ordered[0]
    const lead = room?.members.get('lead')
    const at = lead?.person.position ?? deskSeat(0)
    const working = lead !== undefined && lead.actor.state !== 'idle' && lead.actor.state !== 'done' && lead.actor.state !== 'stopped'
    // The agent a little right of the middle, where the conversation's lines are shorter; on a phone
    // held upright the lines are as long on both sides, so in the middle.
    const right = new THREE.Vector3(Math.cos(BACKDROP_ANGLES.azimuth), 0, -Math.sin(BACKDROP_ANGLES.azimuth))
    const upright = camera.aspect < 1
    const team = room !== undefined && [...room.members.values()].some((member) => !member.actor.lead
      && (member.actor.state === 'working' || member.actor.state === 'arriving' || member.actor.state === 'waiting'))
    // Upright, the picture moves up by this share of the screen's height: the agent above a new
    // conversation's greeting, the newest messages over the floor in front of it.
    const raise = (view: View, share: number): View => {
      if (!upright) return view
      const half = view.radius * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)
      return { ...view, target: view.target.clone().setY(view.target.y - (2 * share * half) / Math.sin(view.polar)) }
    }
    if (team) return raise({ target: TARGET.clone().addScaledVector(right, upright ? 0 : -0.9), radius: fitRadius(ROOM_RADIUS) * 0.52, ...BACKDROP_ANGLES }, 0.08)
    const target = TARGET.clone().lerp(new THREE.Vector3(at.x, 0.75, at.z), upright ? 0.85 : 0.7).addScaledVector(right, upright ? 0 : -1.1)
    // Close enough that the room fills the window: walls, floor and window behind every pane.
    return raise({ target, radius: fitRadius(ROOM_RADIUS) * (working ? 0.31 : 0.38), ...BACKDROP_ANGLES }, 0.18)
  }
  const destination = (): View => {
    if (mode === 'backdrop') return backdropView()
    if (overview()) {
      const height = towerHeight()
      // The building sits left of centre, leaving room on its right for the floors' signs.
      const aside = new THREE.Vector3(Math.cos(BUILDING_ANGLES.azimuth), 0, -Math.sin(BUILDING_ANGLES.azimuth)).multiplyScalar(ROOM_RADIUS * 0.3)
      const target = new THREE.Vector3(TARGET.x, height / 2 - 0.5, TARGET.z).add(aside)
      // All of it in view however few floors it has: the plinth with its trees, the roof with its mast.
      const min = new THREE.Vector3(ROOM.x0 - PLINTH_MARGIN, PLINTH_BOTTOM, ROOM.z0 - PLINTH_MARGIN)
      const max = new THREE.Vector3(ROOM.x1 + PLINTH_MARGIN, ordered.length * STOREY + ROOF_TOP, ROOM.z1 + PLINTH_MARGIN)
      return { target, radius: fitBox(target, BUILDING_ANGLES.polar, BUILDING_ANGLES.azimuth, min, max) * 1.04, ...BUILDING_ANGLES }
    }
    const index = focusFloor()?.index ?? 0
    const target = TARGET.clone().setY(TARGET.y + index * STOREY)
    if (camera.aspect < 1) {
      // A phone held upright: frame the room's own corners, which fills the narrow screen far
      // better than the circle around the room does.
      const base = index * STOREY
      const min = new THREE.Vector3(ROOM.x0, base, ROOM.z0)
      const max = new THREE.Vector3(ROOM.x1, base + ROOM.height, ROOM.z1)
      return { target, radius: fitBox(target, FLOOR_ANGLES.polar, FLOOR_ANGLES.azimuth, min, max) * 1.02, ...FLOOR_ANGLES }
    }
    return { target, radius: fitRadius(ROOM_RADIUS), ...FLOOR_ANGLES }
  }
  const current = (): View => {
    const spherical = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target))
    return { target: controls.target.clone(), radius: spherical.radius, polar: spherical.phi, azimuth: spherical.theta }
  }
  const setCamera = (view: View): void => {
    controls.target.copy(view.target)
    camera.position.setFromSpherical(new THREE.Spherical(view.radius, view.polar, view.azimuth)).add(view.target)
    camera.lookAt(view.target)
  }
  const limit = (): void => {
    const view = destination()
    controls.minDistance = view.radius * 0.45
    controls.maxDistance = view.radius * 1.5
    controls.minPolarAngle = 0.35
    controls.maxPolarAngle = overview() ? 1.45 : 1.28
    controls.minAzimuthAngle = -0.4
    controls.maxAzimuthAngle = 1.5
  }
  /** Fly to where the camera should be now; at once when motion is reduced or nothing is drawn yet. */
  const travel = (animate: boolean): void => {
    const to = destination()
    if (!animate || still || !framed) {
      move = null
      controls.enabled = mode === 'room'
      setCamera(to)
      limit()
      controls.update()
      return
    }
    move = { from: current(), to, start: performance.now() / 1000 }
    controls.enabled = false
  }
  const stepMove = (now: number): void => {
    if (!move) return
    const t = ease(Math.min(1, (now - move.start) / MOVE_SECONDS))
    const { from, to } = move
    // On the way in or out the camera swings a little wider than either end, as a crane would.
    const swing = Math.sin(t * Math.PI) * (overview() ? 0.04 : 0.08)
    setCamera({
      target: from.target.clone().lerp(to.target, t),
      radius: THREE.MathUtils.lerp(from.radius, to.radius, t) * (1 + swing),
      polar: THREE.MathUtils.lerp(from.polar, to.polar, t),
      azimuth: THREE.MathUtils.lerp(from.azimuth, to.azimuth, t),
    })
    if (now - move.start >= MOVE_SECONDS) {
      move = null
      controls.enabled = mode === 'room'
      setCamera(to)
      limit()
      controls.update()
    }
  }

  /**
   * Where every floor and the roof should be: the floors over the one in view lifted away. The
   * camera flies when where it should look changes, not when a floor opens out of view.
   */
  const arrange = (now: number, snap = false): void => {
    const seconds = still || snap ? 0 : MOVE_SECONDS
    const inView = focusFloor()
    for (const floor of ordered) {
      const lifted = building() && inView !== undefined && floor.index > inView.index
      floor.y.set(floor.index * STOREY + (lifted ? LIFT : 0), now, seconds)
    }
    const top = ordered.length * STOREY
    if (!building()) roofOn = false
    else if (!roofOn) {
      roofOn = true
      roofY = new Tween(top + LIFT)
    }
    roofY.set(top + (building() && inView !== undefined ? LIFT : 0), now, seconds)
    const next = overview() ? `building|${ordered.length}` : `floor|${inView?.index ?? 0}`
    if (next !== layoutKey) {
      layoutKey = next
      travel(!snap)
    }
  }

  const label = (member: Member): void => {
    const { actor, tag, bubble } = member
    tag.dataset.state = actor.state
    tag.dataset.lead = actor.lead ? 'true' : 'false'
    tag.querySelector('.studio-tag-name')!.textContent = actor.name
    tag.querySelector('.studio-tag-state')!.textContent = actor.stateLabel
    tag.setAttribute('aria-label', `${actor.name}: ${actor.stateLabel}`)
    member.tagSize = null
    bubble.textContent = actor.bubble ?? ''
    bubble.hidden = !actor.bubble
    bubble.dataset.state = actor.state
  }

  const sign = (floor: Floor): void => {
    const { view } = floor
    floor.sign.dataset.busy = view.busy ? 'true' : 'false'
    floor.sign.querySelector('.studio-floor-number')!.textContent = view.number
    floor.sign.querySelector('.studio-floor-title')!.textContent = view.title
    floor.sign.querySelector('.studio-floor-summary')!.textContent = view.summary
    floor.sign.setAttribute('aria-label', `${view.number} ${view.title}: ${view.summary}`)
    floor.signWidth = floor.sign.offsetWidth
  }

  const addMember = (floor: Floor, actor: StudioActorView, desk: number, now: number): Member => {
    const seat = deskSeat(desk)
    // A sub-agent whose task was over before it was seen has gone already.
    const out = Boolean(actor.leaves) && actor.state !== 'working' && actor.state !== 'arriving' && actor.state !== 'waiting' && actor.state !== 'answering'
    const person = new Person(actor.id, actor.look, floor.first && !out ? seat : DOOR, options.accent, finishes)
    if (floor.first && !out) person.heading = Math.atan2(seat.face.x - seat.x, seat.face.z - seat.z)
    person.root.visible = !out
    floor.group.add(person.root)
    const tag = document.createElement('button')
    tag.type = 'button'
    tag.className = 'studio-tag'
    tag.tabIndex = -1
    const dot = document.createElement('span')
    dot.className = 'studio-tag-dot'
    const name = document.createElement('span')
    name.className = 'studio-tag-name'
    const state = document.createElement('span')
    state.className = 'studio-tag-state'
    tag.append(dot, name, state)
    tag.addEventListener('click', () => handlers.pick(floor.id, actor.id))
    const bubble = document.createElement('div')
    bubble.className = 'studio-bubble'
    overlay.append(bubble, tag)
    const member: Member = {
      person, actor, desk, tag, bubble, since: now, idleNext: now + 4 + Math.random() * 6, idlePlace: null,
      spotSince: now, errands: new Set(actor.errand ? [actor.errand] : []), errand: null, gone: out, enters: 0,
      key: out ? placeKey(OUTSIDE) : '', tagSize: null,
    }
    label(member)
    return member
  }

  const removeMember = (member: Member): void => {
    member.person.dispose()
    member.tag.remove()
    member.bubble.remove()
  }

  const addFloor = (view: StudioFloorView, index: number): Floor => {
    const group = new THREE.Group()
    group.userData.floorId = view.id
    const room = buildRoom(roomKit)
    group.add(room.group)
    const posts = new THREE.Group()
    for (const mesh of meshesOf(postParts, finishes)) posts.add(mesh)
    group.add(posts)
    const signButton = document.createElement('button')
    signButton.type = 'button'
    signButton.className = 'studio-floor-sign'
    signButton.tabIndex = -1
    for (const part of ['studio-floor-number', 'studio-floor-title', 'studio-floor-summary']) {
      const span = document.createElement('span')
      span.className = part
      signButton.append(span)
    }
    signButton.addEventListener('click', () => handlers.pickFloor(view.id))
    signButton.style.visibility = 'hidden'
    overlay.append(signButton)
    const floor: Floor = { id: view.id, index, view, group, room, posts, members: new Map(), first: true, notesSignature: '', y: new Tween(index * STOREY), sign: signButton, signWidth: 0 }
    group.position.y = index * STOREY
    scene.add(group)
    return floor
  }

  const removeFloor = (floor: Floor): void => {
    for (const member of floor.members.values()) removeMember(member)
    floor.members.clear()
    floor.room.dispose()
    floor.group.removeFromParent()
    floor.sign.remove()
  }

  const updateCast = (floor: Floor, cast: readonly StudioActorView[], now: number): void => {
    const ids = new Set(cast.map((actor) => actor.id))
    for (const [id, member] of floor.members) {
      if (ids.has(id)) continue
      removeMember(member)
      floor.members.delete(id)
    }
    let desk = 1
    let arriving = 0
    for (const actor of cast) {
      const index = actor.lead ? 0 : desk++
      const existing = floor.members.get(actor.id)
      if (!existing) {
        const member = addMember(floor, actor, index, now)
        // Newcomers through the door one after another, not in a heap.
        if (!floor.first && !member.gone) member.enters = now + ENTRY_GAP * arriving++
        floor.members.set(actor.id, member)
        continue
      }
      if (existing.actor.state !== actor.state) {
        existing.since = now
        if (actor.state === 'done') existing.person.cheer(now)
      }
      if (existing.actor.spot !== actor.spot) existing.spotSince = now
      existing.actor = actor
      existing.desk = index
      label(existing)
    }
    floor.first = false
  }

  const update = (views: readonly StudioFloorView[]): void => {
    const now = performance.now() / 1000
    // The first layout is shown as it is; later ones move into place.
    const opening = floors.size === 0
    const ids = new Set(views.map((view) => view.id))
    for (const [id, floor] of floors) {
      if (ids.has(id)) continue
      removeFloor(floor)
      floors.delete(id)
    }
    const next: Floor[] = []
    const fresh: Floor[] = []
    views.forEach((view, index) => {
      let floor = floors.get(view.id)
      if (!floor) {
        floor = addFloor(view, index)
        floors.set(view.id, floor)
        fresh.push(floor)
      }
      floor.index = index
      floor.view = view
      sign(floor)
      updateCast(floor, view.cast, now)
      next.push(floor)
    })
    const wasBuilding = building()
    ordered = next
    // One room on its own is always up close; a room that becomes a building is first seen
    // whole, as the page says; a building keeps the floor in view if it is still there.
    if (!building()) focused = ordered[0]?.id ?? null
    else if (!wasBuilding || (focused !== null && !floors.has(focused))) focused = null
    // A new floor over the one in view waits out of sight above; one that opens while the
    // whole building is in view comes down into its place.
    const inView = focusFloor()
    for (const floor of fresh) {
      const lifted = building() && inView !== undefined && floor.index > inView.index
      const target = floor.index * STOREY + (lifted ? LIFT : 0)
      floor.y = new Tween(target + (overview() && !opening && !still ? ARRIVAL : 0))
      floor.y.set(target, now, MOVE_SECONDS)
      floor.group.position.y = floor.y.value(now)
    }
    arrange(now, opening)
  }

  /** Where each person on a floor should be now, and what they do there. */
  const plan = (floor: Floor, now: number): void => {
    const taken = new Map<string, number>()
    const slot = (places: readonly Place[], fallback: Place): Place => {
      for (const place of places) {
        const keyed = placeKey(place)
        if (!taken.has(keyed)) { taken.set(keyed, 1); return place }
      }
      return fallback
    }
    for (const member of floor.members.values()) {
      const { actor, person } = member
      const seat = deskSeat(member.desk)
      const resting = actor.state === 'idle' || actor.state === 'stopped' || (actor.state === 'done' && now - member.since > DONE_SECONDS)
      // A document was just made: fetch it from the printer, once, unless something else comes first.
      if (actor.errand && !member.errands.has(actor.errand)) {
        member.errands.add(actor.errand)
        if (!still) member.errand = { phase: 'fetch', at: null }
      }
      if (member.errand && (resting || actor.state === 'waiting' || actor.state === 'failed')) member.errand = null
      // A sub-agent whose task is over goes out by the door (one that failed after a while too).
      const leaving = Boolean(actor.leaves) && (resting || (actor.state === 'failed' && now - member.since > DONE_SECONDS))
      if (!leaving && member.gone) {
        member.gone = false
        person.root.visible = true
      }
      let place: Place
      if (leaving) {
        place = OUTSIDE
        if (member.key === placeKey(OUTSIDE) && !person.walking && !member.gone) {
          member.gone = true
          person.root.visible = false
        }
      } else if (member.errand) {
        const errand = member.errand
        const there = (target: Place): boolean => member.key === placeKey(target) && !person.walking
        if (errand.phase === 'fetch' && there(PRINTER_PLACE)) {
          errand.at ??= now
          if (now - errand.at > PRINT_SECONDS) errand.phase = 'carry'
        } else if (errand.phase === 'carry' && there(seat)) {
          member.errand = null
        }
        place = member.errand?.phase === 'fetch' ? PRINTER_PLACE : seat
      } else if (resting) {
        // Behind the conversation an idle room stays still (a phone's battery: no frames while nothing
        // goes on); looked at in full, an idle person gets up now and then: coffee, water, the sofa,
        // or back to the desk.
        if (!still && mode === 'room' && now > member.idleNext && !person.walking) {
          const choices = [seat, ...IDLE_PLACES].filter((item) => item === seat || !taken.has(placeKey(item)))
          member.idlePlace = choices[Math.floor(Math.random() * choices.length)] ?? seat
          member.idleNext = now + (actor.lead ? 22 : 12) + Math.random() * 16
        }
        place = member.idlePlace ?? seat
      } else {
        member.idlePlace = null
        member.idleNext = now + 6
        place = actor.spot === 'shelf' ? slot(SHELF_PLACES, seat)
          : actor.spot === 'terminal' ? slot(TERMINAL_PLACES, seat)
          : actor.spot === 'sandbox' ? slot(SANDBOX_PLACES, seat)
          : actor.spot === 'door' ? slot([DOOR_PLACE], seat)
            : actor.spot === 'table' ? slot(actor.lead ? [TABLE_PLACES[3]!, ...TABLE_PLACES] : TABLE_PLACES, seat)
              : actor.spot === 'board' ? slot([BOARD_PLACE], seat)
                : actor.spot === 'window'
                  // After a while at the window they pace in front of it.
                  ? WINDOW_PLACES[now - member.spotSince > PACE_AFTER && !still ? Math.floor((now - member.spotSince) / 7) % 2 : 0]!
                  : seat
      }
      // Waiting outside the door for the one before to go in.
      if (now < member.enters) place = { x: DOOR.x, z: DOOR.z, face: DOORWAY, sit: false }
      taken.set(placeKey(place), 1)
      const keyed = placeKey(place)
      if (keyed !== member.key) {
        member.key = keyed
        person.goTo(place, grid.path(person.position, place))
      }
      person.action = actionFor(member, place)
    }
  }

  /** A floor's room follows the work: screens, notes on the board, the review glow, the rack. */
  const dress = (floor: Floor, now: number): void => {
    const { room, members } = floor
    const atDesk = new Map<number, Member>()
    for (const member of members.values()) {
      if (member.person.seated && member.key === placeKey(deskSeat(member.desk))) atDesk.set(member.desk, member)
    }
    room.screens.forEach((screen, index) => {
      const member = atDesk.get(index)
      const action = member?.person.action
      const busy = action === 'type' || action === 'think' || action === 'browse'
      // A web page is brighter, and flickers as it scrolls.
      const web = action === 'browse'
      screen.emissive.set(web ? (options.dark ? '#8ab4ea' : '#9cc3f2') : busy ? (options.dark ? '#3d7bd9' : '#4b8fe6') : '#203048')
      screen.emissiveIntensity = busy ? (web ? 1.0 : 0.9) + (still ? 0 : Math.sin(now * (web ? 3 : 7) + index) * (web ? 0.14 : 0.08)) : member ? 0.45 : 0.25
    })
    const workers = [...members.values()].filter((member) => !member.actor.lead && (member.actor.state === 'working' || member.actor.state === 'arriving'))
    const signature = workers.map((member) => member.actor.look.shirt).join()
    if (signature !== floor.notesSignature) {
      floor.notesSignature = signature
      for (const note of [...room.notes.children]) {
        room.notes.remove(note)
        ;((note as THREE.Mesh).material as THREE.Material).dispose()
      }
      workers.forEach((member, index) => {
        const note = new THREE.Mesh(NOTE, new THREE.MeshStandardMaterial({ color: member.actor.look.shirt, roughness: 0.9 }))
        note.position.set(0, 0.22 - Math.floor(index / 2) * 0.28, -0.45 + (index % 2) * 0.32)
        note.rotation.x = (index % 2 ? -1 : 1) * 0.06
        room.notes.add(note)
      })
    }
    // Working on its own, the agent has its desk lamp on; pages wait in the printer's tray.
    const lead = members.get('lead')
    const alone = [...members.values()].every((member) => member.actor.lead)
    const late = alone && lead !== undefined && (lead.actor.state === 'working' || lead.actor.state === 'answering' || lead.actor.state === 'waiting' || lead.errand !== null)
    const glow = late ? (options.dark ? 6 : 2.5) : 0
    room.deskLamp.intensity += (glow - room.deskLamp.intensity) * (still ? 1 : 0.08)
    room.printout.visible = [...members.values()].some((member) => member.errand?.phase === 'fetch')
    // The sandbox's door opens for whoever comes near; its strip is green while code runs inside,
    // amber while someone waits outside to be allowed to touch this computer.
    const near = [...members.values()].some((member) => Math.hypot(member.person.position.x - DOOR_CENTER.x, member.person.position.z - DOOR_CENTER.z) < 1.0)
    const door = room.sandbox.door
    const closed = (GLASS.door.x0 + GLASS.door.x1) / 2
    const target = closed - (near ? (GLASS.door.x1 - GLASS.door.x0) * 0.9 : 0)
    door.position.x += (target - door.position.x) * (still ? 1 : 0.12)
    const inside = [...members.values()].some((member) => member.actor.spot === 'sandbox' && member.person.action === 'operate' && !member.person.walking)
    const waiting = [...members.values()].some((member) => member.actor.spot === 'door' && member.actor.state === 'waiting')
    const pulse = still ? 1 : 0.75 + Math.sin(now * 3) * 0.25
    room.sandbox.strip.color.set(inside ? '#38d39f' : waiting ? '#f2b33d' : options.dark ? '#3a4558' : '#c4ccd6')
    if (inside || waiting) room.sandbox.strip.color.multiplyScalar(pulse * 1.4)
    // The room's door swings out for whoever passes through it.
    const passing = [...members.values()].some((member) => !member.gone && Math.hypot(member.person.position.x - DOORWAY.x, member.person.position.z - DOORWAY.z) < 1.3)
    room.entrance.rotation.y += ((passing ? DOOR_OPEN : 0) - room.entrance.rotation.y) * (still ? 1 : 0.14)
    const reviewing = [...members.values()].some((member) => member.actor.state === 'working' && member.actor.spot === 'table')
    room.ring.visible = reviewing
    if (reviewing && !still) {
      room.ring.rotation.z = now * 0.8
      room.ring.position.y = 0.95 + Math.sin(now * 2) * 0.03
    }
    // The rack's two sets of lights blink in turn while someone runs code at the console.
    const operating = [...members.values()].some((member) => member.person.action === 'operate' && !member.person.walking)
    room.leds.forEach((led, index) => {
      led.color.setScalar(operating && !still ? (Math.sin(now * 9 + index * Math.PI) > 0 ? 1.6 : 0.25) : 0.7)
    })
    const time = new Date()
    room.clock.minute.rotation.z = -((time.getMinutes() + time.getSeconds() / 60) / 60) * Math.PI * 2
    room.clock.hour.rotation.z = -(((time.getHours() % 12) + time.getMinutes() / 60) / 12) * Math.PI * 2
  }

  /**
   * Floors, roof and lights for this frame: hidden floors once the camera has arrived. True when
   * nothing is on the way.
   */
  const stack = (now: number): boolean => {
    let settled = move === null && roofY.done(now)
    for (const floor of ordered) {
      floor.group.position.y = floor.y.value(now)
      settled &&= floor.y.done(now)
    }
    roof.position.y = roofY.value(now)
    const inView = focusFloor()
    const wide = building() && (inView === undefined || !settled)
    roof.visible = wide
    plinth.visible = wide
    // Under the floor slab of the room in view, or under the plinth when the whole building is.
    ground.position.y = wide ? PLINTH_BOTTOM - 0.01 : (inView?.group.position.y ?? 0) - 0.26
    for (const floor of ordered) {
      const close = !building() || floor === inView
      floor.group.visible = wide || close
      floor.posts.visible = wide
      // At night the room up close has all its lamps on; from outside each floor shows one.
      floor.room.lamps.forEach((lamp, index) => { lamp.visible = (close && settled) || (wide && index === 0) })
      floor.room.deskLamp.visible = close && settled
    }
    // The key light frames the floor in view, or the whole building.
    const span = wide ? towerHeight() : ROOM.height
    const centre = wide ? span / 2 - 0.5 : (inView?.index ?? 0) * STOREY + 1
    const half = wide ? Math.max(9, (15 + 0.66 * span) / 2 + 1) : 9
    const keyed = `${centre.toFixed(2)}|${half.toFixed(2)}`
    if (keyed !== shadowKey) {
      shadowKey = keyed
      key.target.position.set(0, centre, 0)
      key.position.copy(SUN).multiplyScalar(1 + half / SUN.length()).add(key.target.position)
      const shadow = key.shadow.camera
      shadow.left = -half
      shadow.right = half
      shadow.top = half
      shadow.bottom = -half
      shadow.far = 2 * (SUN.length() + half) + 10
      shadow.updateProjectionMatrix()
    }
    const name = `${inView === undefined && building() ? 'building' : 'floor'}|${settled}`
    if (name !== viewName) {
      viewName = name
      overlay.dataset.view = inView === undefined && building() ? 'building' : 'floor'
      overlay.dataset.moving = settled ? 'false' : 'true'
    }
    return settled
  }

  const projected = new THREE.Vector3()
  const project = (x: number, y: number, z: number): { x: number; y: number; z: number; visible: boolean } => {
    projected.set(x, y, z).project(camera)
    return {
      x: (projected.x * 0.5 + 0.5) * stage.clientWidth,
      y: (-projected.y * 0.5 + 0.5) * stage.clientHeight,
      z: projected.z,
      visible: projected.z < 1 && Math.abs(projected.x) < 1.2 && Math.abs(projected.y) < 1.2,
    }
  }
  /** Behind the conversation the camera drifts after the agent; true while it is still on its way. */
  const follow = (dt: number): boolean => {
    const from = current()
    const to = backdropView()
    const k = still ? 1 : 1 - Math.exp(-dt * 1.4)
    const away = from.target.distanceTo(to.target) + Math.abs(from.radius - to.radius) * 0.2 + Math.abs(from.polar - to.polar) + Math.abs(from.azimuth - to.azimuth)
    if (away < 0.01) return false
    setCamera({
      target: from.target.lerp(to.target, k),
      radius: THREE.MathUtils.lerp(from.radius, to.radius, k),
      polar: THREE.MathUtils.lerp(from.polar, to.polar, k),
      azimuth: THREE.MathUtils.lerp(from.azimuth, to.azimuth, k),
    })
    return true
  }

  const place = (): void => {
    const inView = focusFloor()
    const signs = overview() && move === null
    for (const floor of ordered) {
      const lift = floor.group.position.y
      // People's labels on the floor in view once the camera is there; signs on the building.
      const tags = (!building() || floor === inView) && move === null
      // Nearer people first: a tag that would cover a nearer one shows only its dot (a phone's
      // narrow view puts neighbours' tags on top of each other; the roster below names everyone).
      const people = [...floor.members.values()]
        .map((member) => ({ member, point: project(member.person.position.x, lift + member.person.top + 0.12, member.person.position.z) }))
        .sort((a, b) => a.point.z - b.point.z)
      const taken: Array<[number, number, number, number]> = []
      for (const { member, point } of people) {
        const shown = tags && point.visible && !member.gone
        let compact = false
        if (shown) {
          let size = member.tagSize
          if (!size) {
            member.tag.dataset.compact = 'false'
            size = [member.tag.offsetWidth, member.tag.offsetHeight]
            if (size[0] > 0) member.tagSize = size
          }
          const [width, height] = size
          const box: [number, number, number, number] = [point.x - width / 2, point.y - height, point.x + width / 2, point.y]
          compact = taken.some(([left, top, right, bottom]) => box[0] < right + 2 && box[2] > left - 2 && box[1] < bottom + 2 && box[3] > top - 2)
          if (!compact) taken.push(box)
        }
        if (member.tag.dataset.compact !== String(compact)) member.tag.dataset.compact = String(compact)
        member.tag.style.transform = `translate(${point.x.toFixed(1)}px, ${point.y.toFixed(1)}px) translate(-50%, -100%)`
        member.bubble.style.transform = `translate(${point.x.toFixed(1)}px, ${(point.y - 30).toFixed(1)}px) translate(-50%, -100%)`
        member.tag.style.visibility = shown ? 'visible' : 'hidden'
        member.bubble.style.visibility = shown ? 'visible' : 'hidden'
        // Nearer people draw over farther ones.
        const depth = String(Math.round((1 - point.z) * 10000))
        member.tag.style.zIndex = depth
        member.bubble.style.zIndex = depth
      }
      // Beside the floor's far right corner, kept inside the stage.
      const corner = project(ROOM.x1 + 0.4, lift + ROOM.height * 0.5, ROOM.z0 + 0.6)
      const left = Math.max(8, Math.min(corner.x + 12, stage.clientWidth - floor.signWidth - 8))
      floor.sign.style.transform = `translate(${left.toFixed(1)}px, ${corner.y.toFixed(1)}px) translate(0, -50%)`
      floor.sign.style.visibility = signs && corner.visible ? 'visible' : 'hidden'
      floor.sign.dataset.hover = hovered === floor.id ? 'true' : 'false'
    }
  }

  const resize = (): void => {
    renderer.setPixelRatio(pixelRatio())
    const width = Math.max(1, stage.clientWidth)
    const height = Math.max(1, stage.clientHeight)
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    // Frame the view once the stage has a size; later the user's own zoom stays.
    if (!framed && stage.clientWidth > 0) {
      framed = true
      travel(false)
    }
  }
  const observer = new ResizeObserver(() => {
    resize()
    wake()
  })
  observer.observe(stage)
  resize()

  // Picking: a click (not a drag) on a person up close, or on a floor of the building.
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  let down: { x: number; y: number } | null = null
  const floorOf = (object: THREE.Object3D | null): string | null => {
    for (let node = object; node; node = node.parent) {
      if (typeof node.userData.floorId === 'string') return node.userData.floorId
    }
    return null
  }
  const hit = (event: PointerEvent): { floor: string; person: string | null } | null => {
    if (move) return null
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    if (overview()) {
      const found = raycaster.intersectObjects(ordered.map((floor) => floor.group), true)[0]
      const floor = found ? floorOf(found.object) : null
      return floor ? { floor, person: null } : null
    }
    const floor = focusFloor() ?? ordered[0]
    if (!floor) return null
    const found = raycaster.intersectObjects([...floor.members.values()].filter((member) => !member.gone).map((member) => member.person.root), true)[0]
    const person = found ? (found.object.userData.personId as string | undefined) ?? null : null
    return person ? { floor: floor.id, person } : null
  }
  // While the user turns or zooms the view (and its damping runs out), draw at the full rate.
  let handledUntil = 0
  const handled = (): void => {
    handledUntil = performance.now() + 1500
    wake()
  }
  const onDown = (event: PointerEvent): void => {
    down = { x: event.clientX, y: event.clientY }
    handled()
  }
  const onUp = (event: PointerEvent): void => {
    if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 5) {
      const label = labelAt(overlay, event.clientX, event.clientY)
      const found = label ? null : hit(event)
      if (label) label.click()
      else if (found?.person) handlers.pick(found.floor, found.person)
      else if (found) handlers.pickFloor(found.floor)
    }
    down = null
  }
  const onMove = (event: PointerEvent): void => {
    if (event.buttons) {
      handled()
      return
    }
    const found = hit(event)
    hovered = found && !found.person ? found.floor : null
    renderer.domElement.style.cursor = found ? 'pointer' : 'grab'
  }
  const onLeave = (): void => { hovered = null }
  renderer.domElement.addEventListener('pointerdown', onDown)
  renderer.domElement.addEventListener('pointerup', onUp)
  renderer.domElement.addEventListener('pointermove', onMove)
  renderer.domElement.addEventListener('pointerleave', onLeave)
  renderer.domElement.addEventListener('wheel', handled, { passive: true })
  const onLost = (event: Event): void => event.preventDefault()
  renderer.domElement.addEventListener('webglcontextlost', onLost)

  /** The next frame asked for, 0 while drawing has stopped (calm, hidden or disposed). */
  let frame = 0
  let last = performance.now()
  let drawn = 0
  // What a frame costs, on the stage once a second: draw calls, triangles, milliseconds of work.
  let measured = 0
  let spent = 0
  /** Whether anything moved last frame (someone walking, floors or the camera on the way). */
  let lively = true
  /** Since when nothing has moved, worked or been touched; drawing stops SLEEP_AFTER_MS later. */
  let calmSince = performance.now()
  /** The shadows need drawing again: something changed or moved since they were last drawn. */
  let shadowsStale = true
  /** Off while another page draws the studio, a place of the campus is shown instead, or the app is away. */
  let active = true
  /** A long wait for the next frame (a second behind the conversation) goes by this timer, 0 when none. */
  let timer = 0
  /** Until when frames are drawn as while someone walks (exercise), whatever happens in the room. */
  let exercising = 0
  const working = (): boolean => ordered.some((floor) => [...floor.members.values()].some((member) =>
    member.actor.state === 'working' || member.actor.state === 'answering' || member.actor.state === 'arriving' || member.actor.state === 'waiting'))
  const halt = (): void => {
    cancelAnimationFrame(frame)
    window.clearTimeout(timer)
    frame = 0
    timer = 0
  }
  function wake(): void {
    calmSince = performance.now()
    shadowsStale = true
    stage.dataset.sleeping = 'false'
    if (frame === 0 && active && !disposed && !document.hidden) {
      window.clearTimeout(timer)
      timer = 0
      last = performance.now()
      frame = requestAnimationFrame(loop)
    }
  }
  /** The next frame in this long: a screen frame soon, a timer for a longer wait (asking for every
   * screen frame only to skip it keeps the page busy for nothing). */
  const later = (wait: number): void => {
    if (wait <= 50) {
      frame = requestAnimationFrame(loop)
      return
    }
    timer = window.setTimeout(() => {
      timer = 0
      if (frame === 0 && active && !disposed && !document.hidden) frame = requestAnimationFrame(loop)
    }, wait - 16)
  }
  // 30 frames a second while things move, 12 while people only sway or type; never more, also on
  // faster screens. Behind the conversation fewer, except while the camera flies.
  const frameInterval = (time: number): number => (move ? FRAME_MS
    : mode === 'backdrop' ? (lively || time < exercising ? BACKDROP_FRAME_MS : BACKDROP_REST_MS)
      : lively || time < handledUntil || time < exercising ? FRAME_MS : RESTING_FRAME_MS)
  const loop = (time: number): void => {
    frame = 0
    if (disposed || !active || document.hidden) return
    const interval = frameInterval(time)
    if (time - drawn < interval - 2) {
      later(interval - (time - drawn))
      return
    }
    drawn = time
    const began = performance.now()
    const dt = Math.min(0.05, (time - last) / 1000)
    last = time
    const now = time / 1000
    let walking = false
    if (!paused) {
      for (const floor of ordered) {
        plan(floor, now)
        for (const member of floor.members.values()) {
          member.person.update(dt, now, still)
          walking ||= member.person.walking
        }
        dress(floor, now)
      }
    }
    lively = stack(now) === false || walking || move !== null
    if (move) stepMove(now)
    else if (mode === 'backdrop') lively = follow(dt) || lively
    else controls.update()
    if (lively || shadowsStale || time < exercising) {
      renderer.shadowMap.needsUpdate = true
      shadowsStale = false
    }
    renderer.render(scene, camera)
    if (mode === 'room') place()
    spent += performance.now() - began
    measured += 1
    if (measured >= 60) {
      stage.dataset.drawCalls = String(renderer.info.render.calls)
      stage.dataset.triangles = String(renderer.info.render.triangles)
      stage.dataset.frameMs = (spent / measured).toFixed(2)
      measured = 0
      spent = 0
    }
    // Nothing moves, nobody works and nobody touches the view: stop drawing until something changes.
    const clock = performance.now()
    if (lively || clock < handledUntil || clock < exercising || (working() && !paused)) calmSince = clock
    if (clock - calmSince < SLEEP_AFTER_MS) later(frameInterval(clock))
    else stage.dataset.sleeping = 'true'
  }
  // Out of sight (the app in the background, the screen off): no frames until it is back.
  const onVisibility = (): void => { if (!document.hidden) wake() }
  document.addEventListener('visibilitychange', onVisibility)
  frame = requestAnimationFrame(loop)

  return {
    update(views) {
      if (disposed) return
      update(views)
      wake()
    },
    focus(floorId) {
      if (disposed || !building()) return
      focused = floorId !== null && floors.has(floorId) ? floorId : null
      arrange(performance.now() / 1000)
      wake()
    },
    setPaused(next) {
      paused = next
      wake()
    },
    setMode(next) {
      if (disposed || next === mode) return
      mode = next
      stage.dataset.mode = next
      controls.enabled = false
      resize()
      travel(true)
      wake()
    },
    setActive(next) {
      if (disposed || next === active) return
      active = next
      stage.dataset.active = String(next)
      if (active) wake()
      else halt()
    },
    resetView() {
      travel(true)
      wake()
    },
    exercise(ms) {
      if (disposed) return
      exercising = performance.now() + ms
      wake()
    },
    dispose() {
      disposed = true
      halt()
      document.removeEventListener('visibilitychange', onVisibility)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onDown)
      renderer.domElement.removeEventListener('pointerup', onUp)
      renderer.domElement.removeEventListener('pointermove', onMove)
      renderer.domElement.removeEventListener('pointerleave', onLeave)
      renderer.domElement.removeEventListener('wheel', handled)
      renderer.domElement.removeEventListener('webglcontextlost', onLost)
      controls.dispose()
      for (const floor of floors.values()) removeFloor(floor)
      floors.clear()
      ordered = []
      roof.removeFromParent()
      plinth.removeFromParent()
      for (const group of [roof, plinth]) group.traverse((object) => { if (object instanceof THREE.Mesh) object.geometry.dispose() })
      for (const part of postParts) part.geometry.dispose()
      ground.removeFromParent()
      ground.geometry.dispose()
      ground.material.dispose()
      groundTexture.dispose()
      roomKit.dispose()
      disposeFinishes(finishes)
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    },
  }
}

import * as THREE from 'three'

import {
  BOARD,
  CONSOLE,
  COOLER,
  COUNTER,
  DESK_SIZE,
  DESK_X_COUNT,
  PLANTS,
  RACK,
  ROOM,
  SEAT_Z,
  SHELF,
  SOFA,
  TABLE,
  TABLE_PLACES,
  deskCenter,
} from './layout'
import {
  Batch,
  boxShape,
  coneShape,
  cylinderShape,
  dodecaShape,
  meshesOf,
  sphereShape,
  torusShape,
  type Finishes,
} from './mesh-kit'

export interface RoomTheme {
  dark: boolean
  accent: string
}

/** Parts of one floor's room that change while people work. */
export interface Room {
  group: THREE.Group
  /** Screen of each desk: lit while someone works there. */
  screens: THREE.MeshStandardMaterial[]
  /** Sticky notes on the whiteboard, one per expert at work. */
  notes: THREE.Group
  /** The glow over the meeting table during a review. */
  ring: THREE.Mesh
  /** Two sets of status lights on the server rack; their brightness is the colour's scale. */
  leds: THREE.MeshBasicMaterial[]
  clock: { hour: THREE.Object3D; minute: THREE.Object3D }
  lamps: THREE.PointLight[]
  dispose(): void
}

/**
 * What every floor's room is made of, built once for the scene: the furniture merged into a
 * few meshes per finish, and the shapes of the parts each floor animates on its own.
 */
export interface RoomKit {
  readonly theme: RoomTheme
  readonly finishes: Finishes
  readonly furniture: ReturnType<Batch['build']>
  readonly floor: { geometry: THREE.BufferGeometry; material: THREE.MeshStandardMaterial; texture: THREE.Texture }
  readonly leds: [THREE.BufferGeometry, THREE.BufferGeometry]
  readonly hands: { hour: THREE.BufferGeometry; minute: THREE.BufferGeometry; material: THREE.MeshStandardMaterial }
  dispose(): void
}

const WALL = 0.18
const SCREEN = boxShape(0.58, 0.34, 0.008)
const RING = torusShape(0.42, 0.025, Math.PI * 2, 8, 40)

/** Plank lines on the floor, drawn once. */
function floorTexture(dark: boolean): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const context = canvas.getContext('2d')!
  context.fillStyle = dark ? '#76604b' : '#c9a37c'
  context.fillRect(0, 0, 512, 512)
  for (let row = 0; row < 8; row += 1) {
    const offset = (row % 2) * 128
    for (let column = -1; column < 3; column += 1) {
      const shade = ((row * 7 + column * 3) % 5) / 5
      context.fillStyle = dark ? `rgba(0,0,0,${0.08 + shade * 0.08})` : `rgba(90,55,25,${0.05 + shade * 0.07})`
      context.fillRect(column * 256 + offset + 2, row * 64 + 2, 252, 60)
      // A faint grain line along each plank.
      context.fillStyle = dark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.12)'
      context.fillRect(column * 256 + offset + 10, row * 64 + 20 + (shade * 20), 236, 2)
    }
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(3, 2.2)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  return texture
}

function palette(dark: boolean) {
  return dark
    ? {
        wall: '#4d5466', wallLow: '#434a5b', trim: '#262a33', skirt: '#2b2f38', sky: '#1d2e5c', frame: '#2c303a',
        deskTop: '#6b5a4a', deskFrame: '#3a3f4b', chair: '#2f3442', seat: '#3d4456', wood: '#4e3b2c', woodLight: '#5f4836',
        sofa: '#5a4b72', cushion: '#6d5d88', rug: '#3c3346', rugLounge: '#2f3a4a', pot: '#8a5a44', soil: '#3a2a20',
        leaf: '#4f8a5b', leafLight: '#6aa86f', counter: '#4e3b2c', top: '#6b5a4a', cooler: '#b9bfc8', lampShade: '#ffd9a0',
      }
    : {
        wall: '#f1ece4', wallLow: '#e6ddd0', trim: '#d9cfc1', skirt: '#e9e4dc', sky: '#bfe3ff', frame: '#e8e2d8',
        deskTop: '#e8dccb', deskFrame: '#9aa1ab', chair: '#4c5566', seat: '#5c677c', wood: '#a5784f', woodLight: '#bf9468',
        sofa: '#7f9cc0', cushion: '#9bb4d4', rug: '#d9cbe0', rugLounge: '#c9d6e3', pot: '#c1785a', soil: '#5a4030',
        leaf: '#4f8a5b', leafLight: '#6aa86f', counter: '#a5784f', top: '#e8dccb', cooler: '#d9dde3', lampShade: '#fff1d6',
      }
}

/** The merged furniture of a room, in the room's own coordinates (floor at y = 0). */
function furnish(theme: RoomTheme): Batch {
  const batch = new Batch()
  const c = palette(theme.dark)
  const width = ROOM.x1 - ROOM.x0
  const depth = ROOM.z1 - ROOM.z0

  // Shell: the slab's skirt and bright edge, two walls with a lower panel, rails and skirting.
  batch.add(boxShape(width + 0.1, 0.12, depth + 0.1), c.skirt, { y: -0.3 }, 'matte', false)
  batch.add(boxShape(width + 0.12, 0.05, 0.05), c.trim, { y: -0.21, z: ROOM.z1 + 0.06 }, 'satin', false)
  batch.add(boxShape(0.05, 0.05, depth + 0.12), c.trim, { x: ROOM.x1 + 0.06, y: -0.21 }, 'satin', false)
  const lowWall = 0.95
  batch.add(boxShape(width, lowWall, WALL + 0.02), c.wallLow, { y: lowWall / 2, z: ROOM.z0 - WALL / 2 })
  batch.add(boxShape(width, ROOM.height - lowWall, WALL), c.wall, { y: lowWall + (ROOM.height - lowWall) / 2, z: ROOM.z0 - WALL / 2 })
  batch.add(boxShape(WALL + 0.02, lowWall, depth + WALL), c.wallLow, { x: ROOM.x0 - WALL / 2, y: lowWall / 2, z: -WALL / 2 })
  batch.add(boxShape(WALL, ROOM.height - lowWall, depth + WALL), c.wall, { x: ROOM.x0 - WALL / 2, y: lowWall + (ROOM.height - lowWall) / 2, z: -WALL / 2 })
  for (const [y, h] of [[0.06, 0.12], [lowWall, 0.04], [ROOM.height - 0.02, 0.05]] as const) {
    batch.add(boxShape(width, h, 0.04), c.trim, { y, z: ROOM.z0 + 0.02 }, 'satin', false)
    batch.add(boxShape(0.04, h, depth), c.trim, { x: ROOM.x0 + 0.02, y }, 'satin', false)
  }

  // A wide window on the back wall: daylight or a night sky.
  batch.add(boxShape(4.7, 1.36, 0.06, 0.02), c.frame, { y: 1.62, z: ROOM.z0 + 0.03 }, 'satin', false)
  for (const x of [-1.65, -0.55, 0.55, 1.65]) batch.add(boxShape(1.04, 1.14, 0.02), c.sky, { x, y: 1.62, z: ROOM.z0 + 0.065 }, 'glow', false)
  for (const x of [-1.1, 0, 1.1]) batch.add(boxShape(0.06, 1.16, 0.05), c.frame, { x, y: 1.62, z: ROOM.z0 + 0.08 }, 'satin', false)
  batch.add(boxShape(4.6, 0.04, 0.05), c.frame, { y: 1.62, z: ROOM.z0 + 0.08 }, 'satin', false)
  batch.add(boxShape(4.9, 0.05, 0.16, 0.015), c.trim, { y: 0.92, z: ROOM.z0 + 0.08 }, 'satin', false)
  if (theme.dark) {
    for (const [x, y] of [[-1.8, 1.95], [-0.6, 1.8], [0.5, 2.0], [1.6, 1.75], [-1.3, 1.45], [0.9, 1.4], [1.9, 2.05], [-0.2, 2.1]] as const) {
      batch.add(boxShape(0.03, 0.03, 0.01), '#ffffff', { x, y, z: ROOM.z0 + 0.08 }, 'glow', false)
    }
    batch.add(cylinderShape(0.13, 0.13, 0.01, 20), '#fff1c4', { x: 1.55, y: 1.95, z: ROOM.z0 + 0.08, rx: Math.PI / 2 }, 'glow', false)
  } else {
    for (const [x, y, s] of [[-1.5, 1.95, 1], [0.9, 1.75, 0.8]] as const) {
      for (const [dx, dy, r] of [[0, 0, 0.12], [0.13, 0.02, 0.09], [-0.12, -0.01, 0.08]] as const) {
        batch.add(sphereShape(r * s, 10, 6), '#ffffff', { x: x + dx * s, y: y + dy * s, z: ROOM.z0 + 0.075, sz: 0.2 }, 'glow', false)
      }
    }
  }

  // A framed picture between the window and the corner, and a clock face (its hands move).
  batch.add(boxShape(1.0, 0.76, 0.05, 0.015), c.woodLight, { x: -4.05, y: 1.62, z: ROOM.z0 + 0.03 }, 'satin', false)
  batch.add(boxShape(0.88, 0.64, 0.02), '#f3efe7', { x: -4.05, y: 1.62, z: ROOM.z0 + 0.06 }, 'matte', false)
  for (const [x, y, w, h, color] of [[-4.25, 1.7, 0.3, 0.36, '#e07a5f'], [-3.9, 1.52, 0.4, 0.22, '#3d405b'], [-3.8, 1.78, 0.18, 0.18, '#f2cc8f']] as const) {
    batch.add(boxShape(w, h, 0.01), color, { x, y, z: ROOM.z0 + 0.075 }, 'matte', false)
  }
  batch.add(cylinderShape(0.27, 0.27, 0.04, 32), '#fbfaf7', { x: 3.6, y: 1.85, z: ROOM.z0 + 0.04, rx: Math.PI / 2 }, 'satin', false)
  batch.add(torusShape(0.27, 0.025, Math.PI * 2, 6, 32), '#3b3b40', { x: 3.6, y: 1.85, z: ROOM.z0 + 0.06 }, 'metal', false)
  for (let tick = 0; tick < 12; tick += 1) {
    const angle = (tick / 12) * Math.PI * 2
    batch.add(boxShape(0.018, tick % 3 === 0 ? 0.05 : 0.03, 0.01), '#3b3b40', { x: 3.6 + Math.sin(angle) * 0.21, y: 1.85 + Math.cos(angle) * 0.21, z: ROOM.z0 + 0.065, rz: -angle }, 'matte', false)
  }

  // Desks with a chair, a monitor, keyboard and mouse, and a few of their own things.
  for (let index = 0; index < DESK_X_COUNT; index += 1) {
    const { x, z } = deskCenter(index)
    const deskWidth = DESK_SIZE.width + (index === 0 ? 0.2 : 0)
    batch.add(boxShape(deskWidth, 0.045, DESK_SIZE.depth, 0.015), c.deskTop, { x, y: 0.645, z }, 'satin')
    for (const side of [-1, 1]) batch.add(boxShape(0.04, 0.62, DESK_SIZE.depth - 0.06, 0.01), c.deskFrame, { x: x + side * (deskWidth / 2 - 0.05), y: 0.31, z }, 'metal')
    batch.add(boxShape(deskWidth - 0.14, 0.28, 0.02), c.deskFrame, { x, y: 0.46, z: z + DESK_SIZE.depth / 2 - 0.06 }, 'metal')
    // The monitor faces the seat; its back faces the viewer.
    batch.add(boxShape(0.22, 0.014, 0.14, 0.006), '#2a2d35', { x, y: 0.674, z: z + 0.2 }, 'metal')
    batch.add(boxShape(0.04, 0.2, 0.03), '#5d6470', { x, y: 0.77, z: z + 0.22 }, 'metal')
    batch.add(boxShape(0.64, 0.4, 0.035, 0.014), '#1d2027', { x, y: 1.0, z: z + 0.2 }, 'satin')
    batch.add(boxShape(0.38, 0.018, 0.13, 0.006), '#2a2d35', { x, y: 0.676, z: z - 0.12 }, 'satin')
    batch.add(boxShape(0.34, 0.006, 0.1), '#3d414b', { x, y: 0.687, z: z - 0.12 }, 'matte', false)
    batch.add(boxShape(0.06, 0.024, 0.09, 0.011), '#2a2d35', { x: x + 0.29, y: 0.68, z: z - 0.12 }, 'satin', false)
    const item = index % 3
    if (index === 0) {
      // The lead's desk lamp.
      batch.add(cylinderShape(0.07, 0.08, 0.02, 16), '#2a2d35', { x: x - 0.55, y: 0.678, z: z + 0.15 }, 'metal')
      batch.add(boxShape(0.02, 0.36, 0.02), '#5d6470', { x: x - 0.55, y: 0.85, z: z + 0.1, rx: -0.35 }, 'metal')
      batch.add(coneShape(0.09, 0.12, 16), c.lampShade, { x: x - 0.55, y: 1.02, z: z - 0.02, rx: Math.PI * 0.85 }, theme.dark ? 'glow' : 'satin', false)
    } else if (item === 0) {
      batch.add(cylinderShape(0.045, 0.04, 0.1, 14), '#fbfaf7', { x: x - 0.38, y: 0.72, z: z - 0.05 }, 'satin', false)
      batch.add(torusShape(0.03, 0.008, Math.PI * 2, 6, 12), '#fbfaf7', { x: x - 0.33, y: 0.72, z: z - 0.05 }, 'satin', false)
    } else if (item === 1) {
      batch.add(cylinderShape(0.06, 0.05, 0.09, 12), c.pot, { x: x - 0.4, y: 0.71, z: z + 0.05 }, 'matte', false)
      batch.add(dodecaShape(0.08), c.leafLight, { x: x - 0.4, y: 0.81, z: z + 0.05 }, 'matte', false)
    } else {
      batch.add(boxShape(0.22, 0.02, 0.28, 0.005), ['#3d6fa5', '#c06c84', '#e0a13a'][index % 3]!, { x: x - 0.36, y: 0.678, z: z - 0.05, ry: 0.2 }, 'matte', false)
      batch.add(cylinderShape(0.008, 0.008, 0.16, 6), '#1d2027', { x: x - 0.3, y: 0.692, z: z - 0.06, rz: Math.PI / 2, ry: 0.5 }, 'satin', false)
    }
    // An office chair: cushion, back, arms, gas lift and a five-star base.
    batch.add(boxShape(0.46, 0.07, 0.44, 0.03), c.seat, { x, y: 0.29, z: SEAT_Z }, 'matte')
    batch.add(boxShape(0.44, 0.46, 0.06, 0.03), c.chair, { x, y: 0.62, z: SEAT_Z - 0.23, rx: -0.08 }, 'matte')
    batch.add(boxShape(0.05, 0.2, 0.03), '#3a3f4b', { x, y: 0.4, z: SEAT_Z - 0.22 }, 'metal')
    for (const side of [-1, 1]) {
      batch.add(boxShape(0.04, 0.12, 0.04), '#3a3f4b', { x: x + side * 0.24, y: 0.37, z: SEAT_Z - 0.02 }, 'metal')
      batch.add(boxShape(0.06, 0.025, 0.24, 0.01), c.chair, { x: x + side * 0.24, y: 0.44, z: SEAT_Z - 0.02 }, 'matte')
    }
    batch.add(cylinderShape(0.025, 0.025, 0.2, 10), '#5d6470', { x, y: 0.16, z: SEAT_Z }, 'metal')
    for (let leg = 0; leg < 5; leg += 1) {
      const angle = (leg / 5) * Math.PI * 2
      batch.add(boxShape(0.04, 0.025, 0.24), '#3a3f4b', { x: x + Math.sin(angle) * 0.12, y: 0.05, z: SEAT_Z + Math.cos(angle) * 0.12, ry: angle }, 'metal', false)
      batch.add(sphereShape(0.025, 8, 6), '#1d2027', { x: x + Math.sin(angle) * 0.24, y: 0.025, z: SEAT_Z + Math.cos(angle) * 0.24 }, 'satin', false)
    }
  }

  // Bookshelf on the left wall: rows of books, a few leaning, a vase on top.
  const shelfHeight = 2.0
  const shelfX = (SHELF.x0 + SHELF.x1) / 2
  const shelfZ = (SHELF.z0 + SHELF.z1) / 2
  const shelfDepth = SHELF.x1 - SHELF.x0
  const shelfWidth = SHELF.z1 - SHELF.z0
  for (const z of [SHELF.z0, SHELF.z1]) batch.add(boxShape(shelfDepth, shelfHeight, 0.05, 0.01), c.wood, { x: shelfX, y: shelfHeight / 2, z }, 'satin')
  batch.add(boxShape(0.03, shelfHeight, shelfWidth), c.woodLight, { x: SHELF.x0 + 0.02, y: shelfHeight / 2, z: shelfZ }, 'matte', false)
  const bookColors = ['#b5523b', '#3d6fa5', '#e0a13a', '#4f8a5b', '#7b5ea7', '#c06c84', '#2f4858', '#d9c5a0']
  for (let level = 0; level < 5; level += 1) {
    const y = 0.04 + level * 0.48
    batch.add(boxShape(shelfDepth, 0.035, shelfWidth, 0.008), c.wood, { x: shelfX, y, z: shelfZ }, 'satin')
    if (level === 4) break
    let cursor = SHELF.z0 + 0.08
    let book = level * 3
    while (cursor < SHELF.z1 - 0.14) {
      const thickness = 0.06 + ((book * 37) % 5) * 0.012
      const height = 0.26 + ((book * 13) % 4) * 0.035
      const lean = book % 9 === 4 ? 0.22 : 0
      batch.add(boxShape(0.22, height, thickness, 0.006), bookColors[book % bookColors.length]!, { x: SHELF.x0 + 0.17, y: y + 0.02 + height / 2, z: cursor + thickness / 2 + lean * 0.3, rx: lean }, 'matte', false)
      cursor += thickness + 0.01 + lean * 0.4
      book += 1
    }
  }
  batch.add(cylinderShape(0.06, 0.08, 0.2, 14), '#e8e2d8', { x: shelfX, y: shelfHeight + 0.12, z: SHELF.z0 + 0.35 }, 'satin', false)
  batch.add(dodecaShape(0.09), c.leaf, { x: shelfX, y: shelfHeight + 0.27, z: SHELF.z0 + 0.35 }, 'matte', false)

  // Whiteboard on the left wall, where the lead hands out the work.
  const boardZ = (BOARD.z0 + BOARD.z1) / 2
  const boardWidth = BOARD.z1 - BOARD.z0
  batch.add(boxShape(0.04, 1.08, boardWidth + 0.08, 0.012), '#aeb5bf', { x: BOARD.x, y: 1.45, z: boardZ }, 'metal')
  batch.add(boxShape(0.02, 1.0, boardWidth), '#fcfcfa', { x: BOARD.x + 0.025, y: 1.45, z: boardZ }, 'satin', false)
  batch.add(boxShape(0.08, 0.025, boardWidth, 0.008), '#aeb5bf', { x: BOARD.x + 0.06, y: 0.93, z: boardZ }, 'metal', false)
  for (const [dz, color] of [[-0.3, '#d1495b'], [-0.18, '#3f88c5'], [0.1, '#2a9d8f']] as const) {
    batch.add(cylinderShape(0.012, 0.012, 0.12, 8), color, { x: BOARD.x + 0.07, y: 0.955, z: boardZ + dz, rx: Math.PI / 2 }, 'satin', false)
  }

  // Meeting table on a round rug, with stools.
  batch.add(cylinderShape(1.32, 1.32, 0.015, 48), c.rug, { x: TABLE.x, y: 0.008, z: TABLE.z }, 'matte', false)
  batch.add(torusShape(1.25, 0.02, Math.PI * 2, 4, 48), theme.dark ? '#4a4057' : '#c9b8d3', { x: TABLE.x, y: 0.016, z: TABLE.z, rx: Math.PI / 2 }, 'matte', false)
  batch.add(cylinderShape(TABLE.radius, TABLE.radius, 0.05, 40), c.deskTop, { x: TABLE.x, y: 0.61, z: TABLE.z }, 'satin')
  batch.add(cylinderShape(TABLE.radius - 0.02, TABLE.radius - 0.08, 0.04, 40), c.deskFrame, { x: TABLE.x, y: 0.57, z: TABLE.z }, 'metal', false)
  batch.add(cylinderShape(0.06, 0.06, 0.52, 14), '#5d6470', { x: TABLE.x, y: 0.31, z: TABLE.z }, 'metal')
  batch.add(cylinderShape(0.32, 0.36, 0.04, 28), '#3a3f4b', { x: TABLE.x, y: 0.03, z: TABLE.z }, 'metal')
  for (const place of TABLE_PLACES) {
    batch.add(cylinderShape(0.2, 0.2, 0.07, 20), c.seat, { x: place.x, y: 0.29, z: place.z }, 'matte')
    batch.add(cylinderShape(0.025, 0.025, 0.24, 8), '#5d6470', { x: place.x, y: 0.14, z: place.z }, 'metal', false)
    batch.add(cylinderShape(0.15, 0.17, 0.025, 18), '#3a3f4b', { x: place.x, y: 0.013, z: place.z }, 'metal', false)
  }

  // Server rack and console in the back-right corner.
  const rackX = (RACK.x0 + RACK.x1) / 2
  const rackZ = (RACK.z0 + RACK.z1) / 2
  batch.add(boxShape(RACK.x1 - RACK.x0, 2.0, RACK.z1 - RACK.z0, 0.02), '#23262e', { x: rackX, y: 1.0, z: rackZ }, 'satin')
  batch.add(boxShape(0.02, 1.86, RACK.z1 - RACK.z0 - 0.08), '#30343e', { x: RACK.x0 - 0.002, y: 1.0, z: rackZ }, 'satin', false)
  for (let slot = 0; slot < 7; slot += 1) batch.add(boxShape(0.012, 0.012, RACK.z1 - RACK.z0 - 0.16), '#16181d', { x: RACK.x0 - 0.012, y: 0.3 + slot * 0.22, z: rackZ }, 'matte', false)
  const consoleX = (CONSOLE.x0 + CONSOLE.x1) / 2
  const consoleZ = (CONSOLE.z0 + CONSOLE.z1) / 2
  batch.add(boxShape(CONSOLE.x1 - CONSOLE.x0, 0.05, CONSOLE.z1 - CONSOLE.z0, 0.012), '#5d6470', { x: consoleX, y: 0.9, z: consoleZ }, 'metal')
  batch.add(boxShape(0.06, 0.88, 0.06), '#3a3f4b', { x: consoleX, y: 0.44, z: consoleZ }, 'metal')
  batch.add(boxShape(0.4, 0.03, 0.5, 0.01), '#3a3f4b', { x: consoleX, y: 0.015, z: consoleZ }, 'metal', false)
  for (const z of [-2.75, -2.05]) {
    batch.add(boxShape(0.04, 0.42, 0.62, 0.012), '#1d2027', { x: CONSOLE.x1 - 0.12, y: 1.2, z }, 'satin')
    batch.add(boxShape(0.01, 0.34, 0.54), theme.dark ? '#1f6f5a' : '#2f8f74', { x: CONSOLE.x1 - 0.145, y: 1.2, z }, 'glow', false)
    for (let line = 0; line < 4; line += 1) batch.add(boxShape(0.004, 0.02, 0.18 + (line % 2) * 0.14), '#8af0c8', { x: CONSOLE.x1 - 0.152, y: 1.3 - line * 0.07, z: z - 0.12 + (line % 2) * 0.07 }, 'glow', false)
  }

  // Lounge: a rug, the sofa with cushions, a floor lamp, the coffee counter and a water cooler.
  const sofaX = (SOFA.x0 + SOFA.x1) / 2
  const sofaZ = (SOFA.z0 + SOFA.z1) / 2
  const sofaLength = SOFA.z1 - SOFA.z0
  batch.add(boxShape(1.9, 0.012, 2.5, 0.004), c.rugLounge, { x: -4.6, y: 0.007, z: sofaZ }, 'matte', false)
  batch.add(boxShape(SOFA.x1 - SOFA.x0, 0.2, sofaLength, 0.05), c.sofa, { x: sofaX, y: 0.14, z: sofaZ })
  batch.add(boxShape(0.2, 0.55, sofaLength, 0.06), c.sofa, { x: SOFA.x0 + 0.1, y: 0.42, z: sofaZ })
  for (const z of [SOFA.z0 + 0.08, SOFA.z1 - 0.08]) batch.add(boxShape(SOFA.x1 - SOFA.x0, 0.36, 0.16, 0.06), c.sofa, { x: sofaX, y: 0.3, z })
  for (const z of [sofaZ - sofaLength / 4 + 0.04, sofaZ + sofaLength / 4 - 0.04]) {
    batch.add(boxShape(SOFA.x1 - SOFA.x0 - 0.24, 0.09, sofaLength / 2 - 0.14, 0.04), c.cushion, { x: sofaX + 0.1, y: 0.29, z })
    batch.add(boxShape(0.14, 0.34, sofaLength / 2 - 0.16, 0.05), c.cushion, { x: SOFA.x0 + 0.26, y: 0.52, z, rz: -0.18 })
  }
  batch.add(boxShape(0.1, 0.22, 0.22, 0.05), theme.accent, { x: SOFA.x0 + 0.36, y: 0.45, z: SOFA.z1 - 0.32, rz: -0.25, ry: 0.3 }, 'matte')
  batch.add(cylinderShape(0.14, 0.16, 0.025, 18), '#2a2d35', { x: -5.62, y: 0.013, z: 4.28 }, 'metal', false)
  batch.add(cylinderShape(0.015, 0.015, 1.5, 8), '#5d6470', { x: -5.62, y: 0.76, z: 4.28 }, 'metal')
  batch.add(cylinderShape(0.14, 0.2, 0.26, 20, ), c.lampShade, { x: -5.62, y: 1.58, z: 4.28 }, theme.dark ? 'glow' : 'satin', false)
  const counterX = (COUNTER.x0 + COUNTER.x1) / 2
  const counterZ = (COUNTER.z0 + COUNTER.z1) / 2
  const counterWidth = COUNTER.x1 - COUNTER.x0
  batch.add(boxShape(counterWidth, 0.84, COUNTER.z1 - COUNTER.z0, 0.02), c.counter, { x: counterX, y: 0.42, z: counterZ })
  for (const dx of [-counterWidth / 4, counterWidth / 4]) {
    batch.add(boxShape(counterWidth / 2 - 0.06, 0.72, 0.01), c.woodLight, { x: counterX + dx, y: 0.44, z: COUNTER.z0 - 0.003 }, 'satin', false)
    batch.add(boxShape(0.1, 0.015, 0.02), '#aeb5bf', { x: counterX + dx, y: 0.7, z: COUNTER.z0 - 0.015 }, 'metal', false)
  }
  batch.add(boxShape(counterWidth + 0.06, 0.04, COUNTER.z1 - COUNTER.z0 + 0.06, 0.012), c.top, { x: counterX, y: 0.86, z: counterZ }, 'satin')
  batch.add(boxShape(0.3, 0.36, 0.26, 0.03), '#2b2e36', { x: counterX - 0.25, y: 1.06, z: counterZ }, 'metal')
  batch.add(boxShape(0.22, 0.02, 0.12, 0.006), '#5d6470', { x: counterX - 0.25, y: 0.89, z: counterZ - 0.08 }, 'metal', false)
  batch.add(boxShape(0.04, 0.04, 0.01), '#ff6b4a', { x: counterX - 0.25, y: 1.16, z: counterZ - 0.135 }, 'glow', false)
  for (const dx of [0.18, 0.32]) batch.add(cylinderShape(0.045, 0.04, 0.1, 14), '#fbfaf7', { x: counterX + dx, y: 0.93, z: counterZ }, 'satin', false)
  batch.add(boxShape(0.36, 0.8, 0.36, 0.04), c.cooler, { x: COOLER.x, y: 0.4, z: COOLER.z }, 'satin')
  batch.add(boxShape(0.08, 0.05, 0.05), '#3f88c5', { x: COOLER.x - 0.19, y: 0.62, z: COOLER.z }, 'satin', false)
  batch.add(cylinderShape(0.15, 0.15, 0.4, 20), '#8fc9ff', { x: COOLER.x, y: 1.0, z: COOLER.z }, 'glass', false)
  batch.add(cylinderShape(0.05, 0.05, 0.05, 12), '#3f88c5', { x: COOLER.x, y: 1.22, z: COOLER.z }, 'satin', false)

  // Plants: a pot with soil and a full crown; two are tall plants on a stem.
  for (const [index, plant] of PLANTS.entries()) {
    batch.add(cylinderShape(0.21, 0.15, 0.38, 18), c.pot, { x: plant.x, y: 0.19, z: plant.z }, 'satin')
    batch.add(torusShape(0.205, 0.02, Math.PI * 2, 6, 18), c.pot, { x: plant.x, y: 0.38, z: plant.z, rx: Math.PI / 2 }, 'satin', false)
    batch.add(cylinderShape(0.19, 0.19, 0.02, 16), c.soil, { x: plant.x, y: 0.36, z: plant.z }, 'matte', false)
    const tall = index % 2 === 1
    if (tall) batch.add(cylinderShape(0.02, 0.025, 0.7, 6), '#5b4636', { x: plant.x, y: 0.7, z: plant.z }, 'matte')
    const base = tall ? 1.05 : 0.58
    const leaves: Array<[number, number, number, number, string]> = [
      [0, 0, 0, 0.3, c.leaf], [0.14, 0.12, 0.05, 0.2, c.leafLight], [-0.12, 0.16, -0.06, 0.18, c.leafLight],
      [0.02, 0.3, 0.02, 0.17, c.leaf], [-0.05, 0.06, 0.15, 0.16, c.leafLight],
    ]
    for (const [dx, dy, dz, r, color] of leaves) {
      batch.add(dodecaShape(r * (tall ? 0.9 : 1)), color, { x: plant.x + dx, y: base + dy, z: plant.z + dz, ry: dx * 7 }, 'matte')
    }
  }
  return batch
}

export function createRoomKit(theme: RoomTheme, finishes: Finishes): RoomKit {
  const furniture = furnish(theme).build()
  const texture = floorTexture(theme.dark)
  const width = ROOM.x1 - ROOM.x0
  const depth = ROOM.z1 - ROOM.z0
  const floorGeometry = new THREE.BoxGeometry(width, 0.24, depth)
  floorGeometry.translate(0, -0.12, 0)
  const floorMaterial = new THREE.MeshStandardMaterial({ map: texture, roughness: 0.82 })
  // The rack's status lights, in two sets that blink in turn.
  const ledColors = ['#38d39f', '#4aa3ff', '#f2c230']
  const sets = [new Batch(), new Batch()] as const
  for (let row = 0; row < 7; row += 1) {
    for (let column = 0; column < 3; column += 1) {
      sets[(row + column) % 2]!.add(boxShape(0.012, 0.035, 0.06), ledColors[column]!, { x: RACK.x0 - 0.016, y: 0.36 + row * 0.22, z: RACK.z0 + 0.2 + column * 0.25 }, 'glow', false)
    }
  }
  const leds = sets.map((set) => set.build()[0]!.geometry) as [THREE.BufferGeometry, THREE.BufferGeometry]
  const hour = boxShape(0.03, 0.14, 0.01).clone().translate(0, 0.06, 0)
  const minute = boxShape(0.02, 0.21, 0.01).clone().translate(0, 0.095, 0)
  const handMaterial = new THREE.MeshStandardMaterial({ color: '#25252a', roughness: 0.5 })
  return {
    theme,
    finishes,
    furniture,
    floor: { geometry: floorGeometry, material: floorMaterial, texture },
    leds,
    hands: { hour, minute, material: handMaterial },
    dispose() {
      for (const part of furniture) part.geometry.dispose()
      floorGeometry.dispose()
      floorMaterial.dispose()
      texture.dispose()
      for (const geometry of leds) geometry.dispose()
      hour.dispose()
      minute.dispose()
      handMaterial.dispose()
    },
  }
}

/** One floor's room: the kit's shared furniture, and the parts this floor animates. */
export function buildRoom(kit: RoomKit): Room {
  const { theme, finishes } = kit
  const group = new THREE.Group()
  for (const mesh of meshesOf(kit.furniture, finishes)) group.add(mesh)
  const floor = new THREE.Mesh(kit.floor.geometry, kit.floor.material)
  floor.receiveShadow = true
  floor.matrixAutoUpdate = false
  group.add(floor)
  const owned: THREE.Material[] = []

  const screens: THREE.MeshStandardMaterial[] = []
  for (let index = 0; index < DESK_X_COUNT; index += 1) {
    const { x, z } = deskCenter(index)
    const screen = new THREE.MeshStandardMaterial({ color: '#0e1420', emissive: '#203048', emissiveIntensity: 0.35, roughness: 0.3 })
    screens.push(screen)
    owned.push(screen)
    const mesh = new THREE.Mesh(SCREEN, screen)
    mesh.position.set(x, 1.0, z + 0.18)
    group.add(mesh)
  }

  const notes = new THREE.Group()
  notes.position.set(BOARD.x + 0.04, 1.45, (BOARD.z0 + BOARD.z1) / 2)
  group.add(notes)

  const ringMaterial = new THREE.MeshStandardMaterial({ color: theme.accent, emissive: theme.accent, emissiveIntensity: 1.4, transparent: true, opacity: 0.85 })
  owned.push(ringMaterial)
  const ring = new THREE.Mesh(RING, ringMaterial)
  ring.position.set(TABLE.x, 0.95, TABLE.z)
  ring.rotation.x = Math.PI / 2
  ring.visible = false
  group.add(ring)

  const leds = kit.leds.map((geometry) => {
    const material = new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false })
    owned.push(material)
    group.add(new THREE.Mesh(geometry, material))
    return material
  })

  const hour = new THREE.Mesh(kit.hands.hour, kit.hands.material)
  const minute = new THREE.Mesh(kit.hands.minute, kit.hands.material)
  hour.position.set(3.6, 1.85, ROOM.z0 + 0.08)
  minute.position.set(3.6, 1.85, ROOM.z0 + 0.09)
  group.add(hour, minute)

  // Warm lamps at night: over the desks, by the sofa and over the table.
  const lamps: THREE.PointLight[] = []
  if (theme.dark) {
    for (const [x, y, z] of [[0, 2.1, -1.8], [-5.3, 1.6, 4.0], [1.6, 2.0, 1.5]] as const) {
      const lamp = new THREE.PointLight('#ffcf8a', 9, 9, 1.4)
      lamp.position.set(x, y, z)
      group.add(lamp)
      lamps.push(lamp)
    }
  }

  return {
    group,
    screens,
    notes,
    ring,
    leds,
    clock: { hour, minute },
    lamps,
    dispose() {
      group.removeFromParent()
      for (const note of notes.children) ((note as THREE.Mesh).material as THREE.Material).dispose()
      for (const material of owned) material.dispose()
      for (const lamp of lamps) lamp.dispose()
    },
  }
}

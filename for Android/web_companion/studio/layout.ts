/**
 * The studio's floor plan in metres: x to the right, z toward the viewer, the floor at y = 0.
 * The back wall is at z = -4.5 and the left wall at x = -6; the room is open on the viewer's sides.
 */

export interface Point { x: number; z: number }
/** Where someone stands or sits, and the point they face. */
export interface Place extends Point { face: Point; sit: boolean }
export interface Box { x0: number; x1: number; z0: number; z1: number }

export const ROOM = { x0: -6, x1: 6, z0: -4.5, z1: 4.5, height: 2.6 } as const

const DESK_X = [0, -1.8, 1.8, -3.6, 3.6] as const
export const DESK_X_COUNT = DESK_X.length
export const DESK_Z = -2.2
export const DESK_SIZE = { width: 1.2, depth: 0.7 } as const
export const SEAT_Z = -2.95

/** Desk 0 is the lead's; experts take the next ones in the team's order. */
export function deskCenter(index: number): Point {
  return { x: DESK_X[index % DESK_X.length]!, z: DESK_Z }
}

export function deskSeat(index: number): Place {
  const { x } = deskCenter(index)
  return { x, z: SEAT_Z, face: { x, z: DESK_Z + 2 }, sit: true }
}

export const SHELF: Box = { x0: -6, x1: -5.6, z0: -2.0, z1: -0.2 }
export const SHELF_PLACES: readonly Place[] = [-1.6, -1.1, -0.6].map((z) => ({ x: -5.15, z, face: { x: -7, z }, sit: false }))

export const BOARD = { x: -5.92, z0: 0.4, z1: 1.9 } as const
export const BOARD_PLACE: Place = { x: -5.0, z: 1.15, face: { x: -7, z: 1.15 }, sit: false }

export const RACK: Box = { x0: 5.25, x1: 5.9, z0: -4.3, z1: -3.3 }
export const CONSOLE: Box = { x0: 5.35, x1: 5.9, z0: -3.1, z1: -1.7 }
export const TERMINAL_PLACES: readonly Place[] = [-2.75, -2.05].map((z) => ({ x: 4.95, z, face: { x: 7, z }, sit: false }))

export const TABLE = { x: 1.6, z: 1.5, radius: 0.85 } as const
export const TABLE_PLACES: readonly Place[] = Array.from({ length: 6 }, (_, index) => {
  const angle = (index / 6) * Math.PI * 2 + Math.PI / 6
  return {
    x: TABLE.x + Math.cos(angle) * 1.4,
    z: TABLE.z + Math.sin(angle) * 1.4,
    face: { x: TABLE.x, z: TABLE.z },
    sit: true,
  }
})

export const SOFA: Box = { x0: -5.75, x1: -5.05, z0: 2.3, z1: 4.1 }
export const SOFA_PLACES: readonly Place[] = [2.8, 3.6].map((z) => ({ x: -4.8, z, face: { x: 0, z }, sit: true }))
export const COUNTER: Box = { x0: -3.3, x1: -1.9, z0: 3.95, z1: 4.45 }
export const COFFEE_PLACE: Place = { x: -2.6, z: 3.35, face: { x: -2.6, z: 6 }, sit: false }
export const COOLER: Point = { x: 5.1, z: 3.3 }
export const COOLER_PLACE: Place = { x: 4.5, z: 3.3, face: { x: 7, z: 3.3 }, sit: false }
export const PLANTS: readonly Point[] = [{ x: -5.5, z: -4.0 }, { x: 5.45, z: 4.05 }, { x: -0.6, z: 4.1 }, { x: 4.6, z: -4.05 }]

/** Places an idle person may wander to. */
export const IDLE_PLACES: readonly Place[] = [COFFEE_PLACE, COOLER_PLACE, ...SOFA_PLACES]

/** What people walk around. */
export function obstacles(): Box[] {
  const desks = DESK_X.map((_, index) => {
    const { x, z } = deskCenter(index)
    return { x0: x - DESK_SIZE.width / 2, x1: x + DESK_SIZE.width / 2, z0: z - DESK_SIZE.depth / 2, z1: z + DESK_SIZE.depth / 2 }
  })
  const plants = PLANTS.map(({ x, z }) => ({ x0: x - 0.25, x1: x + 0.25, z0: z - 0.25, z1: z + 0.25 }))
  return [
    ...desks,
    SHELF,
    RACK,
    CONSOLE,
    { x0: TABLE.x - TABLE.radius, x1: TABLE.x + TABLE.radius, z0: TABLE.z - TABLE.radius, z1: TABLE.z + TABLE.radius },
    SOFA,
    COUNTER,
    { x0: COOLER.x - 0.2, x1: COOLER.x + 0.2, z0: COOLER.z - 0.2, z1: COOLER.z + 0.2 },
    ...plants,
  ]
}

import * as THREE from 'three'

import { Batch, boxShape, coneShape, cylinderShape, dodecaShape, sphereShape, torusShape } from '../mesh-kit'
import type { PlaceId } from './models'
import { disposeGeometry, floor, group, palette } from './kit'
import type { PlaceBuilder, PlaceLabel, Vec } from './stage'
import type { PlaceInput } from './types'

/**
 * The campus: the studio's building in the middle, the library, the building site, the duty room
 * and the front desk around it on one lawn (the phone has no server room: trees stand in its corner). Where something is going on, the
 * windows are lit; the signs say what. A click on a building (or its sign) goes in.
 */

export type CampusPlace = Exclude<PlaceId, 'campus'>

export interface CampusSpot {
  busy: boolean
  alert: boolean
  detail: string
}

export interface CampusModel {
  spots: Record<CampusPlace, CampusSpot>
  /** The studio's floors: conversations whose team is at work (at least one). */
  floors: number
}

const GROUND = { x0: -14, x1: 14, z0: -10, z1: 11 }
const SPOTS: Record<CampusPlace, { x: number; z: number; top: number }> = {
  studio: { x: 0, z: -5.5, top: 0 },
  library: { x: -9, z: -4.5, top: 3.3 },
  site: { x: 9, z: -4.5, top: 2.6 },
  duty: { x: 9, z: 4.5, top: 4.4 },
  desk: { x: 0, z: 7.5, top: 2.9 },
}
const STOREY = 1.15

export const buildCampus: PlaceBuilder<PlaceInput<CampusModel>> = (context) => {
  const { root, finishes, options, still } = context
  const dark = options.dark
  const c = palette(dark)
  const lawn = floor('lawn', dark, GROUND, 6)
  root.add(lawn.mesh)

  const batch = new Batch()
  const stone = dark ? '#5d5a56' : '#e4ded4'
  // Paths from the plaza to every door, and the plaza.
  batch.add(cylinderShape(3.2, 3.2, 0.04, 40), stone, { y: 0.02 }, 'matte', false)
  for (const spot of Object.values(SPOTS)) {
    const length = Math.hypot(spot.x, spot.z)
    batch.add(boxShape(1.1, 0.035, length), stone, { x: spot.x / 2, y: 0.018, z: spot.z / 2, ry: Math.atan2(spot.x, spot.z) }, 'matte', false)
  }
  batch.add(cylinderShape(0.9, 1.0, 0.3, 24), dark ? '#6f6b66' : '#cfc8bc', { y: 0.15 }, 'satin')
  batch.add(cylinderShape(0.75, 0.75, 0.04, 24), dark ? '#2d4f73' : '#7fb6d6', { y: 0.3 }, 'glass', false)
  // Street lamps around the plaza.
  for (const [x, z] of [[-3.5, -2.5], [3.5, -2.5], [-3.5, 3.0], [3.5, 3.0]] as const) {
    batch.add(cylinderShape(0.05, 0.07, 2.5, 8), c.metal, { x, y: 1.25, z }, 'metal')
    batch.add(sphereShape(0.16, 10, 8), '#ffe2a8', { x, y: 2.6, z }, dark ? 'glow' : 'satin', false)
  }
  // Trees around the lawn.
  for (const [x, z, s] of [[-13, -8.5, 1], [-5, -9, 0.8], [5, -9, 0.9], [13, -8.5, 1], [-13, 0, 0.9], [13, 0, 1], [-12.5, 9.5, 1], [-5, 10, 0.8], [5, 10, 0.9], [12.5, 9.5, 1], [-4.5, 2.2, 0.7], [4.5, 2.2, 0.7], [-10, 3.6, 1.1], [-7.8, 5.4, 0.85], [-10.6, 6.2, 0.9]] as const) {
    batch.add(cylinderShape(0.08 * s, 0.11 * s, 0.9 * s, 8), '#5b4636', { x, y: 0.45 * s, z }, 'matte')
    batch.add(dodecaShape(0.6 * s), c.leaf, { x, y: 1.15 * s, z }, 'matte')
    batch.add(dodecaShape(0.42 * s), c.leafLight, { x: x + 0.25 * s, y: 1.45 * s, z: z - 0.1 }, 'matte')
  }

  const wall = dark ? '#5a6274' : '#efe9df'
  const roof = dark ? '#3a3f4b' : '#b8b2a8'
  const glass = dark ? '#1d2e5c' : '#9fc9e6'
  // The library: steps, columns, a pediment.
  {
    const { x, z } = SPOTS.library
    batch.add(boxShape(5.2, 0.3, 3.6, 0.03), stone, { x, y: 0.15, z }, 'matte')
    batch.add(boxShape(4.6, 2.2, 2.8, 0.03), wall, { x, y: 1.4, z: z - 0.2 }, 'satin')
    for (let index = 0; index < 6; index += 1) batch.add(cylinderShape(0.13, 0.15, 2.2, 12), stone, { x: x - 2.0 + index * 0.8, y: 1.4, z: z + 1.45 }, 'satin')
    batch.add(boxShape(5.0, 0.25, 3.3, 0.02), stone, { x, y: 2.62, z }, 'satin')
    batch.add(coneShape(2.9, 0.75, 4), roof, { x, y: 3.1, z, ry: Math.PI / 4, sz: 0.62 }, 'satin')
  }
  // The building site: a fence, small buildings, a crane.
  {
    const { x, z } = SPOTS.site
    batch.add(boxShape(5.0, 0.03, 4.2), dark ? '#5a4a3a' : '#c8b08a', { x, y: 0.02, z }, 'matte', false)
    for (const [dx, dz, w, d] of [[0, -2.1, 5.0, 0.04], [0, 2.1, 5.0, 0.04], [-2.5, 0, 0.04, 4.2], [2.5, 0, 0.04, 4.2]] as const) batch.add(boxShape(w, 0.8, d), dark ? '#3c4c5e' : '#7d97b0', { x: x + dx, y: 0.4, z: z + dz }, 'glass', false)
    for (const [dx, dz, h, colour] of [[-1.5, -0.8, 1.2, '#5b7db1'], [-0.7, -0.9, 0.8, '#4f8a5b'], [-1.4, 0.6, 0.6, '#e3dccb'], [-0.5, 0.5, 1.5, '#5b7db1'], [0.4, 0.9, 0.5, '#9aa1ab']] as const) {
      batch.add(boxShape(0.6, h, 0.6, 0.02), colour, { x: x + dx, y: h / 2, z: z + dz }, 'satin')
    }
    batch.add(boxShape(0.14, 3.6, 0.14), '#e0a13a', { x: x + 1.6, y: 1.8, z: z - 1.2 }, 'metal')
    batch.add(boxShape(4.0, 0.12, 0.14), '#e0a13a', { x: x + 0.4, y: 3.6, z: z - 1.2 }, 'metal')
    batch.add(cylinderShape(0.01, 0.01, 1.4, 4), '#2a2d35', { x: x - 1.2, y: 2.9, z: z - 1.2 }, 'metal', false)
  }
  // The duty room: a house with a clock tower.
  {
    const { x, z } = SPOTS.duty
    batch.add(boxShape(3.8, 1.8, 3.0, 0.04), wall, { x, y: 0.9, z }, 'satin')
    batch.add(coneShape(2.8, 1.0, 4), roof, { x, y: 2.3, z, ry: Math.PI / 4, sz: 0.8 }, 'satin')
    batch.add(boxShape(1.0, 3.6, 1.0, 0.03), wall, { x: x + 1.2, y: 1.8, z: z + 0.6 }, 'satin')
    batch.add(coneShape(0.8, 0.8, 4), roof, { x: x + 1.2, y: 4.0, z: z + 0.6, ry: Math.PI / 4 }, 'satin')
    batch.add(cylinderShape(0.38, 0.38, 0.04, 24), '#fbfaf7', { x: x + 1.2, y: 3.0, z: z + 1.11, rx: Math.PI / 2 }, 'satin', false)
    batch.add(torusShape(0.38, 0.03, Math.PI * 2, 6, 24), '#3b3b40', { x: x + 1.2, y: 3.0, z: z + 1.13 }, 'metal', false)
    batch.add(boxShape(0.6, 1.2, 0.04), c.wood, { x: x - 0.5, y: 0.6, z: z + 1.51 }, 'satin', false)
  }
  // The front desk: a gatehouse with a mast.
  {
    const { x, z } = SPOTS.desk
    batch.add(boxShape(4.0, 1.7, 2.4, 0.04), wall, { x, y: 0.85, z }, 'satin')
    batch.add(boxShape(4.4, 0.14, 2.8, 0.03), roof, { x, y: 1.77, z: z + 0.1 }, 'satin')
    batch.add(boxShape(1.6, 1.3, 0.04), glass, { x: x + 0.8, y: 0.75, z: z + 1.21 }, 'glass', false)
    batch.add(cylinderShape(0.04, 0.06, 1.8, 8), c.metal, { x: x - 1.5, y: 2.7, z }, 'metal')
  }
  // The studio: a plinth; its floors are added by the model.
  batch.add(boxShape(4.8, 0.35, 4.8, 0.04), stone, { x: SPOTS.studio.x, y: 0.17, z: SPOTS.studio.z }, 'matte')
  root.add(group(batch, finishes))

  // What changes with the model: the studio's floors, the lit windows, the beacons.
  const tower = new THREE.Group()
  root.add(tower)
  const lights = new Map<CampusPlace, THREE.MeshBasicMaterial>()
  const windows = (place: CampusPlace, parts: Array<[number, number, number, number, number, number]>): void => {
    const material = new THREE.MeshBasicMaterial({ color: c.dim, toneMapped: false })
    lights.set(place, material)
    const geometry = new THREE.BoxGeometry(1, 1, 1)
    for (const [x, y, z, w, h, d] of parts) {
      const mesh = new THREE.Mesh(geometry, material)
      mesh.position.set(x, y, z)
      mesh.scale.set(w, h, d)
      root.add(mesh)
    }
  }
  const at = SPOTS
  windows('library', [[at.library.x - 1.2, 1.5, at.library.z + 1.21, 0.7, 1.0, 0.03], [at.library.x, 1.5, at.library.z + 1.21, 0.7, 1.0, 0.03], [at.library.x + 1.2, 1.5, at.library.z + 1.21, 0.7, 1.0, 0.03]])
  windows('site', [[at.site.x + 0.4, 3.75, at.site.z - 1.2, 0.18, 0.18, 0.18]])
  windows('duty', [[at.duty.x - 0.5, 1.2, at.duty.z + 1.52, 0.9, 0.6, 0.03], [at.duty.x + 0.9, 1.0, at.duty.z - 1.52, 0.9, 0.6, 0.03]])
  windows('desk', [[at.desk.x - 1.0, 1.0, at.desk.z + 1.22, 1.0, 0.6, 0.03], [at.desk.x - 1.5, 3.65, at.desk.z, 0.12, 0.12, 0.12]])
  const studioLight = new THREE.MeshBasicMaterial({ color: c.dim, toneMapped: false })
  lights.set('studio', studioLight)

  const hands = new THREE.MeshStandardMaterial({ color: '#25252a', roughness: 0.5 })
  const hour = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.22, 0.01).translate(0, 0.1, 0), hands)
  const minute = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.32, 0.01).translate(0, 0.15, 0), hands)
  hour.position.set(at.duty.x + 1.2, 3.0, at.duty.z + 1.16)
  minute.position.set(at.duty.x + 1.2, 3.0, at.duty.z + 1.17)
  root.add(hour, minute)

  // Each building is picked as a whole.
  const hitMaterial = new THREE.MeshBasicMaterial({ visible: false })
  for (const [place, spot] of Object.entries(SPOTS) as Array<[CampusPlace, typeof SPOTS[CampusPlace]]>) {
    const hit = new THREE.Mesh(new THREE.BoxGeometry(5.2, place === 'studio' ? 8 : spot.top + 0.4, 4.2), hitMaterial)
    hit.position.set(spot.x, (place === 'studio' ? 8 : spot.top + 0.4) / 2, spot.z)
    root.add(hit)
    context.pickable(hit, `place:${place}`)
  }

  let floors = 0
  let state: CampusModel | null = null
  const raise = (count: number): void => {
    if (count === floors) return
    floors = count
    for (const child of [...tower.children]) {
      child.removeFromParent()
      if (child instanceof THREE.Mesh && child.material === studioLight) child.geometry.dispose()
      else disposeGeometry(child)
    }
    const building = new Batch()
    const { x, z } = at.studio
    for (let level = 0; level < count; level += 1) {
      const y = 0.35 + level * STOREY
      building.add(boxShape(4.0, STOREY - 0.08, 4.0, 0.03), wall, { x, y: y + STOREY / 2, z }, 'satin')
      building.add(boxShape(4.1, 0.08, 4.1, 0.02), c.trim, { x, y: y + STOREY - 0.04, z }, 'satin', false)
    }
    building.add(boxShape(4.3, 0.2, 4.3, 0.03), roof, { x, y: 0.35 + count * STOREY + 0.1, z }, 'satin')
    building.add(cylinderShape(0.04, 0.05, 1.2, 8), c.metal, { x: x + 1.5, y: 0.35 + count * STOREY + 0.8, z: z - 1.5 }, 'metal')
    tower.add(group(building, finishes))
    // A band of windows on each floor's two visible sides.
    const geometry = new THREE.BoxGeometry(1, 1, 1)
    for (let level = 0; level < count; level += 1) {
      const y = 0.35 + level * STOREY + STOREY / 2
      for (const [px, pz, w, d] of [[x, z + 2.01, 3.4, 0.03], [x + 2.01, z, 0.03, 3.4]] as const) {
        const mesh = new THREE.Mesh(geometry, studioLight)
        mesh.position.set(px, y, pz)
        mesh.scale.set(w, 0.45, d)
        mesh.userData.level = level
        tower.add(mesh)
      }
    }
  }
  raise(1)

  const top = (place: CampusPlace): number => (place === 'studio' ? 0.35 + floors * STOREY + 1.0 : at[place].top + 0.5)
  return {
    frame: { min: { x: -12.5, y: 0, z: -8.5 }, max: { x: 12.5, y: 4.0, z: 9.5 }, polar: 0.95, azimuth: 0.55 },
    // Street lamps around the plaza.
    lamps: [{ x: -3.5, y: 2.6, z: -2.5 }, { x: 3.5, y: 2.6, z: -2.5 }, { x: -3.5, y: 2.6, z: 3.0 }, { x: 3.5, y: 2.6, z: 3.0 }],
    update({ model, t }) {
      state = model
      raise(Math.max(1, Math.min(6, model.floors)))
      const labels: Record<string, PlaceLabel> = {}
      for (const place of Object.keys(SPOTS) as CampusPlace[]) {
        const spot = model.spots[place]
        labels[place] = {
          at: { x: at[place].x, y: top(place), z: at[place].z },
          title: t(`places.${place}.title`),
          detail: spot.detail,
          ...(spot.alert ? { tone: 'alert' as const } : spot.busy ? { tone: 'busy' as const } : {}),
          pick: `place:${place}`,
        }
      }
      return { people: [], labels }
    },
    tick(now) {
      const time = new Date()
      minute.rotation.z = -((time.getMinutes() + time.getSeconds() / 60) / 60) * Math.PI * 2
      hour.rotation.z = -(((time.getHours() % 12) + time.getMinutes() / 60) / 12) * Math.PI * 2
      for (const [place, material] of lights) {
        const spot = state?.spots[place]
        const pulse = still ? 1 : 0.85 + Math.sin(now * (place === 'site' || place === 'desk' ? 5 : 1.5)) * 0.15
        if (spot?.alert) material.color.set('#f2b33d').multiplyScalar(pulse)
        else if (spot?.busy) material.color.set(dark ? '#ffd27a' : '#ffcf6a').multiplyScalar(pulse)
        else material.color.set(dark ? '#2a3550' : '#7d8ea3')
      }
      return false
    },
    target(id): Vec | null {
      const place = id.startsWith('place:') ? id.slice(6) as CampusPlace : null
      if (!place || !(place in SPOTS)) return null
      return { x: at[place].x, y: place === 'studio' ? 1.6 : 1.0, z: at[place].z }
    },
    dispose() {
      lawn.dispose()
      for (const child of [...root.children]) disposeGeometry(child)
      for (const material of lights.values()) material.dispose()
      hands.dispose()
      hitMaterial.dispose()
    },
  }
}

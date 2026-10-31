import * as THREE from 'three'

import { lookFor } from '../cast'
import type { Place } from '../layout'
import { Batch, boxShape, cylinderShape, torusShape } from '../mesh-kit'
import { FloorGrid } from '../paths'
import type { Action } from '../person'
import { DUTY_DESKS, type DutyModel, type DutyOfficer } from './models'
import { ROOM_BOX, desk, floor, group, palette, plant, walls, disposeGeometry } from './kit'
import type { CrowdActor, PlaceBuilder, PlaceLabel } from './stage'
import type { PlaceInput } from './types'

/**
 * The duty room: one officer for each scheduled task, at their desk. They get up shortly before
 * their next run, work at the desk while it runs, slump over it when it failed and nobody has
 * looked, and leave their desk empty while the task is paused. The wall clock keeps the time;
 * the board beside it lists the next runs.
 */

const deskAt = (index: number): { x: number; z: number } => ({ x: -4.2 + (index % 4) * 2.8, z: index < 4 ? -1.5 : 1.6 })
const CLOCK = { x: -2.4, y: 1.75 }
const BOARD = { x: 2.2, width: 3.2 }
const seat = (index: number): Place => {
  const { x, z } = deskAt(index)
  return { x, z: z - 0.75, face: { x, z: z + 2 }, sit: true }
}
const standing = (index: number): Place => {
  const { x, z } = deskAt(index)
  return { x: x + 0.85, z: z - 0.6, face: { x: CLOCK.x, z: -9 }, sit: false }
}

const ACTIONS: Record<DutyOfficer['state'], Action> = { running: 'type', soon: 'rest', idle: 'rest', failed: 'slump', done: 'rest', off: 'rest' }

export const buildDuty: PlaceBuilder<PlaceInput<DutyModel>> = (context) => {
  const { root, finishes, options, still } = context
  const dark = options.dark
  const c = palette(dark)
  const slab = floor('carpet', dark, ROOM_BOX, 2)
  root.add(slab.mesh)

  const batch = new Batch()
  walls(batch, dark)
  // The wall clock: a big face with ticks; its hands move.
  batch.add(cylinderShape(0.55, 0.55, 0.05, 40), '#fbfaf7', { x: CLOCK.x, y: CLOCK.y, z: ROOM_BOX.z0 + 0.05, rx: Math.PI / 2 }, 'satin', false)
  batch.add(torusShape(0.55, 0.04, Math.PI * 2, 6, 40), '#3b3b40', { x: CLOCK.x, y: CLOCK.y, z: ROOM_BOX.z0 + 0.07 }, 'metal', false)
  for (let tick = 0; tick < 12; tick += 1) {
    const angle = (tick / 12) * Math.PI * 2
    batch.add(boxShape(0.03, tick % 3 === 0 ? 0.1 : 0.06, 0.01), '#3b3b40', { x: CLOCK.x + Math.sin(angle) * 0.44, y: CLOCK.y + Math.cos(angle) * 0.44, z: ROOM_BOX.z0 + 0.08, rz: -angle }, 'matte', false)
  }
  // The board of the next runs.
  batch.add(boxShape(BOARD.width + 0.08, 1.3, 0.04, 0.012), '#aeb5bf', { x: BOARD.x, y: 1.65, z: ROOM_BOX.z0 + 0.03 }, 'metal', false)
  batch.add(boxShape(BOARD.width, 1.2, 0.02), dark ? '#26303a' : '#fcfcfa', { x: BOARD.x, y: 1.65, z: ROOM_BOX.z0 + 0.055 }, 'satin', false)
  const deskScreens = Array.from({ length: DUTY_DESKS }, (_, index) => desk(batch, dark, deskAt(index).x, deskAt(index).z))
  // A coffee corner at the front left.
  batch.add(boxShape(1.2, 0.85, 0.5, 0.02), c.wood, { x: -5.0, y: 0.42, z: 3.9 }, 'satin')
  batch.add(boxShape(0.3, 0.36, 0.26, 0.03), '#2b2e36', { x: -5.2, y: 1.03, z: 3.9 }, 'metal')
  for (const dx of [0.1, 0.25]) batch.add(cylinderShape(0.045, 0.04, 0.1, 14), '#fbfaf7', { x: -5.0 + dx, y: 0.9, z: 3.9 }, 'satin', false)
  plant(batch, dark, 5.4, 3.9, true)
  plant(batch, dark, 5.5, -4.0)
  root.add(group(batch, finishes))

  const handMaterial = new THREE.MeshStandardMaterial({ color: '#25252a', roughness: 0.5 })
  const hourGeometry = new THREE.BoxGeometry(0.05, 0.3, 0.015).translate(0, 0.13, 0)
  const minuteGeometry = new THREE.BoxGeometry(0.035, 0.45, 0.015).translate(0, 0.2, 0)
  const hour = new THREE.Mesh(hourGeometry, handMaterial)
  const minute = new THREE.Mesh(minuteGeometry, handMaterial)
  hour.position.set(CLOCK.x, CLOCK.y, ROOM_BOX.z0 + 0.1)
  minute.position.set(CLOCK.x, CLOCK.y, ROOM_BOX.z0 + 0.11)
  root.add(hour, minute)

  const screens = deskScreens.map((at) => {
    const material = new THREE.MeshStandardMaterial({ color: '#0e1420', emissive: c.dim, emissiveIntensity: 0.3, roughness: 0.3 })
    const mesh = new THREE.Mesh(boxShape(0.58, 0.34, 0.008), material)
    mesh.userData.shared = true
    mesh.position.copy(at)
    root.add(mesh)
    return material
  })
  for (let index = 0; index < DUTY_DESKS; index += 1) {
    const hit = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.1, 1.5), new THREE.MeshBasicMaterial({ visible: false }))
    hit.position.set(deskAt(index).x, 0.55, deskAt(index).z - 0.35)
    root.add(hit)
    context.pickable(hit, 'route:schedules')
  }

  let officers: DutyOfficer[] = []
  return {
    frame: { min: { x: ROOM_BOX.x0, y: 0, z: ROOM_BOX.z0 }, max: { x: ROOM_BOX.x1, y: 2.4, z: ROOM_BOX.z1 }, polar: 0.98, azimuth: 0.62 },
    lamps: [{ x: -2.8, y: 2.2, z: -1.6 }, { x: 2.8, y: 2.2, z: -1.6 }, { x: -2.8, y: 2.2, z: 1.6 }, { x: 2.8, y: 2.2, z: 1.6 }],
    floor: {
      grid: new FloorGrid([
        ...Array.from({ length: DUTY_DESKS }, (_, index) => ({ x0: deskAt(index).x - 0.6, x1: deskAt(index).x + 0.6, z0: deskAt(index).z - 0.35, z1: deskAt(index).z + 0.35 })),
        { x0: -5.6, x1: -4.4, z0: 3.65, z1: 4.15 },
      ]),
      door: { x: 5.2, z: 4.2 },
    },
    update({ model, t }) {
      officers = model.officers
      const people: CrowdActor[] = officers.flatMap((officer, index): CrowdActor[] => {
        if (officer.state === 'off') return []
        return [{
          id: officer.id,
          name: officer.title || t('places.duty.untitled'),
          state: officer.state === 'running' ? 'working' : officer.state === 'failed' ? 'failed' : officer.state === 'done' ? 'done' : officer.state === 'soon' ? 'waiting' : 'idle',
          stateLabel: t(`places.duty.state.${officer.state}`),
          look: lookFor(`schedule:${officer.id}`),
          place: officer.state === 'soon' ? standing(index) : seat(index),
          action: ACTIONS[officer.state],
          ...(officer.state === 'failed' ? { bubble: '!' } : officer.state === 'done' ? { bubble: '✓' } : {}),
          pick: 'route:schedules',
        }]
      })
      const labels: Record<string, PlaceLabel> = {}
      officers.forEach((officer, index) => {
        if (officer.state !== 'off') return
        labels[`off-${officer.id}`] = { at: { x: deskAt(index).x, y: 1.3, z: deskAt(index).z }, title: officer.title || t('places.duty.untitled'), detail: t('places.duty.state.off'), pick: 'route:schedules' }
      })
      // The board: the next runs, one line each.
      model.upcoming.slice(0, 4).forEach((run, index) => {
        const at = new Date(run.at)
        const time = Number.isNaN(at.getTime()) ? run.at : at.toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })
        labels[`next-${run.id}`] = { at: { x: BOARD.x, y: 2.15 - index * 0.28, z: ROOM_BOX.z0 + 0.1 }, title: time, detail: run.title, pick: 'route:schedules' }
      })
      if (officers.length === 0) labels.empty = { at: { x: 0, y: 1.3, z: 0 }, title: t('places.duty.empty'), pick: 'route:schedules' }
      if (model.more > 0) labels.more = { at: { x: 4.6, y: 1.0, z: 3.2 }, title: t('places.duty.more', { count: model.more }) }
      return { people, labels }
    },
    tick(now) {
      const time = new Date()
      minute.rotation.z = -((time.getMinutes() + time.getSeconds() / 60) / 60) * Math.PI * 2
      hour.rotation.z = -(((time.getHours() % 12) + time.getMinutes() / 60) / 12) * Math.PI * 2
      screens.forEach((material, index) => {
        const officer = officers[index]
        const busy = officer?.state === 'running'
        material.emissive.set(busy ? (dark ? '#3d7bd9' : '#4b8fe6') : officer?.state === 'failed' ? '#8a2b24' : c.dim)
        material.emissiveIntensity = busy ? 0.9 + (still ? 0 : Math.sin(now * 7 + index) * 0.08) : officer && officer.state !== 'off' ? 0.45 : 0.15
      })
      return false
    },
    dispose() {
      slab.dispose()
      for (const child of [...root.children]) disposeGeometry(child)
      handMaterial.dispose()
      for (const material of screens) material.dispose()
      root.traverse((node) => { if (node instanceof THREE.Mesh && node.material instanceof THREE.MeshBasicMaterial && !node.material.visible) node.material.dispose() })
    },
  }
}

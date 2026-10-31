import * as THREE from 'three'

import { lookFor } from '../cast'
import type { Place } from '../layout'
import { Batch, boxShape, cylinderShape } from '../mesh-kit'
import { FloorGrid } from '../paths'
import type { DeskModel } from './models'
import { ROOM_BOX, disposeGeometry, floor, group, palette, plant, walls } from './kit'
import type { CrowdActor, PlaceBuilder, PlaceLabel } from './stage'
import type { PlaceInput } from './types'

/**
 * The front desk: on the phone, the link to the paired computers. Behind the counter sits the
 * receptionist; the badge board lists the computers. One that is reachable waits on the bench; one
 * with something going on (a request for this phone, an approval) stands at the counter. Tasks this
 * phone handed to a computer wait as parcels on the counter. (Kept in step with the desktop app's
 * places/desk.ts, whose visitors are phones.)
 */

const COUNTER = { x: 0, z: -2.3, width: 3.4 }
const BENCH = { x: -3.6, z: 2.6 }
const BOARD = { z: -1.0, length: 3.2 }
const DOOR = { x: 4.6, z: 4.4 }
const RECEPTION: Place = { x: COUNTER.x, z: COUNTER.z - 0.75, face: { x: COUNTER.x, z: 6 }, sit: true }
const atCounter = (index: number): Place => ({ x: COUNTER.x - 1.0 + index * 1.0, z: COUNTER.z + 0.85, face: { x: COUNTER.x - 1.0 + index * 1.0, z: -9 }, sit: false })
const onBench = (index: number): Place => ({ x: BENCH.x - 1.1 + index * 0.75, z: BENCH.z - 0.1, face: { x: BENCH.x - 1.1 + index * 0.75, z: -9 }, sit: true })

export const buildDesk: PlaceBuilder<PlaceInput<DeskModel>> = (context) => {
  const { root, finishes, options, still } = context
  const dark = options.dark
  const c = palette(dark)
  const slab = floor('stone', dark, ROOM_BOX, 2.4)
  root.add(slab.mesh)

  const batch = new Batch()
  walls(batch, dark, { wall: dark ? '#4b5163' : '#f3efe8', low: dark ? '#40465a' : '#e5ddd0' }, { x: 3.2, width: 3.2 })
  // The counter: a long desk with a raised front, a lamp and a tray for parcels.
  batch.add(boxShape(COUNTER.width, 1.05, 0.5, 0.04), c.wood, { x: COUNTER.x, y: 0.525, z: COUNTER.z + 0.1 }, 'satin')
  batch.add(boxShape(COUNTER.width + 0.1, 0.05, 0.62, 0.015), c.deskTop, { x: COUNTER.x, y: 1.07, z: COUNTER.z + 0.1 }, 'satin')
  batch.add(boxShape(COUNTER.width - 0.2, 0.7, 0.04), c.woodLight, { x: COUNTER.x, y: 0.45, z: COUNTER.z + 0.37 }, 'satin', false)
  batch.add(boxShape(0.64, 0.4, 0.035, 0.014), '#1d2027', { x: COUNTER.x + 0.6, y: 1.32, z: COUNTER.z }, 'satin')
  batch.add(boxShape(0.5, 0.04, 0.35, 0.01), c.metal, { x: COUNTER.x - 1.2, y: 1.11, z: COUNTER.z + 0.1 }, 'metal')
  batch.add(boxShape(0.46, 0.07, 0.44, 0.03), c.seat, { x: RECEPTION.x, y: 0.29, z: RECEPTION.z }, 'matte')
  batch.add(boxShape(0.44, 0.46, 0.06, 0.03), c.chair, { x: RECEPTION.x, y: 0.62, z: RECEPTION.z - 0.23 }, 'matte')
  batch.add(cylinderShape(0.025, 0.025, 0.2, 10), '#5d6470', { x: RECEPTION.x, y: 0.16, z: RECEPTION.z }, 'metal')
  // A sign on the wall behind it, lit in the accent colour.
  batch.add(boxShape(2.0, 0.5, 0.05, 0.02), dark ? '#2b2f38' : '#e9e4dc', { x: COUNTER.x - 0.4, y: 1.95, z: ROOM_BOX.z0 + 0.03 }, 'satin', false)
  batch.add(boxShape(1.8, 0.08, 0.02), options.accent, { x: COUNTER.x - 0.4, y: 1.95, z: ROOM_BOX.z0 + 0.06 }, 'glow', false)
  // The badge board on the left wall.
  batch.add(boxShape(0.04, 1.3, BOARD.length + 0.08, 0.012), '#aeb5bf', { x: ROOM_BOX.x0 + 0.04, y: 1.55, z: BOARD.z }, 'metal', false)
  batch.add(boxShape(0.02, 1.2, BOARD.length), dark ? '#26303a' : '#fcfcfa', { x: ROOM_BOX.x0 + 0.07, y: 1.55, z: BOARD.z }, 'satin', false)
  // A bench to wait on, plants, and the door's frame at the front right.
  batch.add(boxShape(3.2, 0.08, 0.5, 0.03), c.seat, { x: BENCH.x, y: 0.45, z: BENCH.z }, 'matte')
  batch.add(boxShape(3.2, 0.5, 0.08, 0.03), c.seat, { x: BENCH.x, y: 0.72, z: BENCH.z + 0.24 }, 'matte')
  for (const dx of [-1.45, 0, 1.45]) batch.add(boxShape(0.06, 0.45, 0.4), c.metal, { x: BENCH.x + dx, y: 0.22, z: BENCH.z }, 'metal', false)
  batch.add(boxShape(0.08, 2.3, 0.08), c.metal, { x: DOOR.x - 0.8, y: 1.15, z: DOOR.z }, 'metal')
  batch.add(boxShape(0.08, 2.3, 0.08), c.metal, { x: DOOR.x + 0.8, y: 1.15, z: DOOR.z }, 'metal')
  batch.add(boxShape(1.68, 0.1, 0.1), c.metal, { x: DOOR.x, y: 2.3, z: DOOR.z }, 'metal')
  plant(batch, dark, -5.4, 4.0, true)
  plant(batch, dark, 1.9, -3.9)
  root.add(group(batch, finishes))

  const screenMaterial = new THREE.MeshStandardMaterial({ color: '#0e1420', emissive: c.dim, emissiveIntensity: 0.35, roughness: 0.3 })
  const screen = new THREE.Mesh(boxShape(0.58, 0.34, 0.008), screenMaterial)
  screen.userData.shared = true
  screen.position.set(COUNTER.x + 0.6, 1.32, COUNTER.z - 0.02)
  screen.rotation.y = Math.PI
  root.add(screen)
  const parcels = new THREE.Group()
  root.add(parcels)
  const counterHit = new THREE.Mesh(new THREE.BoxGeometry(COUNTER.width, 1.1, 0.6), new THREE.MeshBasicMaterial({ visible: false }))
  counterHit.position.set(COUNTER.x, 0.55, COUNTER.z + 0.1)
  root.add(counterHit)
  context.pickable(counterHit, 'route:settings')
  const boardHit = new THREE.Mesh(new THREE.BoxGeometry(0.1, 1.3, BOARD.length), new THREE.MeshBasicMaterial({ visible: false }))
  boardHit.position.set(ROOM_BOX.x0 + 0.06, 1.55, BOARD.z)
  root.add(boardHit)
  context.pickable(boardHit, 'route:settings')

  let parcelCount = -1
  let open = false
  let error = false
  return {
    frame: { min: { x: ROOM_BOX.x0, y: 0, z: ROOM_BOX.z0 }, max: { x: ROOM_BOX.x1, y: 2.5, z: ROOM_BOX.z1 }, polar: 0.98, azimuth: 0.62 },
    lamps: [{ x: 0, y: 2.2, z: -1.6 }, { x: -3.6, y: 2.2, z: 2.2 }, { x: 3.2, y: 2.2, z: 2.0 }],
    floor: {
      grid: new FloorGrid([
        { x0: COUNTER.x - COUNTER.width / 2, x1: COUNTER.x + COUNTER.width / 2, z0: COUNTER.z - 0.2, z1: COUNTER.z + 0.4 },
        { x0: BENCH.x - 1.6, x1: BENCH.x + 1.6, z0: BENCH.z, z1: BENCH.z + 0.3 },
      ]),
      door: { x: DOOR.x, z: DOOR.z - 0.2 },
    },
    update({ model, t }) {
      open = model.enabled
      error = model.error
      const people: CrowdActor[] = []
      if (model.enabled) {
        people.push({
          id: 'reception',
          name: t('places.desk.receptionist'),
          state: model.error ? 'failed' : model.pairing ? 'waiting' : model.outgoing > 0 ? 'working' : 'idle',
          stateLabel: model.error ? t('places.desk.error') : model.pairing ? t('places.desk.pairing') : model.outgoing > 0 ? t('places.desk.sending', { count: model.outgoing }) : model.running ? t('places.desk.open') : t('places.desk.starting'),
          look: lookFor('legal'),
          place: RECEPTION,
          action: model.error ? 'slump' : model.pairing ? 'raise' : model.outgoing > 0 ? 'talk' : 'rest',
          ...(model.pairing ? { bubble: '…' } : model.error ? { bubble: '!' } : {}),
          pick: 'route:settings',
        })
      }
      let counter = 0
      let bench = 0
      for (const phone of model.phones) {
        if (!phone.online && !phone.recent) continue
        const coming = phone.recent !== null && counter < 3
        people.push({
          id: `phone-${phone.id}`,
          name: phone.name,
          state: coming ? 'working' : 'idle',
          stateLabel: coming ? t(`places.desk.action.${phone.recent}`) : t('places.desk.waiting'),
          look: lookFor(`phone:${phone.id}`),
          place: coming ? atCounter(counter++) : onBench(bench++ % 4),
          action: coming ? 'talk' : 'rest',
          pick: 'route:settings',
        })
      }
      if (parcelCount !== Math.min(4, model.outgoing)) {
        parcelCount = Math.min(4, model.outgoing)
        for (const child of [...parcels.children]) {
          child.removeFromParent()
          disposeGeometry(child)
        }
        const boxes = new Batch()
        for (let index = 0; index < parcelCount; index += 1) {
          boxes.add(boxShape(0.3, 0.14, 0.22, 0.015), '#c9a47a', { x: COUNTER.x - 1.2 + (index % 2) * 0.05, y: 1.2 + index * 0.15, z: COUNTER.z + 0.1, ry: index * 0.3 }, 'matte')
          boxes.add(boxShape(0.31, 0.02, 0.05), options.accent, { x: COUNTER.x - 1.2 + (index % 2) * 0.05, y: 1.2 + index * 0.15 + 0.07, z: COUNTER.z + 0.1, ry: index * 0.3 }, 'satin', false)
        }
        if (parcelCount > 0) parcels.add(group(boxes, finishes))
      }
      const labels: Record<string, PlaceLabel> = {}
      model.phones.slice(0, 6).forEach((phone, index) => {
        labels[`badge-${phone.id}`] = {
          at: { x: ROOM_BOX.x0 + 0.1, y: 2.05 - index * 0.2, z: BOARD.z },
          title: phone.name,
          detail: phone.online ? t('places.desk.online') : t('places.desk.offline'),
          ...(phone.online ? { tone: 'busy' as const } : {}),
          pick: 'route:settings',
        }
      })
      if (model.phones.length === 0) labels.none = { at: { x: ROOM_BOX.x0 + 0.1, y: 1.7, z: BOARD.z }, title: t('places.desk.noPhones'), pick: 'route:settings' }
      if (!model.enabled) labels.closed = { at: { x: COUNTER.x, y: 1.5, z: COUNTER.z }, title: t('places.desk.closed'), detail: t('places.desk.closedHint'), pick: 'route:settings' }
      return { people, labels }
    },
    tick(now) {
      screenMaterial.emissive.set(error ? '#8a2b24' : open ? (dark ? '#3d7bd9' : '#4b8fe6') : c.dim)
      screenMaterial.emissiveIntensity = open ? 0.75 + (still ? 0 : Math.sin(now * 2) * 0.05) : 0.2
      return false
    },
    dispose() {
      slab.dispose()
      for (const child of [...root.children]) disposeGeometry(child)
      screenMaterial.dispose()
      for (const hit of [counterHit, boardHit]) (hit.material as THREE.Material).dispose()
    },
  }
}

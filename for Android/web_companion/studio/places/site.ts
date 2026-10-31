import * as THREE from 'three'

import { lookFor } from '../cast'
import type { Place } from '../layout'
import { Batch, boxShape, cylinderShape } from '../mesh-kit'
import { FloorGrid } from '../paths'
import { SITE_DISTRICTS, type BuildingKind, type SiteBuilding, type SiteModel } from './models'
import { ROOM_BOX, disposeGeometry, floor, group, palette } from './kit'
import type { CrowdActor, PlaceBuilder, PlaceLabel } from './stage'
import type { PlaceInput } from './types'

/**
 * The open folder as a building site: each top-level folder is a block, each file a building as
 * tall as the file is large. Files changed and not committed stand in scaffolding (red where Git
 * has a conflict); the one the agent is writing has the crane over it and the agent beside it.
 * Commits not pushed yet are trucks waiting at the gate; the site office shows the branch and
 * the checks.
 */

const AREA = { x0: -3.5, x1: 4.1, z0: -2.7, z1: 3.9 }
const COLUMNS = 4
const STREET = 0.24
const CELL = 0.36
const FOOT = 0.26
const OFFICE = { x: -4.85, z: -3.55 }
const CRANE = { x: 4.9, z: -3.55 }
const GATE = { x: 5.2, z: 4.2 }
const MAST = 4.6

const KIND_COLOURS: Record<BuildingKind, string> = {
  code: '#5b7db1', web: '#7b5ea7', doc: '#e3dccb', data: '#4f8a5b', config: '#9aa1ab', asset: '#c06c84', other: '#b8a48c',
}

const OFFICE_PLACE: Place = { x: OFFICE.x + 1.35, z: OFFICE.z + 0.5, face: { x: 0, z: 2 }, sit: false }

interface Plot { x0: number; x1: number; z0: number; z1: number; columns: number }

function plots(count: number): Plot[] {
  const rows = count > COLUMNS ? 2 : 1
  const columns = Math.min(COLUMNS, Math.max(1, count))
  const width = (AREA.x1 - AREA.x0 - STREET * (columns - 1)) / columns
  const depth = (AREA.z1 - AREA.z0 - STREET * (rows - 1)) / rows
  return Array.from({ length: count }, (_, index) => {
    const column = index % COLUMNS
    const row = Math.floor(index / COLUMNS)
    const x0 = AREA.x0 + column * (width + STREET)
    const z0 = AREA.z0 + row * (depth + STREET)
    return { x0, x1: x0 + width, z0, z1: z0 + depth, columns: Math.max(1, Math.floor((width - 0.1) / CELL)) }
  })
}

export const buildSite: PlaceBuilder<PlaceInput<SiteModel>> = (context) => {
  const { root, finishes, options, still } = context
  const dark = options.dark
  const c = palette(dark)
  const ground = floor('dirt', dark, ROOM_BOX, 3)
  root.add(ground.mesh)

  const batch = new Batch()
  batch.add(boxShape(ROOM_BOX.x1 - ROOM_BOX.x0 + 0.1, 0.12, ROOM_BOX.z1 - ROOM_BOX.z0 + 0.1), c.skirt, { y: -0.3 }, 'matte', false)
  // A fence of panels on posts along the back and the left, with the gate gap at the front right.
  const fence = dark ? '#8a93a3' : '#9aa1ab'
  for (let x = ROOM_BOX.x0; x <= ROOM_BOX.x1 + 0.01; x += 1.2) batch.add(cylinderShape(0.04, 0.04, 1.3, 8), fence, { x, y: 0.65, z: ROOM_BOX.z0 + 0.05 }, 'metal')
  for (let z = ROOM_BOX.z0; z <= ROOM_BOX.z1 + 0.01; z += 1.2) batch.add(cylinderShape(0.04, 0.04, 1.3, 8), fence, { x: ROOM_BOX.x0 + 0.05, y: 0.65, z }, 'metal')
  batch.add(boxShape(ROOM_BOX.x1 - ROOM_BOX.x0, 1.1, 0.02), dark ? '#3c4c5e' : '#7d97b0', { y: 0.65, z: ROOM_BOX.z0 + 0.05 }, 'glass', false)
  batch.add(boxShape(0.02, 1.1, ROOM_BOX.z1 - ROOM_BOX.z0), dark ? '#3c4c5e' : '#7d97b0', { x: ROOM_BOX.x0 + 0.05, y: 0.65 }, 'glass', false)
  // The site office: a cabin on blocks with a window, a door and steps.
  const cabin = dark ? '#c9a43a' : '#e8c547'
  batch.add(boxShape(2.1, 1.25, 1.2, 0.03), cabin, { x: OFFICE.x, y: 0.8, z: OFFICE.z }, 'satin')
  batch.add(boxShape(2.2, 0.08, 1.3, 0.02), c.trim, { x: OFFICE.x, y: 1.46, z: OFFICE.z }, 'satin')
  for (const dx of [-0.85, 0.85]) batch.add(boxShape(0.3, 0.18, 1.0), '#7a7a7a', { x: OFFICE.x + dx, y: 0.09, z: OFFICE.z }, 'matte')
  batch.add(boxShape(0.7, 0.45, 0.02), c.sky, { x: OFFICE.x - 0.35, y: 0.95, z: OFFICE.z + 0.61 }, 'glow', false)
  batch.add(boxShape(0.4, 0.95, 0.02), '#5d6470', { x: OFFICE.x + 0.6, y: 0.66, z: OFFICE.z + 0.61 }, 'satin', false)
  batch.add(boxShape(0.5, 0.08, 0.3), '#7a7a7a', { x: OFFICE.x + 0.6, y: 0.1, z: OFFICE.z + 0.78 }, 'matte')
  // The tower crane's mast and base; its jib turns.
  batch.add(boxShape(0.9, 0.3, 0.9, 0.02), '#7a7a7a', { x: CRANE.x, y: 0.15, z: CRANE.z }, 'matte')
  for (let y = 0.3; y < MAST; y += 0.45) {
    for (const [dx, dz] of [[-0.18, -0.18], [0.18, -0.18], [-0.18, 0.18], [0.18, 0.18]] as const) batch.add(boxShape(0.04, 0.46, 0.04), '#e0a13a', { x: CRANE.x + dx, y: y + 0.22, z: CRANE.z + dz }, 'metal', false)
    batch.add(boxShape(0.4, 0.03, 0.4), '#e0a13a', { x: CRANE.x, y, z: CRANE.z }, 'metal', false)
  }
  root.add(group(batch, finishes))

  const jib = new THREE.Group()
  jib.position.set(CRANE.x, MAST, CRANE.z)
  const arm = new Batch()
  arm.add(boxShape(7.2, 0.18, 0.22), '#e0a13a', { x: -2.8 }, 'metal')
  arm.add(boxShape(1.4, 0.3, 0.5, 0.03), '#6b7280', { x: 1.2, y: -0.1 }, 'metal')
  arm.add(boxShape(0.7, 0.55, 0.55, 0.03), dark ? '#c9ccd2' : '#eef0f3', { x: 0.2, y: -0.4 }, 'satin')
  jib.add(group(arm, finishes))
  // The hook hangs from the trolley on a cable that pays out to the building.
  const cable = new THREE.Group()
  const line = new Batch()
  line.add(cylinderShape(0.008, 0.008, 1, 4), '#2a2d35', { y: -0.5 }, 'metal', false)
  cable.add(group(line, finishes))
  jib.add(cable)
  const hook = new THREE.Group()
  const block = new Batch()
  block.add(boxShape(0.1, 0.12, 0.1, 0.02), '#2a2d35', {}, 'metal')
  hook.add(group(block, finishes))
  jib.add(hook)
  root.add(jib)

  // Buildings: one instanced mesh, and scaffolding around the changed ones.
  const capacity = 240
  const buildingMaterial = new THREE.MeshStandardMaterial({ roughness: 0.7 })
  const buildings = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), buildingMaterial, capacity)
  buildings.castShadow = true
  buildings.receiveShadow = true
  buildings.count = 0
  root.add(buildings)
  const scaffoldMaterial = new THREE.MeshStandardMaterial({ color: '#f08a24', transparent: true, opacity: 0.38, roughness: 0.6, depthWrite: false })
  const scaffolds = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), scaffoldMaterial, capacity)
  scaffolds.count = 0
  root.add(scaffolds)
  const pavement = new THREE.Group()
  root.add(pavement)
  const trucks = new THREE.Group()
  root.add(trucks)
  const beacon = new THREE.MeshBasicMaterial({ color: '#ff3b30', toneMapped: false })
  const beaconMesh = new THREE.Mesh(boxShape(0.12, 0.12, 0.12, 0.03), beacon)
  beaconMesh.userData.shared = true
  beaconMesh.position.set(OFFICE.x - 0.85, 1.6, OFFICE.z + 0.4)
  root.add(beaconMesh)

  let shown: SiteBuilding[] = []
  context.pickable(buildings, (index) => (shown[index] ? `file:${shown[index]!.path}` : undefined))
  const officeHit = new THREE.Mesh(new THREE.BoxGeometry(2.1, 1.5, 1.2), new THREE.MeshBasicMaterial({ visible: false }))
  officeHit.position.set(OFFICE.x, 0.8, OFFICE.z)
  root.add(officeHit)
  context.pickable(officeHit, 'route:changes')

  const matrix = new THREE.Matrix4()
  const colour = new THREE.Color()
  const at = new Map<string, THREE.Vector3>()
  let editing: THREE.Vector3 | null = null
  let jibAngle = 0.4
  let failing = false
  let plotSignature = ''
  let uncommitted = ''

  const layout = (model: SiteModel): Record<string, PlaceLabel> => {
    const lots = plots(Math.min(SITE_DISTRICTS, model.districts.length))
    const signature = lots.map((lot) => `${lot.x0.toFixed(2)},${lot.z0.toFixed(2)}`).join('|')
    if (signature !== plotSignature) {
      plotSignature = signature
      for (const child of [...pavement.children]) {
        child.removeFromParent()
        disposeGeometry(child)
      }
      const slabs = new Batch()
      for (const lot of lots) slabs.add(boxShape(lot.x1 - lot.x0, 0.04, lot.z1 - lot.z0, 0.01), dark ? '#4a4f5a' : '#d6d2c8', { x: (lot.x0 + lot.x1) / 2, y: 0.02, z: (lot.z0 + lot.z1) / 2 }, 'matte', false)
      if (lots.length > 0) pavement.add(group(slabs, finishes))
    }
    let count = 0
    let marks = 0
    shown = []
    at.clear()
    editing = null
    const labels: Record<string, PlaceLabel> = {}
    model.districts.forEach((district, index) => {
      const lot = lots[index]
      if (!lot) return
      // The block's buildings in the middle of its lot, in as many columns as keep it square.
      const rowsFit = Math.max(1, Math.floor((lot.z1 - lot.z0 - 0.1) / CELL))
      const columns = Math.min(lot.columns, Math.max(1, Math.ceil(district.buildings.length / rowsFit), Math.ceil(Math.sqrt(district.buildings.length * (lot.x1 - lot.x0) / (lot.z1 - lot.z0)))))
      const rows = Math.min(rowsFit, Math.ceil(district.buildings.length / columns))
      const left = lot.x0 + (lot.x1 - lot.x0 - columns * CELL) / 2
      const back = lot.z0 + (lot.z1 - lot.z0 - rows * CELL) / 2
      district.buildings.forEach((building, slot) => {
        const column = slot % columns
        const row = Math.floor(slot / columns)
        const x = left + CELL / 2 + column * CELL
        const z = back + CELL / 2 + row * CELL
        if (z + FOOT / 2 > lot.z1 || count >= capacity) return
        const height = 0.12 + building.height * 1.5
        matrix.compose(new THREE.Vector3(x, 0.04, z), new THREE.Quaternion(), new THREE.Vector3(FOOT, height, FOOT))
        buildings.setMatrixAt(count, matrix)
        buildings.setColorAt(count, colour.set(building.editing ? options.accent : KIND_COLOURS[building.kind]))
        shown[count] = building
        count += 1
        at.set(building.path, new THREE.Vector3(x, height, z))
        if (building.editing) editing = new THREE.Vector3(x, height, z)
        if (building.changed || building.conflict || building.editing) {
          matrix.compose(new THREE.Vector3(x, 0.04, z), new THREE.Quaternion(), new THREE.Vector3(FOOT + 0.07, height + 0.12, FOOT + 0.07))
          scaffolds.setMatrixAt(marks, matrix)
          scaffolds.setColorAt(marks, colour.set(building.conflict ? '#e5534b' : '#ffffff'))
          marks += 1
        }
      })
      labels[`district-${district.name}`] = {
        at: { x: (lot.x0 + lot.x1) / 2, y: 0.5, z: lot.z1 },
        title: district.name === '.' ? (model.folder ?? '.') : district.name,
        detail: String(district.total),
      }
    })
    buildings.count = count
    scaffolds.count = marks
    buildings.instanceMatrix.needsUpdate = true
    if (buildings.instanceColor) buildings.instanceColor.needsUpdate = true
    scaffolds.instanceMatrix.needsUpdate = true
    if (scaffolds.instanceColor) scaffolds.instanceColor.needsUpdate = true
    return labels
  }

  const park = (count: number): void => {
    if (trucks.children.length === count) return
    for (const child of [...trucks.children]) {
      child.removeFromParent()
      disposeGeometry(child)
    }
    const fleet = new Batch()
    for (let index = 0; index < count; index += 1) {
      const z = GATE.z - 0.9 - index * 1.25
      fleet.add(boxShape(0.75, 0.6, 1.0, 0.04), '#f2f2f2', { x: GATE.x, y: 0.45, z }, 'satin')
      fleet.add(boxShape(0.7, 0.5, 0.42, 0.05), '#3f88c5', { x: GATE.x, y: 0.4, z: z + 0.72 }, 'satin')
      fleet.add(boxShape(0.6, 0.18, 0.02), c.sky, { x: GATE.x, y: 0.52, z: z + 0.94 }, 'glow', false)
      for (const [dx, dz] of [[-0.38, -0.3], [0.38, -0.3], [-0.38, 0.7], [0.38, 0.7]] as const) fleet.add(cylinderShape(0.12, 0.12, 0.08, 12), '#1d2027', { x: GATE.x + dx, y: 0.12, z: z + dz, rz: Math.PI / 2 }, 'satin')
    }
    if (count > 0) trucks.add(group(fleet, finishes))
  }

  return {
    frame: { min: { x: ROOM_BOX.x0, y: 0, z: ROOM_BOX.z0 }, max: { x: ROOM_BOX.x1, y: 2.2, z: ROOM_BOX.z1 }, polar: 0.92, azimuth: 0.62 },
    // Floodlights on the fence.
    lamps: [{ x: -4.5, y: 3.0, z: -3.0, colour: '#fff1d6' }, { x: 2.0, y: 3.0, z: -3.6, colour: '#fff1d6' }, { x: 0.5, y: 3.0, z: 2.5, colour: '#fff1d6' }],
    floor: {
      grid: new FloorGrid([
        { x0: OFFICE.x - 1.05, x1: OFFICE.x + 1.05, z0: OFFICE.z - 0.6, z1: OFFICE.z + 0.6 },
        { x0: CRANE.x - 0.45, x1: CRANE.x + 0.45, z0: CRANE.z - 0.45, z1: CRANE.z + 0.45 },
      ]),
      door: GATE,
    },
    update({ model, t, lead, visitors = [] }) {
      uncommitted = t('places.site.uncommitted')
      const labels = layout(model)
      park(Math.min(3, model.ahead))
      failing = model.checks.failed.length > 0
      const target = editing as THREE.Vector3 | null
      const worker: Place = target && model.worker.state === 'editing'
        ? { x: target.x - 0.32, z: target.z + 0.32, face: { x: target.x, z: target.z }, sit: false }
        : OFFICE_PLACE
      const people: CrowdActor[] = [{
        id: 'worker',
        name: lead,
        state: model.worker.state === 'idle' ? 'idle' : 'working',
        stateLabel: t(`places.site.worker.${model.worker.state}`),
        look: { ...lookFor('lead'), accessory: 'helmet' },
        place: worker,
        action: model.worker.state === 'editing' ? 'operate' : model.worker.state === 'testing' ? 'operate' : model.worker.state === 'reading' ? 'paper' : 'rest',
        pick: 'agent',
      }]
      // Experts of any team writing code or running checks: each at a building of the site.
      const standing = [...at.values()]
      visitors.forEach((visitor, index) => {
        const spot = standing.length > 0 ? standing[(index * 7 + 3) % standing.length]! : new THREE.Vector3(OFFICE_PLACE.x + 0.6 * (index + 1), 0, OFFICE_PLACE.z + 0.4)
        people.push({
          id: visitor.id, name: visitor.name, state: 'working', stateLabel: visitor.stateLabel,
          look: { ...visitor.look, accessory: 'helmet' },
          place: { x: spot.x + 0.3, z: spot.z + 0.3, face: { x: spot.x, z: spot.z }, sit: false },
          action: 'operate', pick: visitor.pick,
        })
      })
      labels.office = {
        at: { x: OFFICE.x, y: 1.75, z: OFFICE.z },
        title: model.branch ?? t('places.site.noGit'),
        detail: model.checks.running ? t('places.site.checking')
          : model.checks.failed.length > 0 ? t('places.site.checksFailed', { names: model.checks.failed.slice(0, 3).join(', ') })
            : model.changed > 0 ? t('places.site.changed', { count: model.changed }) : t('places.site.clean'),
        ...(model.checks.failed.length > 0 ? { tone: 'alert' as const } : model.checks.running || model.worker.state !== 'idle' ? { tone: 'busy' as const } : {}),
        pick: 'route:changes',
      }
      if (model.ahead > 0) labels.gate = { at: { x: GATE.x, y: 1.0, z: GATE.z - 1.2 }, title: t('places.site.unpushed', { count: model.ahead }), pick: 'route:changes' }
      if (model.files === 0) labels.empty = { at: { x: 0.3, y: 0.6, z: 0.6 }, title: t('places.site.empty') }
      return { people, labels }
    },
    tick(now, dt) {
      // The jib turns toward the file being written, the hook over it.
      const target = editing as THREE.Vector3 | null
      const want = target ? Math.atan2(-(target.z - CRANE.z), target.x - CRANE.x) + Math.PI : 0.4
      let diff = want - jibAngle
      diff = Math.atan2(Math.sin(diff), Math.cos(diff))
      const turning = Math.abs(diff) > 0.002
      jibAngle += still ? diff : diff * Math.min(1, dt * 1.5)
      jib.rotation.y = jibAngle
      const reach = target ? Math.min(6.5, Math.hypot(target.x - CRANE.x, target.z - CRANE.z)) : 3
      const drop = Math.max(0.3, target ? MAST - target.y - 0.4 : 1.8)
      cable.position.set(-reach, 0, 0)
      cable.scale.set(1, drop, 1)
      hook.position.set(-reach, -drop - 0.06, 0)
      beacon.color.set(failing ? (still || Math.sin(now * 6) > 0 ? '#ff3b30' : '#5a1a16') : '#3a3f4b')
      return turning
    },
    hover(pick) {
      if (!pick.startsWith('file:')) return null
      const path = pick.slice(5)
      const point = at.get(path)
      const building = shown.find((item) => item.path === path)
      return point && building ? { at: { x: point.x, y: point.y + 0.15, z: point.z }, title: path, ...(building.changed ? { detail: uncommitted, tone: 'busy' as const } : {}) } : null
    },
    dispose() {
      ground.dispose()
      for (const child of [...root.children]) if (child !== buildings && child !== scaffolds) disposeGeometry(child)
      buildings.geometry.dispose()
      scaffolds.geometry.dispose()
      buildingMaterial.dispose()
      scaffoldMaterial.dispose()
      beacon.dispose()
      ;(officeHit.material as THREE.Material).dispose()
    },
  }
}

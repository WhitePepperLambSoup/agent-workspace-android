import * as THREE from 'three'

import { lookFor } from '../cast'
import type { Place } from '../layout'
import { Batch, boxShape, cylinderShape } from '../mesh-kit'
import { FloorGrid } from '../paths'
import { BOOKS_PER_CASE, LIBRARY_CASES, type BookKind, type LibraryBook, type LibraryModel } from './models'
import { ROOM_BOX, desk, disposeGeometry, floor, group, hashed, palette, plant, walls } from './kit'
import type { CrowdActor, PlaceBuilder, PlaceLabel } from './stage'
import type { PlaceInput } from './types'

/**
 * The library: a bookcase for each knowledge base along the back wall, its documents as books;
 * the reference library's papers on the left wall; reading tables in the middle; the desk, the
 * cart of documents still being read in, and the scanner at the front. The librarian is the
 * conversation's agent: at the shelves while it searches, at a reading table with what it found.
 */

const CASE_WIDTH = 1.9
const CASE_HEIGHT = 2.2
const CASE_DEPTH = 0.42
const LEVELS = 4
const LEVEL_HEIGHT = 0.52
const SHELF_ORDER = [2, 1, 3, 0] as const
const caseX = (index: number): number => -4.6 + index * 2.3
const CASE_Z = ROOM_BOX.z0 + CASE_DEPTH / 2 + 0.04
const PAPERS = { x: ROOM_BOX.x0 + 0.24, z0: -2.6, z1: 0.6 }
const TABLES = [{ x: -1.3, z: 0.9 }, { x: 2.1, z: 0.9 }]
const COUNTER = { x: 3.9, z: 3.3 }
const CART = { x: 1.9, z: 3.5 }
const SCANNER = { x: 5.3, z: 1.6 }

const KIND_COLOURS: Record<BookKind, string> = {
  pdf: '#b5523b', word: '#3d6fa5', sheet: '#4f8a5b', slides: '#e0a13a', web: '#7b5ea7', text: '#c06c84', image: '#2f4858', other: '#8a8d3b',
}

const CASE_PLACE = (index: number): Place => ({ x: caseX(index), z: CASE_Z + 0.85, face: { x: caseX(index), z: -9 }, sit: false })
const PAPERS_PLACE: Place = { x: PAPERS.x + 0.75, z: (PAPERS.z0 + PAPERS.z1) / 2, face: { x: -9, z: (PAPERS.z0 + PAPERS.z1) / 2 }, sit: false }
const READING_PLACE: Place = { x: TABLES[0]!.x - 0.5, z: TABLES[0]!.z - 0.72, face: { x: TABLES[0]!.x - 0.5, z: 5 }, sit: true }
const DESK_PLACE: Place = { x: COUNTER.x, z: COUNTER.z - 0.75, face: { x: COUNTER.x, z: 6 }, sit: true }
const CART_PLACE: Place = { x: CART.x, z: CART.z - 0.65, face: { x: CART.x, z: 6 }, sit: false }
const SCANNER_PLACE: Place = { x: SCANNER.x - 0.7, z: SCANNER.z, face: { x: 9, z: SCANNER.z }, sit: false }

export const buildLibrary: PlaceBuilder<PlaceInput<LibraryModel>> = (context) => {
  const { root, finishes, options, still } = context
  const dark = options.dark
  const c = palette(dark)
  const slab = floor('wood', dark, ROOM_BOX, 3)
  root.add(slab.mesh)

  const batch = new Batch()
  walls(batch, dark, { wall: dark ? '#4a4f5f' : '#efe6d8', low: dark ? '#3f4454' : '#e2d5c2' })
  // Bookcases: sides, back, shelves and a crown.
  for (let index = 0; index < LIBRARY_CASES; index += 1) {
    const x = caseX(index)
    for (const side of [-1, 1]) batch.add(boxShape(0.05, CASE_HEIGHT, CASE_DEPTH, 0.01), c.wood, { x: x + side * (CASE_WIDTH / 2), y: CASE_HEIGHT / 2, z: CASE_Z }, 'satin')
    batch.add(boxShape(CASE_WIDTH, CASE_HEIGHT, 0.03), c.woodLight, { x, y: CASE_HEIGHT / 2, z: CASE_Z - CASE_DEPTH / 2 + 0.015 }, 'matte', false)
    for (let level = 0; level <= LEVELS; level += 1) batch.add(boxShape(CASE_WIDTH, 0.035, CASE_DEPTH, 0.008), c.wood, { x, y: 0.06 + level * LEVEL_HEIGHT, z: CASE_Z }, 'satin')
    batch.add(boxShape(CASE_WIDTH + 0.1, 0.08, CASE_DEPTH + 0.06, 0.02), c.wood, { x, y: CASE_HEIGHT + 0.04, z: CASE_Z }, 'satin')
  }
  // The papers' shelves on the left wall.
  const papersLength = PAPERS.z1 - PAPERS.z0
  for (const z of [PAPERS.z0, PAPERS.z1]) batch.add(boxShape(0.42, CASE_HEIGHT, 0.05, 0.01), c.wood, { x: PAPERS.x, y: CASE_HEIGHT / 2, z }, 'satin')
  for (let level = 0; level <= LEVELS; level += 1) batch.add(boxShape(0.42, 0.035, papersLength, 0.008), c.wood, { x: PAPERS.x, y: 0.06 + level * LEVEL_HEIGHT, z: (PAPERS.z0 + PAPERS.z1) / 2 }, 'satin')
  // Reading tables with chairs on both long sides and green lamps.
  for (const table of TABLES) {
    batch.add(boxShape(2.4, 0.06, 0.95, 0.02), c.wood, { x: table.x, y: 0.72, z: table.z }, 'satin')
    for (const [dx, dz] of [[-1.1, -0.38], [1.1, -0.38], [-1.1, 0.38], [1.1, 0.38]] as const) batch.add(boxShape(0.07, 0.7, 0.07), c.woodLight, { x: table.x + dx, y: 0.35, z: table.z + dz }, 'satin')
    for (const dx of [-0.5, 0.5]) {
      for (const side of [-1, 1]) {
        const z = table.z + side * 0.72
        batch.add(boxShape(0.42, 0.06, 0.4, 0.02), c.seat, { x: table.x + dx, y: 0.46, z }, 'matte')
        batch.add(boxShape(0.42, 0.42, 0.05, 0.02), c.wood, { x: table.x + dx, y: 0.7, z: z + side * 0.2 }, 'satin')
        for (const [lx, lz] of [[-0.17, -0.15], [0.17, -0.15], [-0.17, 0.15], [0.17, 0.15]] as const) batch.add(boxShape(0.035, 0.44, 0.035), c.woodLight, { x: table.x + dx + lx, y: 0.22, z: z + lz }, 'satin', false)
      }
      batch.add(cylinderShape(0.06, 0.07, 0.02, 12), '#b08d3c', { x: table.x + dx, y: 0.76, z: table.z }, 'metal', false)
      batch.add(cylinderShape(0.012, 0.012, 0.26, 6), '#b08d3c', { x: table.x + dx, y: 0.88, z: table.z }, 'metal', false)
      batch.add(boxShape(0.3, 0.07, 0.12, 0.03), '#2f6b48', { x: table.x + dx, y: 1.02, z: table.z }, dark ? 'glow' : 'satin', false)
    }
  }
  // The desk at the front, the cart and the scanner.
  const screenAt = desk(batch, dark, COUNTER.x, COUNTER.z, 1.8)
  batch.add(boxShape(0.9, 0.05, 0.5, 0.01), c.metal, { x: CART.x, y: 0.75, z: CART.z }, 'metal')
  batch.add(boxShape(0.9, 0.05, 0.5, 0.01), c.metal, { x: CART.x, y: 0.35, z: CART.z }, 'metal')
  for (const [dx, dz] of [[-0.42, -0.22], [0.42, -0.22], [-0.42, 0.22], [0.42, 0.22]] as const) {
    batch.add(boxShape(0.03, 0.75, 0.03), c.metal, { x: CART.x + dx, y: 0.42, z: CART.z + dz }, 'metal', false)
    batch.add(cylinderShape(0.04, 0.04, 0.03, 10), '#2a2d35', { x: CART.x + dx, y: 0.04, z: CART.z + dz, rz: Math.PI / 2 }, 'satin', false)
  }
  batch.add(boxShape(0.7, 0.9, 0.6, 0.03), dark ? '#c9ccd2' : '#eef0f3', { x: SCANNER.x, y: 0.45, z: SCANNER.z }, 'satin')
  batch.add(boxShape(0.62, 0.04, 0.5, 0.01), '#3a3f4b', { x: SCANNER.x, y: 0.92, z: SCANNER.z }, 'satin', false)
  plant(batch, dark, -5.4, 4.0, true)
  plant(batch, dark, 5.5, -2.9)
  root.add(group(batch, finishes))

  // Books: one instanced mesh for the knowledge bases, the papers and the cart; a ribbon marks
  // what the latest search found.
  const capacity = LIBRARY_CASES * BOOKS_PER_CASE + 60 + 10
  const bookMaterial = new THREE.MeshStandardMaterial({ roughness: 0.8 })
  const books = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), bookMaterial, capacity)
  books.castShadow = true
  books.count = 0
  root.add(books)
  const ribbonMaterial = new THREE.MeshBasicMaterial({ color: options.accent, toneMapped: false })
  const ribbons = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), ribbonMaterial, BOOKS_PER_CASE * LIBRARY_CASES)
  ribbons.count = 0
  root.add(ribbons)
  // A stack on the reading table: what the agent found, while it writes the answer.
  const stack = new THREE.Group()
  root.add(stack)
  const lampLight = new THREE.PointLight('#ffd9a0', 0, 3, 1.6)
  lampLight.position.set(TABLES[0]!.x - 0.5, 1.2, TABLES[0]!.z)
  root.add(lampLight)
  const screenMaterial = new THREE.MeshStandardMaterial({ color: '#0e1420', emissive: c.dim, emissiveIntensity: 0.4, roughness: 0.3 })
  const screen = new THREE.Mesh(boxShape(0.58, 0.34, 0.008), screenMaterial)
  screen.userData.shared = true
  screen.position.copy(screenAt)
  root.add(screen)

  for (let index = 0; index < LIBRARY_CASES; index += 1) {
    const hit = new THREE.Mesh(new THREE.BoxGeometry(CASE_WIDTH, CASE_HEIGHT, CASE_DEPTH), new THREE.MeshBasicMaterial({ visible: false }))
    hit.position.set(caseX(index), CASE_HEIGHT / 2, CASE_Z)
    root.add(hit)
    context.pickable(hit, 'route:knowledge')
  }
  const papersHit = new THREE.Mesh(new THREE.BoxGeometry(0.42, CASE_HEIGHT, papersLength), new THREE.MeshBasicMaterial({ visible: false }))
  papersHit.position.set(PAPERS.x, CASE_HEIGHT / 2, (PAPERS.z0 + PAPERS.z1) / 2)
  root.add(papersHit)
  context.pickable(papersHit, 'route:workspace')

  const matrix = new THREE.Matrix4()
  const colour = new THREE.Color()
  const quaternion = new THREE.Quaternion()
  const tilt = new THREE.Euler()
  const place = (index: number, x: number, y: number, z: number, width: number, height: number, depth: number, colourOf: string, lean = 0): void => {
    quaternion.setFromEuler(tilt.set(0, 0, lean))
    matrix.compose(new THREE.Vector3(x, y, z), quaternion, new THREE.Vector3(width, height, depth))
    books.setMatrixAt(index, matrix)
    books.setColorAt(index, colour.set(colourOf))
  }
  const thickness = (book: LibraryBook): number => 0.045 + Math.min(0.06, Math.log2(1 + book.size) * 0.008)
  const shelve = (model: LibraryModel): number => {
    let count = 0
    let marks = 0
    model.cases.forEach((item, caseIndex) => {
      // The eye-level shelves fill first.
      let shelf = 0
      let level: number = SHELF_ORDER[0]
      let cursor = caseX(caseIndex) - CASE_WIDTH / 2 + 0.08
      for (const book of item.books) {
        const width = thickness(book)
        if (cursor + width > caseX(caseIndex) + CASE_WIDTH / 2 - 0.06) {
          shelf += 1
          if (shelf >= SHELF_ORDER.length) break
          level = SHELF_ORDER[shelf]!
          cursor = caseX(caseIndex) - CASE_WIDTH / 2 + 0.08
        }
        const height = 0.36 + hashed(book.id) * 0.1
        const y = 0.08 + level * LEVEL_HEIGHT + height / 2
        // What the latest search found stands out of the row, with a ribbon.
        const out = book.cited ? 0.08 : 0
        place(count++, cursor + width / 2, y, CASE_Z + 0.02 + out, width, height, 0.24, KIND_COLOURS[book.kind])
        if (book.cited) {
          matrix.compose(new THREE.Vector3(cursor + width / 2, y + height / 2 + 0.03, CASE_Z + 0.14 + out), quaternion.identity(), new THREE.Vector3(Math.max(0.012, width * 0.4), 0.08, 0.01))
          ribbons.setMatrixAt(marks++, matrix)
        }
        cursor += width + 0.006
      }
    })
    let level = LEVELS - 1
    let cursor = PAPERS.z0 + 0.06
    for (const paper of model.papers.books) {
      if (cursor + 0.03 > PAPERS.z1 - 0.06) {
        level -= 1
        cursor = PAPERS.z0 + 0.06
        if (level < 0) break
      }
      place(count++, PAPERS.x + 0.04, 0.08 + level * LEVEL_HEIGHT + 0.15, cursor + 0.012, 0.25, 0.3, 0.024, hashed(paper.id) > 0.5 ? '#e8e2d2' : '#d9cdb4')
      cursor += 0.03
    }
    // The cart: reading in (pale) or failed (lying flat, grey).
    model.cart.forEach((book, index) => {
      const failed = book.state === 'failed'
      const x = CART.x - 0.36 + (index % 5) * 0.17
      const y = index < 5 ? 0.79 : 0.39
      place(count++, x, y + (failed ? 0.02 : 0.13), CART.z, failed ? 0.24 : 0.05, failed ? 0.04 : 0.26, failed ? 0.18 : 0.2, failed ? '#8a8f98' : new THREE.Color(KIND_COLOURS[book.kind]).lerp(new THREE.Color('#ffffff'), 0.35).getStyle())
    })
    books.count = count
    ribbons.count = marks
    books.instanceMatrix.needsUpdate = true
    if (books.instanceColor) books.instanceColor.needsUpdate = true
    ribbons.instanceMatrix.needsUpdate = true
    return marks
  }

  let reading = false
  let screenBusy = false
  let stackSize = 0
  return {
    frame: { min: { x: ROOM_BOX.x0, y: 0, z: ROOM_BOX.z0 }, max: { x: ROOM_BOX.x1, y: CASE_HEIGHT + 0.2, z: ROOM_BOX.z1 }, polar: 0.98, azimuth: 0.62 },
    lamps: [{ x: -2.3, y: 2.2, z: -2.6 }, { x: 2.3, y: 2.2, z: -2.6 }, { x: 0.4, y: 2.0, z: 1.0 }, { x: 3.9, y: 1.9, z: 3.0 }],
    floor: {
      grid: new FloorGrid([
        ...Array.from({ length: LIBRARY_CASES }, (_, index) => ({ x0: caseX(index) - CASE_WIDTH / 2, x1: caseX(index) + CASE_WIDTH / 2, z0: ROOM_BOX.z0, z1: CASE_Z + CASE_DEPTH / 2 })),
        { x0: ROOM_BOX.x0, x1: PAPERS.x + 0.21, z0: PAPERS.z0, z1: PAPERS.z1 },
        ...TABLES.map((table) => ({ x0: table.x - 1.2, x1: table.x + 1.2, z0: table.z - 0.48, z1: table.z + 0.48 })),
        { x0: COUNTER.x - 0.9, x1: COUNTER.x + 0.9, z0: COUNTER.z - 0.35, z1: COUNTER.z + 0.35 },
        { x0: CART.x - 0.45, x1: CART.x + 0.45, z0: CART.z - 0.25, z1: CART.z + 0.25 },
        { x0: SCANNER.x - 0.35, x1: SCANNER.x + 0.35, z0: SCANNER.z - 0.3, z1: SCANNER.z + 0.3 },
      ]),
      door: { x: 5.4, z: 4.2 },
    },
    update({ model, t, lead, visitors = [] }) {
      shelve(model)
      const people: CrowdActor[] = []
      const { librarian } = model
      const caseIndex = model.cases.findIndex((item) => item.id === librarian.caseId)
      const where: Place = librarian.state === 'searching' ? CASE_PLACE(Math.max(0, caseIndex))
        : librarian.state === 'papers' ? PAPERS_PLACE
          : librarian.state === 'reading' ? READING_PLACE
            : librarian.state === 'adding' ? CART_PLACE : DESK_PLACE
      people.push({
        id: 'librarian',
        name: lead,
        state: librarian.state === 'idle' ? 'idle' : 'working',
        stateLabel: t(`places.library.librarian.${librarian.state}`),
        look: lookFor('lead'),
        place: where,
        action: librarian.state === 'searching' || librarian.state === 'papers' ? 'read'
          : librarian.state === 'reading' ? 'paper' : librarian.state === 'adding' ? 'operate' : 'rest',
        pick: 'agent',
      })
      if (model.clerk) {
        people.push({
          id: 'clerk', name: t('places.library.clerk'), state: 'working',
          stateLabel: t('places.library.reading', { count: model.cart.filter((book) => book.state !== 'failed').length }),
          look: lookFor('teacher'), place: SCANNER_PLACE, action: 'operate', pick: 'route:knowledge',
        })
      }
      // Experts of any team looking things up: at the shelves the librarian leaves free, then at the second table.
      const spots: Array<[Place, 'read' | 'paper']> = [
        ...Array.from({ length: LIBRARY_CASES }, (_, index): [Place, 'read'] => [CASE_PLACE(index), 'read']),
        [PAPERS_PLACE, 'read'],
        ...[-0.5, 0.5].map((dx): [Place, 'paper'] => [{ x: TABLES[1]!.x + dx, z: TABLES[1]!.z - 0.72, face: { x: TABLES[1]!.x + dx, z: 5 }, sit: true }, 'paper']),
      ]
      const free = spots.filter(([spot]) => spot.x !== where.x || spot.z !== where.z)
      visitors.slice(0, free.length).forEach((visitor, index) => {
        const [spot, action] = free[index]!
        people.push({ id: visitor.id, name: visitor.name, state: 'working', stateLabel: visitor.stateLabel, look: visitor.look, place: spot, action, pick: visitor.pick })
      })
      reading = librarian.state === 'reading'
      screenBusy = librarian.state !== 'idle'
      if (stackSize !== (reading ? Math.min(6, librarian.cited) : 0)) {
        stackSize = reading ? Math.min(6, librarian.cited) : 0
        for (const child of [...stack.children]) {
          child.removeFromParent()
          disposeGeometry(child)
        }
        const pile = new Batch()
        for (let index = 0; index < stackSize; index += 1) {
          pile.add(boxShape(0.24, 0.05, 0.3, 0.008), Object.values(KIND_COLOURS)[index % 8]!, { x: TABLES[0]!.x - 0.05, y: 0.775 + index * 0.052, z: TABLES[0]!.z - 0.1, ry: (index % 3) * 0.12 }, 'matte')
        }
        if (stackSize > 0) stack.add(group(pile, finishes))
      }
      const labels: Record<string, PlaceLabel> = {}
      model.cases.forEach((item, index) => {
        labels[`case-${item.id}`] = {
          at: { x: caseX(index), y: CASE_HEIGHT + 0.25, z: CASE_Z },
          title: item.name,
          detail: t('places.library.documents', { count: item.total }),
          ...(librarian.caseId === item.id && librarian.state !== 'idle' ? { tone: 'busy' as const } : {}),
          pick: 'route:knowledge',
        }
      })
      if (model.cases.length === 0) {
        labels.empty = { at: { x: 0, y: CASE_HEIGHT + 0.25, z: CASE_Z }, title: t('places.library.empty'), pick: 'route:knowledge' }
      }
      // The phone keeps no list of the reference library's papers: their shelf has no sign there.
      if (model.papers.total > 0) labels.papers = { at: { x: PAPERS.x, y: CASE_HEIGHT + 0.25, z: (PAPERS.z0 + PAPERS.z1) / 2 }, title: t('places.library.papers'), detail: t('places.library.paperCount', { count: model.papers.total }), pick: 'route:workspace' }
      if (model.cart.length > 0) {
        const failed = model.cart.filter((book) => book.state === 'failed').length
        labels.cart = {
          at: { x: CART.x, y: 1.1, z: CART.z },
          title: t('places.library.cart'),
          detail: failed > 0 ? t('places.library.failed', { count: failed }) : t('places.library.reading', { count: model.cart.length }),
          tone: failed > 0 ? 'alert' : 'busy',
          pick: 'route:knowledge',
        }
      }
      if (!model.enabled) labels.off = { at: { x: COUNTER.x, y: 1.4, z: COUNTER.z }, title: t('places.library.off'), tone: 'alert', pick: 'route:knowledge' }
      return { people, labels }
    },
    tick(now) {
      lampLight.intensity += ((reading ? (dark ? 5 : 2) : 0) - lampLight.intensity) * (still ? 1 : 0.08)
      screenMaterial.emissive.set(screenBusy ? (dark ? '#3d7bd9' : '#4b8fe6') : c.dim)
      screenMaterial.emissiveIntensity = screenBusy ? 0.9 + (still ? 0 : Math.sin(now * 5) * 0.08) : 0.35
      return false
    },
    dispose() {
      slab.dispose()
      for (const child of [...root.children]) if (child !== books && child !== ribbons) disposeGeometry(child)
      books.geometry.dispose()
      ribbons.geometry.dispose()
      bookMaterial.dispose()
      ribbonMaterial.dispose()
      screenMaterial.dispose()
      lampLight.dispose()
      root.traverse((node) => { if (node instanceof THREE.Mesh && node.material instanceof THREE.MeshBasicMaterial && !node.material.visible) node.material.dispose() })
    },
  }
}

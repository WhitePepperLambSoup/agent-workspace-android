import * as THREE from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'

import { AQUARIUM } from './layout'
import { Batch, boxShape, capsuleShape, sphereShape, type Finishes } from './mesh-kit'

/**
 * A long fish tank on a low cabinet in the studio. What swims in it depends on the model at
 * work: with a DeepSeek model, a blue whale (the "big fat fish") that cruises just under the
 * surface and every few seconds blows a spout of water up out of the tank; with any other model,
 * a few small orange fish. The tank is merged with the furniture; the fish and the spout move.
 */

export type TankFish = 'whale' | 'small'

/** Which fish suit a model id. */
export function fishFor(model: string | null | undefined): TankFish {
  return model && /deepseek/i.test(model) ? 'whale' : 'small'
}

const CENTRE = { x: (AQUARIUM.x0 + AQUARIUM.x1) / 2, z: (AQUARIUM.z0 + AQUARIUM.z1) / 2 }
const WIDTH = AQUARIUM.x1 - AQUARIUM.x0
const DEPTH = AQUARIUM.z1 - AQUARIUM.z0
const CABINET = 0.5
const TANK = 0.62
/** The whale is shown large, so the mark's outline reads from across the room. */
const WHALE_SCALE = 1.4
const WATER_BOTTOM = CABINET + 0.04
const WATER_TOP = CABINET + TANK - 0.04
/** Where each kind swims: the whale with its back just under the surface, small fish mid-water. */
const SWIM_Y: Record<TankFish, number> = { whale: WATER_TOP - 0.165 * WHALE_SCALE, small: CABINET + 0.28 }
/** The spout: every so many seconds, for so long, this many drops. */
const SPOUT_EVERY = 6.5
const SPOUT_FOR = 1.9
const DROPS = 30
const GRAVITY = 2.3

/** The cabinet, the tank's rims and corners, gravel, rocks, weed, bubbles and a lamp bar. */
export function furnishAquarium(batch: Batch, dark: boolean): void {
  const wood = dark ? '#4e3b2c' : '#a5784f'
  batch.within({ x: CENTRE.x, z: CENTRE.z }, () => {
    batch.add(boxShape(WIDTH, CABINET, DEPTH, 0.02), wood, { y: CABINET / 2 }, 'satin')
    for (const side of [-1, 0, 1]) {
      batch.add(boxShape(WIDTH / 3 - 0.05, CABINET - 0.12, 0.01, 0.004), dark ? '#5f4836' : '#bf9468', { x: side * WIDTH / 3, y: CABINET / 2, z: DEPTH / 2 + 0.003 }, 'satin', false)
      batch.add(boxShape(0.1, 0.012, 0.018, 0.005), '#c3c9d2', { x: side * WIDTH / 3, y: CABINET - 0.1, z: DEPTH / 2 + 0.014 }, 'metal', false)
    }
    const top = CABINET
    const inner = { w: WIDTH - 0.06, d: DEPTH - 0.06 }
    // Black rims round the bottom and the open top (the room looks in from above), the corners,
    // and a lamp bar along the back edge with its light underneath.
    batch.add(boxShape(WIDTH - 0.02, 0.024, DEPTH - 0.02, 0.006), '#1d2027', { y: top + 0.012 }, 'satin', false)
    for (const side of [-1, 1]) {
      batch.add(boxShape(WIDTH - 0.02, 0.02, 0.02), '#1d2027', { y: top + TANK - 0.01, z: side * (DEPTH / 2 - 0.02) }, 'satin', false)
      batch.add(boxShape(0.02, 0.02, DEPTH - 0.02), '#1d2027', { x: side * (WIDTH / 2 - 0.02), y: top + TANK - 0.01 }, 'satin', false)
      for (const end of [-1, 1]) batch.add(boxShape(0.018, TANK, 0.018), '#1d2027', { x: side * (WIDTH / 2 - 0.02), y: top + TANK / 2, z: end * (DEPTH / 2 - 0.02) }, 'satin', false)
    }
    batch.add(boxShape(inner.w - 0.1, 0.024, 0.06, 0.008), '#24272e', { y: top + TANK + 0.012, z: -DEPTH / 2 + 0.06 }, 'satin', false)
    batch.add(boxShape(inner.w - 0.16, 0.006, 0.04), '#e6f8ff', { y: top + TANK - 0.002, z: -DEPTH / 2 + 0.06 }, 'glow', false)
    batch.add(boxShape(inner.w, 0.04, inner.d), dark ? '#b8a27a' : '#d9c7a0', { y: top + 0.045 }, 'matte', false)
    for (const [x, z, size, grey] of [[-0.55, -0.08, 0.1, '#7d7a74'], [-0.44, 0.08, 0.065, '#8f8b83'], [0.5, 0.1, 0.08, '#86827a']] as const) {
      batch.add(sphereShape(size, 10, 8), grey, { x, y: top + 0.075, z, sx: 1.3, sy: 0.65 }, 'matte', false)
    }
    for (const [x, z, height, lean] of [[-0.68, -0.12, 0.34, 0.1], [-0.62, 0.02, 0.26, -0.15], [-0.5, -0.14, 0.2, 0.12], [0.6, -0.12, 0.36, -0.08], [0.66, 0.04, 0.28, 0.12], [0.55, 0.14, 0.2, 0.2]] as const) {
      batch.add(capsuleShape(0.012, height, 8), dark ? '#3f7a52' : '#4f9a63', { x, y: top + 0.065 + height / 2, z, rz: lean }, 'matte', false)
    }
    for (const [x, y, z] of [[0.62, 0.18, -0.02], [0.65, 0.28, -0.03], [0.63, 0.37, -0.01]] as const) {
      batch.add(sphereShape(0.01, 8, 6), '#e6fbff', { x, y: top + y, z }, 'glow', false)
    }
  })
}

interface FishShape { body: THREE.BufferGeometry; tail: THREE.BufferGeometry; tailAt: readonly [number, number] }

/**
 * The whale: a real whale's build in the DeepSeek mark's manner. The body is lofted along x, round
 * and blunt at the head, tapering into the tail stock, which rises at the back as the mark's tail
 * does; it is the mark's blue, with its white crescent of a mouth running back along the jaw.
 */
const WHALE = { length: 0.48, radius: 0.11, tall: 1.05, wide: 0.86, rise: 0.1 }

const whaleRadius = (s: number): number => s < 0.35
  ? WHALE.radius * Math.sqrt(Math.max(0, 1 - (1 - s / 0.35) ** 2.2))
  : WHALE.radius * (1 - 0.86 * ((s - 0.35) / 0.65) ** 1.6)
const whaleCentre = (s: number): [number, number] => [WHALE.length / 2 - s * WHALE.length, s > 0.55 ? WHALE.rise * ((s - 0.55) / 0.45) ** 2 : 0]

/** A point on the whale's skin: `s` along it (0 the snout, 1 the tail), `v` from the belly (-1) to the back (1), on one side. */
function whaleSkin(s: number, v: number, side: number): THREE.Vector3 {
  const [x, y] = whaleCentre(s)
  const r = whaleRadius(s)
  return new THREE.Vector3(x, y + v * r * WHALE.tall, side * Math.sqrt(Math.max(0, 1 - v * v)) * r * WHALE.wide)
}

/** The blowhole, where the spout starts (before the whale's scale). */
const BLOWHOLE = whaleSkin(0.22, 1, 0)

/** Whether a point of the skin is in the white crescent of the mouth: thick at the snout, thinning back along the jaw. */
function inMouth(s: number, v: number): boolean {
  // High on the side, so the room (which looks down on the tank) sees it.
  if (s > 0.62) return false
  const upper = 0.12 - 0.82 * s
  const lower = upper - (0.07 + 0.3 * (1 - s / 0.62) ** 0.6)
  return v <= upper && v >= lower
}

function whaleBodyGeometry(blue: string, white: string): THREE.BufferGeometry {
  const rings = 72
  const around = 48
  const positions: number[] = []
  const colours: number[] = []
  const blueColour = new THREE.Color(blue)
  const whiteColour = new THREE.Color(white)
  for (let ring = 0; ring <= rings; ring += 1) {
    const s = ring / rings
    const [x, y] = whaleCentre(s)
    const r = whaleRadius(s)
    for (let step = 0; step <= around; step += 1) {
      const angle = (step / around) * Math.PI * 2
      const v = Math.cos(angle)
      positions.push(x, y + v * r * WHALE.tall, Math.sin(angle) * r * WHALE.wide)
      const colour = inMouth(s, v) ? whiteColour : blueColour
      colours.push(colour.r, colour.g, colour.b)
    }
  }
  const index: number[] = []
  for (let ring = 0; ring < rings; ring += 1) {
    for (let step = 0; step < around; step += 1) {
      const a = ring * (around + 1) + step
      const b = a + around + 1
      index.push(a, b, a + 1, a + 1, b, b + 1)
    }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3))
  geometry.setIndex(index)
  geometry.computeVertexNormals()
  const flat = geometry.toNonIndexed()
  geometry.dispose()
  return flat
}

/** One merged geometry of a batch's parts (all of one finish). */
function merged(build: (batch: Batch) => void): THREE.BufferGeometry {
  const batch = new Batch()
  build(batch)
  const [part] = batch.build()
  return part!.geometry
}

/** The fish of every room, made once for the scene. Each faces +x. */
export interface AquariumKit {
  whale: FishShape
  small: FishShape
  /** The water's shape, and one drop of the whale's spout. */
  water: THREE.BufferGeometry
  drop: THREE.BufferGeometry
  dispose(): void
}

export function createAquariumKit(): AquariumKit {
  const blue = '#4d6bfe'
  const white = '#f6f8ff'
  // The eye, the long flippers, a small dorsal fin and the blowhole; the flukes are the tail.
  const extras = merged((batch) => {
    for (const side of [-1, 1]) {
      const eye = whaleSkin(0.33, 0.14, side)
      batch.add(sphereShape(0.017, 16, 12), white, { x: eye.x, y: eye.y, z: eye.z, sz: 0.45 })
      batch.add(sphereShape(0.0095, 12, 8), '#14171f', { x: eye.x + 0.004, y: eye.y + 0.001, z: eye.z + side * 0.006, sz: 0.5 })
      const flipper = whaleSkin(0.42, -0.55, side)
      batch.add(sphereShape(1, 20, 12), blue, { x: flipper.x - 0.045, y: flipper.y - 0.025, z: flipper.z + side * 0.03, ry: side * 0.5, rz: 0.45, sx: 0.075, sy: 0.011, sz: 0.026 })
    }
    const fin = whaleSkin(0.74, 1, 0)
    batch.add(sphereShape(1, 14, 10), blue, { x: fin.x, y: fin.y + 0.008, rz: 0.6, sx: 0.032, sy: 0.022, sz: 0.007 })
    batch.add(sphereShape(1, 10, 8), '#26338a', { x: BLOWHOLE.x, y: BLOWHOLE.y, sx: 0.012, sy: 0.004, sz: 0.008 })
  })
  const body = mergeGeometries([whaleBodyGeometry(blue, white), extras], false)!
  extras.dispose()
  const [tailX, tailY] = whaleCentre(1)
  const whale: FishShape = {
    body,
    tail: merged((batch) => {
      batch.add(sphereShape(1, 16, 12), blue, { sx: 0.028, sy: 0.02, sz: 0.02 })
      for (const side of [-1, 1]) batch.add(sphereShape(1, 24, 14), blue, { x: -0.045, y: 0.014, z: side * 0.062, ry: side * 0.55, rz: 0.55, sx: 0.05, sy: 0.008, sz: 0.085 })
    }),
    tailAt: [tailX, tailY],
  }
  // A small orange fish with a white band, for every other model.
  const small: FishShape = {
    body: merged((batch) => {
      batch.add(sphereShape(1, 16, 12), '#ff8a3d', { sx: 0.05, sy: 0.034, sz: 0.022 })
      batch.add(sphereShape(1, 12, 10), '#fbfaf6', { x: 0.012, sx: 0.01, sy: 0.035, sz: 0.0235 })
      batch.add(sphereShape(1, 10, 8), '#ff7a2a', { y: 0.032, x: -0.005, sx: 0.02, sy: 0.012, sz: 0.004 })
      for (const side of [-1, 1]) batch.add(sphereShape(0.006, 8, 6), '#14171f', { x: 0.033, y: 0.008, z: side * 0.016 })
    }),
    tail: merged((batch) => {
      batch.add(sphereShape(1, 12, 8), '#ff9a55', { x: -0.02, sx: 0.024, sy: 0.026, sz: 0.004 })
    }),
    tailAt: [-0.045, 0],
  }
  const water = new THREE.BoxGeometry(WIDTH - 0.05, WATER_TOP - WATER_BOTTOM, DEPTH - 0.05)
  const drop = new THREE.SphereGeometry(0.018, 10, 8)
  return {
    whale,
    small,
    water,
    drop,
    dispose() {
      for (const shape of [whale, small]) {
        shape.body.dispose()
        shape.tail.dispose()
      }
      water.dispose()
      drop.dispose()
    },
  }
}

interface Swimmer { root: THREE.Group; tail: THREE.Object3D; phase: number; speed: number; reach: number; depth: number; bob: number; heading: number }

/** The fish of one room, in its tank: one kind shown at a time. */
export interface Aquarium {
  setFish(kind: TankFish): void
  /** One frame of swimming; `still` (reduced motion) keeps them in place and the spout off. */
  tick(now: number, dt: number, still: boolean): void
  dispose(): void
}

export function placeAquarium(kit: AquariumKit, finishes: Finishes, group: THREE.Group, dark: boolean): Aquarium {
  // The water: clear enough to see the fish through, tinted, with a soft sheen.
  const water = new THREE.MeshStandardMaterial({ color: dark ? '#4a9fd0' : '#8fd6f2', transparent: true, opacity: 0.2, roughness: 0.05, metalness: 0, depthWrite: false })
  const waterMesh = new THREE.Mesh(kit.water, water)
  waterMesh.position.set(CENTRE.x, (WATER_BOTTOM + WATER_TOP) / 2, CENTRE.z)
  waterMesh.renderOrder = 1
  group.add(waterMesh)

  const make = (shape: FishShape, kind: TankFish, at: { phase: number; speed: number; reach: number; depth: number; bob: number; scale?: number }): Swimmer => {
    const root = new THREE.Group()
    root.add(new THREE.Mesh(shape.body, finishes.matte))
    const tail = new THREE.Group()
    tail.position.set(shape.tailAt[0], shape.tailAt[1], 0)
    tail.add(new THREE.Mesh(shape.tail, finishes.matte))
    root.add(tail)
    root.scale.setScalar(at.scale ?? 1)
    root.position.set(CENTRE.x, SWIM_Y[kind], CENTRE.z)
    group.add(root)
    return { root, tail, ...at, heading: 0 }
  }
  const schools: Record<TankFish, Swimmer[]> = {
    whale: [make(kit.whale, 'whale', { phase: 0, speed: 0.18, reach: 0.36, depth: 0.02, bob: 0.008, scale: WHALE_SCALE })],
    small: [
      make(kit.small, 'small', { phase: 0.3, speed: 0.55, reach: 0.55, depth: 0.1, bob: 0.06 }),
      make(kit.small, 'small', { phase: 2.1, speed: 0.47, reach: 0.5, depth: 0.08, bob: 0.06, scale: 0.85 }),
      make(kit.small, 'small', { phase: 4.0, speed: 0.6, reach: 0.52, depth: 0.12, bob: 0.06, scale: 0.9 }),
    ],
  }

  // The spout: drops thrown up from the blowhole, drawn as one instanced mesh.
  const dropMaterial = new THREE.MeshBasicMaterial({ color: '#e8f7ff', toneMapped: false, transparent: true, opacity: 0.9 })
  const spout = new THREE.InstancedMesh(kit.drop, dropMaterial, DROPS)
  spout.frustumCulled = false
  spout.visible = false
  group.add(spout)
  // Two plumes leaning apart, a V as a baleen whale blows, with drops of a few sizes.
  const drops = Array.from({ length: DROPS }, (_, index) => {
    const plume = index % 2 === 0 ? 1 : -1
    return {
      delay: (index / DROPS) * 0.6,
      up: 1.3 + ((index * 37) % 7) * 0.05,
      side: (((index * 53) % 11) / 11 - 0.5) * 0.16,
      across: plume * (0.12 + ((index * 29) % 5) * 0.025),
      size: 0.8 + ((index * 17) % 5) * 0.12,
    }
  })
  const origin = new THREE.Vector3()
  const place = new THREE.Matrix4()
  let spouting = -1

  let shown: TankFish = 'small'
  const show = (kind: TankFish): void => {
    shown = kind
    for (const [name, fish] of Object.entries(schools)) for (const swimmer of fish) swimmer.root.visible = name === kind
    spout.visible = false
  }
  show(shown)
  return {
    setFish(kind) {
      if (kind !== shown) show(kind)
    },
    tick(now, dt, still) {
      const whale = shown === 'whale'
      for (const [index, swimmer] of schools[shown].entries()) {
        const t = still ? swimmer.phase : now * swimmer.speed + swimmer.phase
        // Back and forth along the tank, a gentle rise and fall, turning round at the ends.
        const x = Math.sin(t) * swimmer.reach
        const facing = Math.cos(t) >= 0 ? 0 : Math.PI
        swimmer.heading += (facing - swimmer.heading) * (still ? 1 : Math.min(1, dt * 2.5))
        swimmer.root.position.set(CENTRE.x + x, SWIM_Y[shown] + Math.sin(t * 2.3 + index) * swimmer.bob, CENTRE.z + Math.sin(t * 1.3 + index * 2) * swimmer.depth)
        swimmer.root.rotation.y = -swimmer.heading
        if (whale) {
          // The raised tail sways a little and the body rocks with it.
          const beat = still ? 0 : Math.sin(now * 2.2)
          swimmer.tail.rotation.z = beat * 0.14
          swimmer.root.rotation.z = beat * 0.03
        } else {
          swimmer.tail.rotation.y = still ? 0 : Math.sin(now * 11 + index) * 0.4
        }
      }
      if (!whale || still) {
        spout.visible = false
        return
      }
      // Every few seconds the whale blows: drops rise from the blowhole above the surface and fall.
      const cycle = now % SPOUT_EVERY
      if (cycle > SPOUT_FOR) {
        spout.visible = false
        spouting = -1
        return
      }
      const whaleRoot = schools.whale[0]!.root
      const round = Math.floor(now / SPOUT_EVERY)
      if (spouting !== round) {
        spouting = round
        origin.copy(BLOWHOLE).multiplyScalar(whaleRoot.scale.x).applyAxisAngle(THREE.Object3D.DEFAULT_UP, whaleRoot.rotation.y).add(whaleRoot.position)
      }
      spout.visible = true
      for (const [index, drop] of drops.entries()) {
        const t = cycle - drop.delay
        const y = origin.y + drop.up * t - (GRAVITY / 2) * t * t
        const size = t > 0 && y > WATER_TOP ? drop.size : 0
        place.makeScale(size, size, size)
        place.setPosition(origin.x + drop.side * t, y, origin.z + drop.across * t)
        spout.setMatrixAt(index, place)
      }
      spout.instanceMatrix.needsUpdate = true
    },
    dispose() {
      water.dispose()
      dropMaterial.dispose()
      spout.dispose()
    },
  }
}

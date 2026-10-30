import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'

/**
 * Tools for building the studio's models cheaply: many small parts with their colours baked
 * into the vertices are merged into one mesh per surface finish, so a room of hundreds of parts
 * is drawn in a handful of calls, and the floors of the building share the same buffers.
 */

/** How a surface takes the light: each finish is one material and one draw call. */
export type Finish = 'matte' | 'satin' | 'metal' | 'glass' | 'glow'

export type Finishes = Record<Finish, THREE.Material>

/** One set of materials per scene, shared by every room and person in it. */
export function createFinishes(): Finishes {
  return {
    matte: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.84, metalness: 0 }),
    satin: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.42, metalness: 0.05 }),
    metal: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.38, metalness: 0.55 }),
    glass: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.08, metalness: 0.1, transparent: true, opacity: 0.55, depthWrite: false }),
    // Lit from within: screens off, indicator lights, the night sky.
    glow: new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false }),
  }
}

export function disposeFinishes(finishes: Finishes): void {
  for (const material of Object.values(finishes)) material.dispose()
}

const cache = new Map<string, THREE.BufferGeometry>()

function cached(key: string, make: () => THREE.BufferGeometry): THREE.BufferGeometry {
  let geometry = cache.get(key)
  if (!geometry) {
    geometry = make()
    cache.set(key, geometry)
  }
  return geometry
}

/** Below this a rounded edge cannot be seen at the studio's scale, and costs 9 times the triangles. */
const VISIBLE_ROUNDING = 0.02

/**
 * A box, its edges bevelled by `radius` where that shows (one segment: a soft edge at a ninth of
 * a fully rounded box's triangles). Shapes are made once and reused.
 */
export function boxShape(width: number, height: number, depth: number, radius = 0): THREE.BufferGeometry {
  const r = Math.min(radius, width / 2, height / 2, depth / 2)
  return cached(`box:${width}:${height}:${depth}:${r}`, () => (r >= VISIBLE_ROUNDING ? new RoundedBoxGeometry(width, height, depth, 1, r) : new THREE.BoxGeometry(width, height, depth)))
}

export function cylinderShape(top: number, bottom: number, height: number, segments = 16): THREE.BufferGeometry {
  return cached(`cyl:${top}:${bottom}:${height}:${segments}`, () => new THREE.CylinderGeometry(top, bottom, height, segments))
}

export function sphereShape(radius: number, width = 12, height = 8): THREE.BufferGeometry {
  return cached(`sph:${radius}:${width}:${height}`, () => new THREE.SphereGeometry(radius, width, height))
}

export function coneShape(radius: number, height: number, segments = 8): THREE.BufferGeometry {
  return cached(`cone:${radius}:${height}:${segments}`, () => new THREE.ConeGeometry(radius, height, segments))
}

export function torusShape(radius: number, tube: number, arc = Math.PI * 2, radial = 8, tubular = 24): THREE.BufferGeometry {
  return cached(`torus:${radius}:${tube}:${arc}:${radial}:${tubular}`, () => new THREE.TorusGeometry(radius, tube, radial, tubular, arc))
}

export function dodecaShape(radius: number): THREE.BufferGeometry {
  return cached(`dodeca:${radius}`, () => new THREE.DodecahedronGeometry(radius, 0))
}

/** Where a part goes: a position, and optionally a rotation (radians) and a scale. */
export interface Placement {
  x?: number
  y?: number
  z?: number
  rx?: number
  ry?: number
  rz?: number
  sx?: number
  sy?: number
  sz?: number
}

const matrix = new THREE.Matrix4()
const quaternion = new THREE.Quaternion()
const euler = new THREE.Euler()
const position = new THREE.Vector3()
const scale = new THREE.Vector3()
const colour = new THREE.Color()

function placed(shape: THREE.BufferGeometry, at: Placement, color: string): THREE.BufferGeometry {
  const geometry = (shape.index ? shape.toNonIndexed() : shape.clone())
  geometry.deleteAttribute('uv')
  position.set(at.x ?? 0, at.y ?? 0, at.z ?? 0)
  quaternion.setFromEuler(euler.set(at.rx ?? 0, at.ry ?? 0, at.rz ?? 0))
  scale.set(at.sx ?? 1, at.sy ?? 1, at.sz ?? 1)
  geometry.applyMatrix4(matrix.compose(position, quaternion, scale))
  // Colour management turns the sRGB value into the linear one vertex colours are read in.
  colour.set(color)
  const count = geometry.getAttribute('position').count
  const colours = new Float32Array(count * 3)
  for (let index = 0; index < count; index += 1) {
    colours[index * 3] = colour.r
    colours[index * 3 + 1] = colour.g
    colours[index * 3 + 2] = colour.b
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3))
  return geometry
}

/** Parts gathered for merging: by finish, and whether they cast shadows. */
export class Batch {
  private readonly groups = new Map<string, THREE.BufferGeometry[]>()

  add(shape: THREE.BufferGeometry, color: string, at: Placement = {}, finish: Finish = 'matte', shadow = true): void {
    const key = `${finish}|${shadow ? 1 : 0}`
    let list = this.groups.get(key)
    if (!list) {
      list = []
      this.groups.set(key, list)
    }
    list.push(placed(shape, at, color))
  }

  /** One geometry per finish and shadow flag; the parts' own buffers are freed. */
  build(): Array<{ geometry: THREE.BufferGeometry; finish: Finish; shadow: boolean }> {
    const built: Array<{ geometry: THREE.BufferGeometry; finish: Finish; shadow: boolean }> = []
    for (const [key, list] of this.groups) {
      const [finish, shadow] = key.split('|') as [Finish, string]
      const geometry = mergeGeometries(list, false)
      for (const part of list) part.dispose()
      if (!geometry) continue
      geometry.computeBoundingSphere()
      built.push({ geometry, finish, shadow: shadow === '1' })
    }
    this.groups.clear()
    return built
  }
}

/** Meshes over merged geometry, sharing the scene's finishes. */
export function meshesOf(parts: ReturnType<Batch['build']>, finishes: Finishes, receive = true): THREE.Mesh[] {
  return parts.map(({ geometry, finish, shadow }) => {
    const mesh = new THREE.Mesh(geometry, finishes[finish])
    mesh.castShadow = shadow && finish !== 'glass' && finish !== 'glow'
    mesh.receiveShadow = receive && finish !== 'glow'
    mesh.matrixAutoUpdate = false
    mesh.updateMatrix()
    return mesh
  })
}

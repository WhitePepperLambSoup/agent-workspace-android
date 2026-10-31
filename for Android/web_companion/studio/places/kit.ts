import * as THREE from 'three'

import type { Box } from '../layout'
import { Batch, boxShape, cylinderShape, dodecaShape, meshesOf, torusShape, type Finishes } from '../mesh-kit'

/**
 * Pieces the campus's places share with the studio's look: floors, the two walls of a room open
 * toward the viewer, plants, desks with a screen. All in metres, x to the right, z toward the
 * viewer, the floor at y = 0.
 */

export const ROOM_BOX: Box = { x0: -6, x1: 6, z0: -4.5, z1: 4.5 }
export const ROOM_HEIGHT = 2.6
const WALL = 0.18

export type FloorStyle = 'wood' | 'tile' | 'raised' | 'stone' | 'dirt' | 'lawn' | 'carpet'

export function palette(dark: boolean) {
  return dark
    ? { wall: '#4d5466', wallLow: '#434a5b', trim: '#262a33', skirt: '#2b2f38', sky: '#1d2e5c', frame: '#2c303a', wood: '#4e3b2c', woodLight: '#5f4836', deskTop: '#6b5a4a', deskFrame: '#3a3f4b', chair: '#2f3442', seat: '#3d4456', pot: '#8a5a44', soil: '#3a2a20', leaf: '#4f8a5b', leafLight: '#6aa86f', metal: '#5d6470', dim: '#203048' }
    : { wall: '#f1ece4', wallLow: '#e6ddd0', trim: '#d9cfc1', skirt: '#e9e4dc', sky: '#bfe3ff', frame: '#e8e2d8', wood: '#a5784f', woodLight: '#bf9468', deskTop: '#e8dccb', deskFrame: '#9aa1ab', chair: '#4c5566', seat: '#5c677c', pot: '#c1785a', soil: '#5a4030', leaf: '#4f8a5b', leafLight: '#6aa86f', metal: '#9aa1ab', dim: '#203048' }
}

function canvas(size: number, paint: (context: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const element = document.createElement('canvas')
  element.width = size
  element.height = size
  paint(element.getContext('2d')!)
  const texture = new THREE.CanvasTexture(element)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  return texture
}

/** A floor's pattern, drawn once. */
function floorTexture(style: FloorStyle, dark: boolean): THREE.CanvasTexture {
  if (style === 'wood') {
    return canvas(512, (context) => {
      context.fillStyle = dark ? '#76604b' : '#c9a37c'
      context.fillRect(0, 0, 512, 512)
      for (let row = 0; row < 8; row += 1) {
        const offset = (row % 2) * 128
        for (let column = -1; column < 3; column += 1) {
          const shade = ((row * 7 + column * 3) % 5) / 5
          context.fillStyle = dark ? `rgba(0,0,0,${0.08 + shade * 0.08})` : `rgba(90,55,25,${0.05 + shade * 0.07})`
          context.fillRect(column * 256 + offset + 2, row * 64 + 2, 252, 60)
        }
      }
    })
  }
  if (style === 'raised') {
    // Raised floor tiles of a server room, some of them perforated for the cold air.
    return canvas(512, (context) => {
      context.fillStyle = dark ? '#5a606c' : '#c9ced6'
      context.fillRect(0, 0, 512, 512)
      for (let row = 0; row < 4; row += 1) {
        for (let column = 0; column < 4; column += 1) {
          context.fillStyle = dark ? '#646b78' : '#d6dbe2'
          context.fillRect(column * 128 + 3, row * 128 + 3, 122, 122)
          if ((row + column) % 3 === 0) {
            context.fillStyle = dark ? '#3e434d' : '#9aa1ab'
            for (let y = 0; y < 8; y += 1) for (let x = 0; x < 8; x += 1) context.fillRect(column * 128 + 14 + x * 13, row * 128 + 14 + y * 13, 5, 5)
          }
        }
      }
    })
  }
  if (style === 'tile' || style === 'stone') {
    return canvas(512, (context) => {
      context.fillStyle = style === 'stone' ? (dark ? '#6d6a66' : '#e4ded4') : (dark ? '#5d6470' : '#dfe2e6')
      context.fillRect(0, 0, 512, 512)
      const size = style === 'stone' ? 256 : 128
      for (let row = 0; row < 512 / size; row += 1) {
        for (let column = 0; column < 512 / size; column += 1) {
          const shade = ((row * 5 + column * 3) % 4) / 4
          context.fillStyle = dark ? `rgba(255,255,255,${0.02 + shade * 0.03})` : `rgba(0,0,0,${0.02 + shade * 0.03})`
          context.fillRect(column * size + 2, row * size + 2, size - 4, size - 4)
          if (style === 'stone') {
            context.strokeStyle = dark ? 'rgba(255,255,255,0.05)' : 'rgba(120,110,95,0.12)'
            context.beginPath()
            context.moveTo(column * size + size * 0.2, row * size + size * (0.3 + shade * 0.4))
            context.bezierCurveTo(column * size + size * 0.5, row * size + size * 0.1, column * size + size * 0.6, row * size + size * 0.9, column * size + size * 0.9, row * size + size * 0.6)
            context.stroke()
          }
        }
      }
    })
  }
  if (style === 'carpet') {
    return canvas(256, (context) => {
      context.fillStyle = dark ? '#3c4456' : '#c8cfdb'
      context.fillRect(0, 0, 256, 256)
      for (let index = 0; index < 900; index += 1) {
        context.fillStyle = dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.04)'
        context.fillRect((index * 97) % 256, (index * 61) % 256, 2, 2)
      }
    })
  }
  // Dirt of a building site, or lawn.
  const lawn = style === 'lawn'
  return canvas(256, (context) => {
    context.fillStyle = lawn ? (dark ? '#2f4a3a' : '#9cc49a') : (dark ? '#5a4a3a' : '#c8b08a')
    context.fillRect(0, 0, 256, 256)
    for (let index = 0; index < 700; index += 1) {
      const light = (index * 13) % 3 === 0
      context.fillStyle = light ? (dark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.18)') : (dark ? 'rgba(0,0,0,0.12)' : 'rgba(80,60,30,0.1)')
      context.fillRect((index * 89) % 256, (index * 47) % 256, 2 + (index % 3), 2)
    }
  })
}

/** A floor slab over the box, its pattern repeated every `tile` metres. */
export function floor(style: FloorStyle, dark: boolean, box: Box, tile = 4): { mesh: THREE.Mesh; dispose(): void } {
  const width = box.x1 - box.x0
  const depth = box.z1 - box.z0
  const texture = floorTexture(style, dark)
  texture.repeat.set(width / tile, depth / tile)
  const geometry = new THREE.BoxGeometry(width, 0.24, depth)
  geometry.translate((box.x0 + box.x1) / 2, -0.12, (box.z0 + box.z1) / 2)
  const material = new THREE.MeshStandardMaterial({ map: texture, roughness: style === 'stone' || style === 'tile' ? 0.55 : 0.85 })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.receiveShadow = true
  mesh.matrixAutoUpdate = false
  return { mesh, dispose() { geometry.dispose(); material.dispose(); texture.dispose() } }
}

/** The back and left walls of a room, with skirting and rails; a window on the back wall if asked. */
export function walls(batch: Batch, dark: boolean, colours: { wall?: string; low?: string } = {}, window?: { x: number; width: number }): void {
  const c = palette(dark)
  const box = ROOM_BOX
  const width = box.x1 - box.x0
  const depth = box.z1 - box.z0
  const wall = colours.wall ?? c.wall
  const low = colours.low ?? c.wallLow
  const lowWall = 0.95
  batch.add(boxShape(width + 0.1, 0.12, depth + 0.1), c.skirt, { y: -0.3 }, 'matte', false)
  batch.add(boxShape(width, lowWall, WALL + 0.02), low, { y: lowWall / 2, z: box.z0 - WALL / 2 })
  batch.add(boxShape(width, ROOM_HEIGHT - lowWall, WALL), wall, { y: lowWall + (ROOM_HEIGHT - lowWall) / 2, z: box.z0 - WALL / 2 })
  batch.add(boxShape(WALL + 0.02, lowWall, depth + WALL), low, { x: box.x0 - WALL / 2, y: lowWall / 2, z: -WALL / 2 })
  batch.add(boxShape(WALL, ROOM_HEIGHT - lowWall, depth + WALL), wall, { x: box.x0 - WALL / 2, y: lowWall + (ROOM_HEIGHT - lowWall) / 2, z: -WALL / 2 })
  for (const [y, h] of [[0.06, 0.12], [lowWall, 0.04], [ROOM_HEIGHT - 0.02, 0.05]] as const) {
    batch.add(boxShape(width, h, 0.04), c.trim, { y, z: box.z0 + 0.02 }, 'satin', false)
    batch.add(boxShape(0.04, h, depth), c.trim, { x: box.x0 + 0.02, y }, 'satin', false)
  }
  if (window) {
    batch.add(boxShape(window.width + 0.2, 1.36, 0.06, 0.02), c.frame, { x: window.x, y: 1.62, z: box.z0 + 0.03 }, 'satin', false)
    batch.add(boxShape(window.width, 1.14, 0.02), c.sky, { x: window.x, y: 1.62, z: box.z0 + 0.065 }, 'glow', false)
    const panes = Math.max(2, Math.round(window.width / 1.1))
    for (let index = 1; index < panes; index += 1) {
      batch.add(boxShape(0.06, 1.16, 0.05), c.frame, { x: window.x - window.width / 2 + (window.width / panes) * index, y: 1.62, z: box.z0 + 0.08 }, 'satin', false)
    }
    batch.add(boxShape(window.width + 0.3, 0.05, 0.16, 0.015), c.trim, { x: window.x, y: 0.92, z: box.z0 + 0.08 }, 'satin', false)
  }
}

export function plant(batch: Batch, dark: boolean, x: number, z: number, tall = false): void {
  const c = palette(dark)
  batch.add(cylinderShape(0.21, 0.15, 0.38, 18), c.pot, { x, y: 0.19, z }, 'satin')
  batch.add(torusShape(0.205, 0.02, Math.PI * 2, 6, 18), c.pot, { x, y: 0.38, z, rx: Math.PI / 2 }, 'satin', false)
  batch.add(cylinderShape(0.19, 0.19, 0.02, 16), c.soil, { x, y: 0.36, z }, 'matte', false)
  if (tall) batch.add(cylinderShape(0.02, 0.025, 0.7, 6), '#5b4636', { x, y: 0.7, z }, 'matte')
  const base = tall ? 1.05 : 0.58
  for (const [dx, dy, dz, r, light] of [[0, 0, 0, 0.3, false], [0.14, 0.12, 0.05, 0.2, true], [-0.12, 0.16, -0.06, 0.18, true], [0.02, 0.3, 0.02, 0.17, false]] as const) {
    batch.add(dodecaShape(r * (tall ? 0.9 : 1)), light ? c.leafLight : c.leaf, { x: x + dx, y: base + dy, z: z + dz, ry: dx * 7 }, 'matte')
  }
}

/**
 * A desk facing +z (the seat behind it at z - 0.75) with a monitor whose back faces the viewer,
 * a keyboard and an office chair. Returns where the screen goes.
 */
export function desk(batch: Batch, dark: boolean, x: number, z: number, width = 1.2): THREE.Vector3 {
  const c = palette(dark)
  const depth = 0.7
  const seatZ = z - 0.75
  batch.add(boxShape(width, 0.045, depth, 0.015), c.deskTop, { x, y: 0.645, z }, 'satin')
  for (const side of [-1, 1]) batch.add(boxShape(0.04, 0.62, depth - 0.06, 0.01), c.deskFrame, { x: x + side * (width / 2 - 0.05), y: 0.31, z }, 'metal')
  batch.add(boxShape(0.22, 0.014, 0.14, 0.006), '#2a2d35', { x, y: 0.674, z: z + 0.2 }, 'metal')
  batch.add(boxShape(0.04, 0.2, 0.03), '#5d6470', { x, y: 0.77, z: z + 0.22 }, 'metal')
  batch.add(boxShape(0.64, 0.4, 0.035, 0.014), '#1d2027', { x, y: 1.0, z: z + 0.2 }, 'satin')
  batch.add(boxShape(0.38, 0.018, 0.13, 0.006), '#2a2d35', { x, y: 0.676, z: z - 0.12 }, 'satin')
  batch.add(boxShape(0.46, 0.07, 0.44, 0.03), c.seat, { x, y: 0.29, z: seatZ }, 'matte')
  batch.add(boxShape(0.44, 0.46, 0.06, 0.03), c.chair, { x, y: 0.62, z: seatZ - 0.23, rx: -0.08 }, 'matte')
  batch.add(cylinderShape(0.025, 0.025, 0.2, 10), '#5d6470', { x, y: 0.16, z: seatZ }, 'metal')
  batch.add(cylinderShape(0.2, 0.22, 0.03, 12), '#3a3f4b', { x, y: 0.03, z: seatZ }, 'metal', false)
  return new THREE.Vector3(x, 1.0, z + 0.18)
}

export const SCREEN = boxShape(0.58, 0.34, 0.008)

/** The batch's meshes in a group, for a place's root. */
export function group(batch: Batch, finishes: Finishes): THREE.Group {
  const result = new THREE.Group()
  for (const mesh of meshesOf(batch.build(), finishes)) result.add(mesh)
  return result
}

/**
 * Disposes every geometry under the object (its materials belong to the scene), except shapes
 * from mesh-kit's cache, which are marked `shared`.
 */
export function disposeGeometry(object: THREE.Object3D): void {
  object.traverse((node) => { if (node instanceof THREE.Mesh && !node.userData.shared) node.geometry.dispose() })
}

/** A hashed number in 0..1 from text, for steady choices (colours, small offsets). */
export function hashed(text: string, salt = 0): number {
  let value = 2166136261 ^ salt
  for (const char of text) value = Math.imul(value ^ char.codePointAt(0)!, 16777619)
  return ((value >>> 0) % 10007) / 10007
}

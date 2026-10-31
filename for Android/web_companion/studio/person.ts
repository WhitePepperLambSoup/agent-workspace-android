import * as THREE from 'three'

import type { ActorLook } from './cast'
import type { Place, Point } from './layout'
import { Batch, boxShape, coneShape, cylinderShape, sphereShape, torusShape, type Finishes } from './mesh-kit'

/** What a person's body does where they are; walking is handled by the move itself. */
export type Action = 'rest' | 'type' | 'read' | 'think' | 'write' | 'talk' | 'raise' | 'cheer' | 'slump' | 'sip' | 'operate'
  | 'browse' | 'paper' | 'gaze' | 'carry'

const WALK_SPEED = 1.35
const TURN_SPEED = 8
/** Standing hip height; seated, the hips drop to just above a low chair. */
const HIP = 0.5
const SIT_DROP = 0.2

interface Limb {
  upper: THREE.Group
  lower: THREE.Group
  /** The hand or foot end of the lower part, where a held prop goes. */
  end: THREE.Group
}

function shade(color: string, amount: number): string {
  return `#${new THREE.Color(color).offsetHSL(0, 0, amount).getHexString()}`
}

/**
 * A small person with rounded blocky parts, like the figures of a toy office. Each moving part
 * is one mesh with its colours in the vertices, so a person costs about a dozen draw calls.
 */
export class Person {
  readonly root = new THREE.Group()
  readonly id: string
  readonly position: Point
  heading = 0
  path: Point[] = []
  place: Place | null = null
  private doing: Action = 'rest'
  /** When the action last changed or the person last came to a stop, for poses that start with a move. */
  private changedAt = 0
  private settledAt = 0
  /** Seated (0..1, eased) and the walk cycle's phase. */
  private sit = 0
  private stride = 0
  private moving = false
  private blinkAt: number
  private cheerUntil = 0
  private readonly body = new THREE.Group()
  private readonly head = new THREE.Group()
  private readonly eyes: THREE.Mesh
  private readonly legs: [Limb, Limb]
  private readonly arms: [Limb, Limb]
  private readonly book: THREE.Mesh
  private readonly cup: THREE.Mesh
  private readonly marker: THREE.Mesh
  private readonly paper: THREE.Mesh
  private readonly pages: THREE.Mesh
  private readonly geometries: THREE.BufferGeometry[] = []
  private readonly finishes: Finishes
  private readonly phase: number

  constructor(id: string, look: ActorLook, start: Point, accent: string, finishes: Finishes) {
    this.id = id
    this.finishes = finishes
    this.position = { ...start }
    this.phase = (id.length * 1.7) % (Math.PI * 2)
    this.blinkAt = 1 + Math.random() * 3
    const shoe = '#2a2a2e'

    // Legs: thigh and shin with the shoe, pivoting at the hip and the knee.
    this.legs = [-0.085, 0.085].map((x) => {
      const leg = this.limb(0.24, 0.2,
        (batch) => batch.add(boxShape(0.13, 0.25, 0.13, 0.035), look.pants, { y: -0.12 }),
        (batch) => {
          batch.add(boxShape(0.12, 0.2, 0.12, 0.03), look.pants, { y: -0.1 })
          batch.add(boxShape(0.135, 0.065, 0.21, 0.03), shoe, { y: -0.225, z: 0.035 })
          batch.add(boxShape(0.13, 0.015, 0.2, 0.006), '#e8e4dc', { y: -0.255, z: 0.035 })
        })
      leg.upper.position.set(x, HIP, 0)
      this.body.add(leg.upper)
      return leg
    }) as [Limb, Limb]

    // Torso with a belt, the collar, and what they wear on it.
    const torso = new Batch()
    torso.add(boxShape(0.36, 0.42, 0.22, 0.06), look.shirt, { y: HIP + 0.21 })
    torso.add(boxShape(0.37, 0.05, 0.23, 0.02), shade(look.pants, -0.08), { y: HIP + 0.02 })
    torso.add(boxShape(0.05, 0.035, 0.01), '#c9a24a', { y: HIP + 0.02, z: 0.116 })
    torso.add(boxShape(0.2, 0.05, 0.16, 0.02), shade(look.shirt, 0.08), { y: HIP + 0.41 })
    torso.add(cylinderShape(0.055, 0.06, 0.06, 10), look.skin, { y: HIP + 0.45 })
    if (look.accessory === 'tie') {
      torso.add(boxShape(0.07, 0.04, 0.02), '#9e2b25', { y: HIP + 0.37, z: 0.115 })
      torso.add(boxShape(0.06, 0.22, 0.02, 0.008), '#9e2b25', { y: HIP + 0.24, z: 0.115 })
    } else if (look.accessory === 'scarf') {
      torso.add(torusShape(0.15, 0.045, Math.PI * 2, 8, 16), '#e8c547', { y: HIP + 0.43, rx: Math.PI / 2 })
      torso.add(boxShape(0.07, 0.16, 0.03, 0.012), '#e8c547', { y: HIP + 0.33, z: 0.12, x: 0.07 })
    } else if (look.accessory === 'badge') {
      torso.add(boxShape(0.08, 0.09, 0.02, 0.008), accent, { y: HIP + 0.32, z: 0.115, x: -0.09 })
      torso.add(boxShape(0.05, 0.012, 0.022), '#ffffff', { y: HIP + 0.33, z: 0.116, x: -0.09 })
    }
    this.body.add(this.meshOf(torso))

    // Arms: upper arm and forearm with a hand, pivoting at the shoulder and the elbow.
    this.arms = [-0.235, 0.235].map((x) => {
      const arm = this.limb(0.19, 0.16,
        (batch) => batch.add(boxShape(0.1, 0.2, 0.1, 0.03), look.shirt, { y: -0.095 }),
        (batch) => {
          batch.add(boxShape(0.092, 0.16, 0.092, 0.028), look.shirt, { y: -0.08 })
          batch.add(boxShape(0.096, 0.025, 0.096, 0.01), shade(look.shirt, -0.06), { y: -0.15 })
          batch.add(boxShape(0.095, 0.09, 0.095, 0.035), look.skin, { y: -0.205 })
        })
      arm.end.position.y = -0.205
      arm.upper.position.set(x, HIP + 0.38, 0)
      this.body.add(arm.upper)
      return arm
    }) as [Limb, Limb]

    // Head: a rounded block with ears, a nose, cheeks, hair and what they wear on it.
    this.head.position.y = HIP + 0.42 + 0.2
    const head = new Batch()
    head.add(boxShape(0.38, 0.36, 0.36, 0.08), look.skin)
    for (const side of [-1, 1]) head.add(boxShape(0.04, 0.08, 0.07, 0.02), look.skin, { x: side * 0.195, y: -0.01 })
    head.add(boxShape(0.05, 0.05, 0.04, 0.018), shade(look.skin, -0.06), { y: -0.03, z: 0.18 })
    head.add(boxShape(0.09, 0.022, 0.02, 0.008), '#a5574b', { y: -0.1, z: 0.175 })
    for (const side of [-1, 1]) head.add(boxShape(0.055, 0.03, 0.01, 0.01), '#f08f8f', { x: side * 0.12, y: -0.06, z: 0.181 })
    this.addHair(head, look)
    this.addHeadwear(head, look)
    this.head.add(this.meshOf(head))
    // Eyes on their own, so they can blink.
    const eyes = new Batch()
    for (const side of [-1, 1]) {
      eyes.add(boxShape(0.05, 0.07, 0.02, 0.012), '#1d1d22', { x: side * 0.08 })
      eyes.add(boxShape(0.016, 0.018, 0.005), '#ffffff', { x: side * 0.08 + 0.01, y: 0.016, z: 0.011 })
    }
    this.eyes = this.meshOf(eyes, false)
    this.eyes.position.set(0, 0.02, 0.18)
    this.head.add(this.eyes)
    this.body.add(this.head)

    // Props shown for some actions.
    const book = new Batch()
    book.add(boxShape(0.22, 0.28, 0.05, 0.01), '#b5523b')
    book.add(boxShape(0.2, 0.26, 0.052), '#f3efe7', { x: 0.012 })
    this.book = this.meshOf(book)
    this.book.position.set(0, 0.62, 0.24)
    this.book.visible = false
    this.body.add(this.book)
    const cup = new Batch()
    cup.add(cylinderShape(0.038, 0.034, 0.09, 12), '#ffffff')
    cup.add(torusShape(0.024, 0.007, Math.PI * 2, 6, 10), '#ffffff', { x: 0.04 })
    this.cup = this.meshOf(cup)
    this.cup.position.set(0, -0.06, 0.06)
    this.cup.visible = false
    this.arms[1].end.add(this.cup)
    const marker = new Batch()
    marker.add(cylinderShape(0.014, 0.014, 0.15, 8), accent, { rx: Math.PI / 2 })
    marker.add(coneShape(0.014, 0.03, 8), '#1d1d22', { z: 0.09, rx: Math.PI / 2 })
    this.marker = this.meshOf(marker)
    this.marker.position.set(0, -0.05, 0.08)
    this.marker.visible = false
    this.arms[1].end.add(this.marker)
    // A page held up to read, and printed pages carried in both hands.
    const paper = new Batch()
    paper.add(boxShape(0.21, 0.29, 0.006), '#fbfaf6')
    for (let line = 0; line < 6; line += 1) paper.add(boxShape(0.15 - (line % 3) * 0.02, 0.012, 0.002), '#9aa1ab', { y: 0.1 - line * 0.035, z: 0.004 })
    this.paper = this.meshOf(paper, false)
    this.paper.position.set(0, 0.64, 0.25)
    this.paper.rotation.x = -0.35
    this.paper.visible = false
    this.body.add(this.paper)
    const pages = new Batch()
    for (let sheet = 0; sheet < 4; sheet += 1) pages.add(boxShape(0.21, 0.007, 0.29), '#fbfaf6', { y: sheet * 0.008, ry: (sheet % 2) * 0.05 })
    this.pages = this.meshOf(pages)
    this.pages.position.set(0, 0.6, 0.27)
    this.pages.visible = false
    this.body.add(this.pages)

    this.root.add(this.body)
    this.root.position.set(start.x, 0, start.z)
    this.root.userData.personId = id
    this.root.traverse((object) => { object.userData.personId = id })
  }

  /** One mesh of merged parts, drawn with the scene's matte finish. */
  private meshOf(batch: Batch, shadow = true): THREE.Mesh {
    const [part] = batch.build()
    const geometry = part!.geometry
    this.geometries.push(geometry)
    const mesh = new THREE.Mesh(geometry, this.finishes.matte)
    mesh.castShadow = shadow
    return mesh
  }

  private limb(upperLength: number, lowerLength: number, upperParts: (batch: Batch) => void, lowerParts: (batch: Batch) => void): Limb {
    const upper = new THREE.Group()
    const top = new Batch()
    upperParts(top)
    upper.add(this.meshOf(top))
    const lower = new THREE.Group()
    lower.position.y = -upperLength
    const bottom = new Batch()
    lowerParts(bottom)
    lower.add(this.meshOf(bottom))
    const end = new THREE.Group()
    end.position.y = -lowerLength
    lower.add(end)
    upper.add(lower)
    return { upper, lower, end }
  }

  private addHair(head: Batch, look: ActorLook): void {
    const hair = look.hair
    if (look.hairStyle === 'bald') {
      for (const side of [-1, 1]) head.add(boxShape(0.03, 0.12, 0.26, 0.012), hair, { x: side * 0.19, y: 0.02, z: -0.04 })
      return
    }
    head.add(boxShape(0.4, 0.11, 0.38, 0.05), hair, { y: 0.17 })
    head.add(boxShape(0.4, 0.22, 0.07, 0.03), hair, { y: 0.07, z: -0.165 })
    for (const side of [-1, 1]) head.add(boxShape(0.03, 0.12, 0.2, 0.012), hair, { x: side * 0.195, y: 0.1, z: -0.05 })
    if (look.hairStyle === 'short') head.add(boxShape(0.3, 0.06, 0.05, 0.02), hair, { y: 0.15, z: 0.17, rx: 0.3 })
    if (look.hairStyle === 'long') {
      head.add(boxShape(0.42, 0.44, 0.09, 0.03), hair, { y: -0.03, z: -0.175 })
      head.add(boxShape(0.36, 0.06, 0.05, 0.02), hair, { y: 0.15, z: 0.17, rx: 0.2 })
    }
    if (look.hairStyle === 'bun') head.add(sphereShape(0.09, 12, 10), hair, { y: 0.27, z: -0.12 })
    if (look.hairStyle === 'spiky') {
      for (const [x, z, tilt] of [[-0.11, 0.06, -0.3], [0.02, -0.06, 0], [0.12, 0.08, 0.3], [-0.02, 0.14, 0.15], [0.08, -0.12, 0.2]] as const) {
        head.add(coneShape(0.065, 0.14, 5), hair, { x, y: 0.28, z, rz: tilt })
      }
    }
  }

  private addHeadwear(head: Batch, look: ActorLook): void {
    const dark = '#1d1d22'
    const accessory = look.accessory
    if (accessory === 'glasses') {
      for (const side of [-1, 1]) {
        head.add(torusShape(0.042, 0.009, Math.PI * 2, 6, 16), dark, { x: side * 0.08, y: 0.02, z: 0.19 })
      }
      head.add(boxShape(0.05, 0.012, 0.012), dark, { y: 0.03, z: 0.19 })
    } else if (accessory === 'headset') {
      head.add(torusShape(0.21, 0.018, Math.PI, 6, 16), dark, { y: 0.06 })
      for (const side of [-1, 1]) head.add(boxShape(0.05, 0.11, 0.11, 0.025), dark, { x: side * 0.2 })
      head.add(boxShape(0.02, 0.02, 0.15, 0.008), dark, { x: 0.2, y: -0.08, z: 0.08, ry: 0.4 })
      head.add(sphereShape(0.022, 8, 6), '#38c98f', { x: 0.17, y: -0.09, z: 0.15 })
    } else if (accessory === 'cap') {
      head.add(boxShape(0.41, 0.11, 0.39, 0.05), look.shirt, { y: 0.21 })
      head.add(boxShape(0.36, 0.025, 0.17, 0.01), look.shirt, { y: 0.17, z: 0.24 })
      head.add(sphereShape(0.025, 8, 6), shade(look.shirt, 0.15), { y: 0.27 })
    } else if (accessory === 'helmet') {
      head.add(sphereShape(0.245, 16, 10), '#f2c230', { y: 0.12, sy: 0.75 })
      head.add(boxShape(0.5, 0.025, 0.5, 0.01), '#f2c230', { y: 0.1 })
    }
  }

  get action(): Action {
    return this.doing
  }

  set action(next: Action) {
    if (next === this.doing) return
    this.doing = next
    this.changedAt = performance.now() / 1000
  }

  /** Walk to a place along a path (the last point is the place itself). */
  goTo(place: Place, path: Point[]): void {
    this.place = place
    this.path = path
  }

  get walking(): boolean {
    return this.moving
  }

  get seated(): boolean {
    return this.sit > 0.5
  }

  cheer(now: number): void {
    this.cheerUntil = now + 1.4
  }

  /** The height of the top of the head, for labels. */
  get top(): number {
    return HIP + 0.84 + 0.12 - this.sit * SIT_DROP
  }

  update(dt: number, now: number, still: boolean): void {
    // Moving along the path.
    const wasMoving = this.moving
    this.moving = false
    if (this.path.length > 0) {
      const next = this.path[0]!
      const dx = next.x - this.position.x
      const dz = next.z - this.position.z
      const distance = Math.hypot(dx, dz)
      const step = still ? distance : WALK_SPEED * dt
      if (distance <= step || distance < 0.01) {
        this.position.x = next.x
        this.position.z = next.z
        this.path.shift()
      } else {
        this.position.x += (dx / distance) * step
        this.position.z += (dz / distance) * step
        this.turnToward(Math.atan2(dx, dz), dt, still)
      }
      this.moving = this.path.length > 0 || distance > step
    }
    if (wasMoving && !this.moving) this.settledAt = now
    const arrived = !this.moving && this.place !== null
    if (arrived && this.place) {
      this.turnToward(Math.atan2(this.place.face.x - this.position.x, this.place.face.z - this.position.z), dt, still)
    }
    const sitting = arrived && Boolean(this.place?.sit) && !this.moving
    const ease = still ? 1 : 1 - Math.exp(-dt * 8)
    this.sit += ((sitting ? 1 : 0) - this.sit) * ease
    this.root.position.set(this.position.x, 0, this.position.z)
    this.root.rotation.y = this.heading
    this.pose(dt, now, still)
  }

  private turnToward(angle: number, dt: number, still: boolean): void {
    let diff = angle - this.heading
    diff = Math.atan2(Math.sin(diff), Math.cos(diff))
    this.heading += still ? diff : diff * Math.min(1, dt * TURN_SPEED)
  }

  private pose(dt: number, now: number, still: boolean): void {
    const [leftLeg, rightLeg] = this.legs
    const [leftArm, rightArm] = this.arms
    const t = now + this.phase
    if (this.moving && !still) this.stride += dt * 9
    const swing = this.moving && !still ? Math.sin(this.stride) : 0
    const sit = this.sit

    // Legs: a walk swing standing, thighs forward and shins down seated.
    leftLeg.upper.rotation.x = swing * 0.55 * (1 - sit) - (Math.PI / 2) * sit
    rightLeg.upper.rotation.x = -swing * 0.55 * (1 - sit) - (Math.PI / 2) * sit
    leftLeg.lower.rotation.x = Math.max(0, -swing) * 0.6 * (1 - sit) + (Math.PI / 2) * sit
    rightLeg.lower.rotation.x = Math.max(0, swing) * 0.6 * (1 - sit) + (Math.PI / 2) * sit
    // A slight breath while standing still, a bob while walking.
    const breath = still || this.moving ? 0 : Math.sin(t * 1.6) * 0.004
    this.body.position.y = -SIT_DROP * sit + (this.moving && !still ? Math.abs(Math.cos(this.stride)) * 0.03 : breath)
    this.body.rotation.x = 0

    // Arms by action (walking overrides them with a swing).
    let left = { x: -swing * 0.5, z: -0.06, elbow: -0.15 }
    let right = { x: swing * 0.5, z: 0.06, elbow: -0.15 }
    let headX = 0
    let headY = 0
    this.book.visible = false
    this.cup.visible = false
    this.marker.visible = false
    this.paper.visible = false
    this.pages.visible = false
    // Printed pages stay in the hands on the way back to the desk.
    const action = this.moving && this.action !== 'carry' ? 'walk' : this.action
    const settled = now - Math.max(this.settledAt, this.changedAt)
    const cheering = now < this.cheerUntil && !still
    if (cheering) {
      const lift = Math.sin(((this.cheerUntil - now) / 1.4) * Math.PI)
      left = { x: 0, z: -2.6, elbow: -0.2 }
      right = { x: 0, z: 2.6, elbow: -0.2 }
      this.body.position.y += lift * 0.12
    } else if (action === 'type') {
      const tap = still ? 0 : Math.sin(t * 18) * 0.08
      left = { x: -1.05 + tap, z: 0.1, elbow: -0.55 }
      right = { x: -1.05 - tap, z: -0.1, elbow: -0.55 }
      headX = 0.12 + (still ? 0 : Math.sin(t * 2.1) * 0.03)
    } else if (action === 'read' && sit < 0.5 && settled < 1.3 && !still) {
      // At the shelf: reach up and take a book out first.
      const reach = Math.sin(Math.min(1, settled / 1.3) * Math.PI)
      right = { x: -2.4 * reach, z: -0.12, elbow: -0.25 }
      left = { x: -0.2, z: 0.08, elbow: -0.3 }
      headX = -0.18 * reach
    } else if (action === 'read') {
      left = { x: -0.95, z: 0.2, elbow: -0.9 }
      right = { x: -0.95, z: -0.2, elbow: -0.9 }
      headX = 0.3
      this.book.visible = true
    } else if (action === 'browse') {
      // A hand on the mouse, now and then a scroll; the eyes go along the page.
      const scroll = still ? 0 : Math.max(0, Math.sin(t * 0.7)) ** 8 * 0.12
      right = { x: -1.0 - scroll, z: -0.2, elbow: -0.55 + scroll }
      left = { x: -0.8, z: 0.16, elbow: -0.75 }
      headX = 0.1 + (still ? 0 : Math.sin(t * 0.45) * 0.04)
      headY = still ? 0 : Math.sin(t * 0.6) * 0.12
    } else if (action === 'paper') {
      left = { x: -1.0, z: 0.16, elbow: -0.85 }
      right = { x: -1.0, z: -0.16, elbow: -0.85 }
      headX = 0.26 + (still ? 0 : Math.sin(t * 0.5) * 0.04)
      this.paper.visible = true
    } else if (action === 'gaze') {
      // Hands behind the back, looking out of the window.
      left = { x: 0.45, z: 0.12, elbow: -0.6 }
      right = { x: 0.45, z: -0.12, elbow: -0.6 }
      headX = -0.1
      headY = still ? 0 : Math.sin(t * 0.35) * 0.22
    } else if (action === 'carry') {
      left = { x: -0.75, z: 0.12, elbow: -0.75 }
      right = { x: -0.75, z: -0.12, elbow: -0.75 }
      headX = 0.12
      this.pages.visible = true
    } else if (action === 'think') {
      right = { x: -1.6, z: -0.35, elbow: -1.9 }
      left = { x: -0.3, z: 0.25, elbow: -1.2 }
      headX = -0.12
      headY = still ? 0 : Math.sin(t * 0.9) * 0.15
    } else if (action === 'write') {
      // At the whiteboard: the right hand moves the marker across.
      right = { x: -2.3 + (still ? 0 : Math.sin(t * 3) * 0.15), z: -0.2 + (still ? 0 : Math.cos(t * 2.3) * 0.2), elbow: -0.3 }
      this.marker.visible = true
      headY = still ? 0 : Math.sin(t * 1.1) * 0.12
    } else if (action === 'talk') {
      right = { x: -0.9 + (still ? 0 : Math.sin(t * 2.6) * 0.25), z: -0.15, elbow: -0.9 }
      left = { x: -0.4, z: 0.1, elbow: -0.6 }
      headX = still ? 0 : Math.sin(t * 3.2) * 0.07
      headY = still ? 0 : Math.sin(t * 0.7) * 0.25
    } else if (action === 'raise') {
      right = { x: 0, z: 2.75 + (still ? 0 : Math.sin(t * 6) * 0.18), elbow: -0.25 }
      headX = -0.1
    } else if (action === 'slump') {
      headX = 0.45
      left = { x: 0.05, z: 0.04, elbow: 0 }
      right = { x: 0.05, z: -0.04, elbow: 0 }
    } else if (action === 'sip') {
      const lift = still ? 0 : Math.max(0, Math.sin(t * 0.8))
      right = { x: -0.5 - lift * 1.2, z: -0.15, elbow: -0.6 - lift * 1.4 }
      this.cup.visible = true
    } else if (action === 'operate') {
      const tap = still ? 0 : Math.sin(t * 12) * 0.1
      left = { x: -1.2 + tap, z: 0.12, elbow: -0.4 }
      right = { x: -1.2 - tap, z: -0.12, elbow: -0.4 }
      headX = 0.05
    } else if (action === 'rest' && sit > 0.5) {
      left = { x: -0.5, z: 0.1, elbow: -0.6 }
      right = { x: -0.5, z: -0.1, elbow: -0.6 }
    }
    const blend = still ? 1 : 1 - Math.exp(-dt * 10)
    for (const [arm, target] of [[leftArm, left], [rightArm, right]] as const) {
      arm.upper.rotation.x += (target.x - arm.upper.rotation.x) * blend
      arm.upper.rotation.z += (target.z - arm.upper.rotation.z) * blend
      arm.lower.rotation.x += (target.elbow - arm.lower.rotation.x) * blend
    }
    this.head.rotation.x += (headX - this.head.rotation.x) * blend
    this.head.rotation.y += (headY - this.head.rotation.y) * blend

    // Blinking.
    if (!still && now > this.blinkAt) this.blinkAt = now + 2.5 + Math.random() * 3.5
    this.eyes.scale.y = !still && now > this.blinkAt - 0.12 ? 0.15 : 1
  }

  dispose(): void {
    this.root.removeFromParent()
    // The finishes belong to the scene; the merged parts are this person's own.
    for (const geometry of this.geometries) geometry.dispose()
  }
}

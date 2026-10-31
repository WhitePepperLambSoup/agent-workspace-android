import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

import type { ActorLook } from '../cast'
import type { Place, Point } from '../layout'
import { createFinishes, disposeFinishes, type Finishes } from '../mesh-kit'
import type { FloorGrid } from '../paths'
import { Person, type Action } from '../person'
import type { StudioOptions } from '../scene'

/**
 * The stage the campus's places are drawn on: the renderer, the light, the camera that frames a
 * place and flies in when it opens, the people who walk about it, and the HTML signs and tags
 * laid over the canvas. Each place builds its own models and says who is where.
 */

export interface Vec { x: number; y: number; z: number }

/** A sign over something in the place: its name and what is going on there. */
export interface PlaceLabel {
  at: Vec
  title: string
  detail?: string
  /** busy: something is under way; alert: something needs a look. */
  tone?: 'busy' | 'alert'
  pick?: string
}

/** Someone in the place, where they should be and what they do there. */
export interface CrowdActor {
  id: string
  name: string
  state: 'working' | 'waiting' | 'done' | 'failed' | 'idle'
  stateLabel: string
  look: ActorLook
  place: Place
  action: Action
  bubble?: string
  pick?: string
}

export interface PlaceContext {
  root: THREE.Group
  finishes: Finishes
  options: StudioOptions
  still: boolean
  /**
   * A click on this object, or anything in it, picks the id; for an instanced mesh the id may
   * come from the instance clicked.
   */
  pickable(object: THREE.Object3D, id: string | ((instance: number) => string | undefined)): void
}

export interface PlaceFrame {
  min: Vec
  max: Vec
  polar: number
  azimuth: number
}

export interface PlaceUpdate {
  people: CrowdActor[]
  labels: Record<string, PlaceLabel>
}

export interface PlaceRuntime<M> {
  /** What the camera frames, and from where. */
  frame: PlaceFrame
  /** The floor people walk on, and where newcomers come in. */
  floor?: { grid: FloorGrid; door: Point }
  /** Lamps of the place, lit at night (in the dark colour mode) and faintly by day. */
  lamps?: ReadonlyArray<Vec & { colour?: string }>
  update(model: M, now: number): PlaceUpdate
  /** One frame; true while something in it moves. */
  tick(now: number, dt: number): boolean
  /** Where the camera heads for when something is picked on the way in (the campus's buildings). */
  target?(id: string): Vec | null
  /** A sign for what the pointer is over, if the place has one for it. */
  hover?(pick: string): PlaceLabel | null
  dispose(): void
}

export type PlaceBuilder<M> = (context: PlaceContext) => PlaceRuntime<M>

export interface PlaceScene<M> {
  update(model: M): void
  setPaused(paused: boolean): void
  resetView(): void
  /** Flies toward what was picked; resolves once there (at once with reduced motion). */
  approach(id: string): Promise<void>
  dispose(): void
}

// A phone: 30 frames a second while things move, 12 while people only sway (the desktop draws 60/30),
// and none once nothing has moved, been touched or changed for SLEEP_AFTER_MS.
const FRAME_MS = 1000 / 30
const RESTING_FRAME_MS = 1000 / 12
const SLEEP_AFTER_MS = 4000
const ARRIVE_SECONDS = 1.2
const APPROACH_SECONDS = 0.7
const SUN = new THREE.Vector3(-5, 11, 8)
const HOVER = '__hover'

interface View { target: THREE.Vector3; radius: number; polar: number; azimuth: number }

interface Member {
  person: Person
  actor: CrowdActor
  tag: HTMLButtonElement
  bubble: HTMLDivElement
  key: string
}

function ease(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

export function createPlaceScene<M>(
  stage: HTMLElement,
  overlay: HTMLElement,
  options: StudioOptions,
  build: PlaceBuilder<M>,
  handlers: { pick(id: string): void },
): PlaceScene<M> {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
  // As the studio on a phone: 1.25 pixels per CSS pixel, shadows drawn again only when something moved.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.shadowMap.autoUpdate = false
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = options.dark ? 1.05 : 1.0
  renderer.domElement.classList.add('studio-canvas')
  renderer.domElement.setAttribute('aria-hidden', 'true')
  stage.prepend(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(30, 1, 0.5, 260)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.enablePan = false
  controls.rotateSpeed = 0.6
  controls.zoomSpeed = 0.8

  scene.add(new THREE.HemisphereLight(options.dark ? '#9fb0e0' : '#fff6ea', options.dark ? '#3a3040' : '#b8a48c', options.dark ? 1.35 : 1.5))
  const key = new THREE.DirectionalLight(options.dark ? '#b9c8ff' : '#fff1dc', options.dark ? 1.5 : 2.2)
  key.castShadow = true
  key.shadow.mapSize.set(1024, 1024)
  key.shadow.camera.near = 1
  key.shadow.bias = -0.0006
  key.shadow.radius = 3
  scene.add(key, key.target)
  const fill = new THREE.DirectionalLight(options.dark ? '#5b4b8a' : '#cfe3ff', options.dark ? 0.35 : 0.6)
  fill.position.set(9, 5, -3)
  scene.add(fill)

  const finishes = createFinishes()
  const root = new THREE.Group()
  scene.add(root)
  const still = options.reducedMotion
  const pickables: THREE.Object3D[] = []
  const place = build({
    root,
    finishes,
    options,
    still,
    pickable(object, id) {
      object.traverse((node) => {
        if (typeof id === 'function') node.userData.pickInstance = id
        else node.userData.pick = id
      })
      pickables.push(object)
    },
  })

  // The light and its shadow cover the place's box.
  const { min, max } = place.frame
  const centre = new THREE.Vector3((min.x + max.x) / 2, (min.y + max.y) / 2, (min.z + max.z) / 2)
  const half = Math.max(max.x - min.x, max.z - min.z) / 2 + 2
  key.target.position.copy(centre)
  key.position.copy(SUN).multiplyScalar(1 + half / SUN.length()).add(centre)
  Object.assign(key.shadow.camera, { left: -half, right: half, top: half, bottom: -half, far: 2 * (SUN.length() + half) + 10 })
  key.shadow.camera.updateProjectionMatrix()
  const lamps = (place.lamps ?? []).map((at) => {
    const lamp = new THREE.PointLight(at.colour ?? '#ffcf8a', options.dark ? 9 : 2.5, 9, 1.4)
    lamp.position.set(at.x, at.y, at.z)
    scene.add(lamp)
    return lamp
  })

  // The distance at which the camera, at these angles, has every corner of the box in view.
  const fitBox = (target: THREE.Vector3, polar: number, azimuth: number): number => {
    const back = new THREE.Vector3().setFromSpherical(new THREE.Spherical(1, polar, azimuth))
    const right = new THREE.Vector3(0, 1, 0).cross(back).normalize()
    const up = back.clone().cross(right)
    const vertical = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)
    const horizontal = vertical * camera.aspect
    const corner = new THREE.Vector3()
    let distance = 0
    for (let index = 0; index < 8; index += 1) {
      corner.set(index & 1 ? max.x : min.x, index & 2 ? max.y : min.y, index & 4 ? max.z : min.z).sub(target)
      const depth = corner.dot(back)
      distance = Math.max(distance, depth + Math.abs(corner.dot(right)) / horizontal, depth + Math.abs(corner.dot(up)) / vertical)
    }
    return distance
  }
  const home = (): View => {
    // A phone held upright: from higher up and a little closer, so the place's floor fills more of
    // the narrow screen (its far corners may be cut; the view can be turned and zoomed).
    const upright = camera.aspect < 1
    const polar = upright ? Math.max(0.45, place.frame.polar - 0.25) : place.frame.polar
    return { target: centre.clone(), radius: fitBox(centre, polar, place.frame.azimuth) * (upright ? 0.9 : 1.03), polar, azimuth: place.frame.azimuth }
  }
  const current = (): View => {
    const spherical = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target))
    return { target: controls.target.clone(), radius: spherical.radius, polar: spherical.phi, azimuth: spherical.theta }
  }
  const setCamera = (view: View): void => {
    controls.target.copy(view.target)
    camera.position.setFromSpherical(new THREE.Spherical(view.radius, view.polar, view.azimuth)).add(view.target)
    camera.lookAt(view.target)
  }
  const limit = (): void => {
    const view = home()
    controls.minDistance = view.radius * 0.4
    controls.maxDistance = view.radius * 1.5
    controls.minPolarAngle = 0.3
    controls.maxPolarAngle = 1.4
    controls.minAzimuthAngle = view.azimuth - 1.1
    controls.maxAzimuthAngle = view.azimuth + 1.0
  }
  let move: { from: View; to: View; start: number; seconds: number; done?: () => void } | null = null
  const fly = (to: View, seconds: number, done?: () => void): void => {
    if (still || seconds <= 0) {
      setCamera(to)
      controls.update()
      done?.()
      return
    }
    move = { from: current(), to, start: performance.now() / 1000, seconds, ...(done ? { done } : {}) }
    controls.enabled = false
  }
  const stepMove = (now: number): void => {
    if (!move) return
    const t = ease(Math.min(1, (now - move.start) / move.seconds))
    const { from, to } = move
    setCamera({
      target: from.target.clone().lerp(to.target, t),
      radius: THREE.MathUtils.lerp(from.radius, to.radius, t),
      polar: THREE.MathUtils.lerp(from.polar, to.polar, t),
      azimuth: THREE.MathUtils.lerp(from.azimuth, to.azimuth, t),
    })
    if (now - move.start >= move.seconds) {
      const done = move.done
      move = null
      controls.enabled = true
      controls.update()
      done?.()
    }
  }

  // People: a tag and a bubble each, laid over the canvas.
  const members = new Map<string, Member>()
  let first = true
  // What the place shows comes in over its first seconds (the sidecar answers one question at a
  // time): whoever appears then is already at their place; later arrivals come in at the door.
  const opened = performance.now()
  const SETTLING_MS = 4000
  const label = (member: Member): void => {
    const { actor, tag, bubble } = member
    tag.dataset.state = actor.state
    tag.querySelector('.studio-tag-name')!.textContent = actor.name
    tag.querySelector('.studio-tag-state')!.textContent = actor.stateLabel
    tag.setAttribute('aria-label', `${actor.name}: ${actor.stateLabel}`)
    bubble.textContent = actor.bubble ?? ''
    bubble.hidden = !actor.bubble
    bubble.dataset.state = actor.state
  }
  const addMember = (actor: CrowdActor): Member => {
    const settling = first || performance.now() - opened < SETTLING_MS
    const start = settling || !place.floor ? actor.place : place.floor.door
    const person = new Person(actor.id, actor.look, start, options.accent, finishes)
    if (settling) person.heading = Math.atan2(actor.place.face.x - actor.place.x, actor.place.face.z - actor.place.z)
    root.add(person.root)
    const tag = document.createElement('button')
    tag.type = 'button'
    tag.className = 'studio-tag'
    tag.tabIndex = -1
    for (const part of ['studio-tag-dot', 'studio-tag-name', 'studio-tag-state']) {
      const span = document.createElement('span')
      span.className = part
      tag.append(span)
    }
    tag.addEventListener('click', () => { if (member.actor.pick) handlers.pick(member.actor.pick) })
    const bubble = document.createElement('div')
    bubble.className = 'studio-bubble'
    overlay.append(bubble, tag)
    const member: Member = { person, actor, tag, bubble, key: '' }
    label(member)
    return member
  }
  const removeMember = (member: Member): void => {
    member.person.dispose()
    member.tag.remove()
    member.bubble.remove()
  }

  // Signs over things in the place.
  const signs = new Map<string, { element: HTMLButtonElement; label: PlaceLabel; width: number; height: number }>()
  /** The place's own signs, and the one for what the pointer is over. */
  let shownLabels: Record<string, PlaceLabel> = {}
  let hovered: string | null = null
  const showSigns = (labels: Record<string, PlaceLabel>): void => {
    for (const [id, sign] of signs) {
      if (labels[id]) continue
      sign.element.remove()
      signs.delete(id)
    }
    for (const [id, value] of Object.entries(labels)) {
      let sign = signs.get(id)
      if (!sign) {
        const element = document.createElement('button')
        element.type = 'button'
        element.className = 'studio-floor-sign place-sign'
        element.tabIndex = -1
        for (const part of ['studio-floor-title', 'studio-floor-summary']) {
          const span = document.createElement('span')
          span.className = part
          element.append(span)
        }
        element.addEventListener('click', () => { const pick = signs.get(id)?.label.pick; if (pick) handlers.pick(pick) })
        overlay.append(element)
        sign = { element, label: value, width: 0, height: 0 }
        signs.set(id, sign)
      }
      sign.label = value
      const { element } = sign
      element.dataset.busy = value.tone === 'busy' ? 'true' : 'false'
      element.dataset.tone = value.tone ?? ''
      element.dataset.pick = value.pick ? 'true' : 'false'
      element.querySelector('.studio-floor-title')!.textContent = value.title
      const detail = element.querySelector<HTMLElement>('.studio-floor-summary')!
      detail.textContent = value.detail ?? ''
      detail.hidden = !value.detail
      element.setAttribute('aria-label', value.detail ? `${value.title}: ${value.detail}` : value.title)
      sign.width = element.offsetWidth
      sign.height = element.offsetHeight
    }
  }

  let paused = false
  let disposed = false
  const update = (next: M): void => {
    const now = performance.now() / 1000
    const { people, labels } = place.update(next, now)
    const ids = new Set(people.map((actor) => actor.id))
    for (const [id, member] of members) {
      if (ids.has(id)) continue
      removeMember(member)
      members.delete(id)
    }
    for (const actor of people) {
      const known = members.get(actor.id)
      if (known) {
        if (known.actor.state !== actor.state && actor.state === 'done') known.person.cheer(now)
        known.actor = actor
        label(known)
      } else {
        members.set(actor.id, addMember(actor))
      }
    }
    first = false
    shownLabels = labels
    const hover = hovered ? place.hover?.(hovered) ?? null : null
    showSigns(hover ? { ...labels, [HOVER]: hover } : labels)
  }

  const projected = new THREE.Vector3()
  const project = (x: number, y: number, z: number): { x: number; y: number; z: number; visible: boolean } => {
    projected.set(x, y, z).project(camera)
    return {
      x: (projected.x * 0.5 + 0.5) * stage.clientWidth,
      y: (-projected.y * 0.5 + 0.5) * stage.clientHeight,
      z: projected.z,
      visible: projected.z < 1 && Math.abs(projected.x) < 1.15 && Math.abs(projected.y) < 1.15,
    }
  }
  const lay = (): void => {
    const shown = move === null
    for (const member of members.values()) {
      const point = project(member.person.position.x, member.person.top + 0.12, member.person.position.z)
      const visible = shown && point.visible
      member.tag.style.transform = `translate(${point.x.toFixed(1)}px, ${point.y.toFixed(1)}px) translate(-50%, -100%)`
      member.bubble.style.transform = `translate(${point.x.toFixed(1)}px, ${(point.y - 30).toFixed(1)}px) translate(-50%, -100%)`
      member.tag.style.visibility = visible ? 'visible' : 'hidden'
      member.bubble.style.visibility = visible ? 'visible' : 'hidden'
      const depth = String(Math.round((1 - point.z) * 10000))
      member.tag.style.zIndex = depth
      member.bubble.style.zIndex = depth
    }
    // A phone's narrow view puts signs on top of each other: the one pointed at, those with something
    // going on, then the nearer ones keep their place; a sign that would cover one of them waits
    // (the list below the place names everything).
    const rank = (id: string, sign: { label: PlaceLabel }): number => (id === HOVER ? 0 : sign.label.tone === 'alert' ? 1 : sign.label.tone === 'busy' ? 2 : 3)
    const placed = [...signs.entries()]
      .map(([id, sign]) => ({ id, sign, point: project(sign.label.at.x, sign.label.at.y, sign.label.at.z) }))
      .sort((a, b) => rank(a.id, a.sign) - rank(b.id, b.sign) || a.point.z - b.point.z)
    const taken: Array<[number, number, number, number]> = []
    for (const { sign, point } of placed) {
      const left = Math.max(8, Math.min(point.x - sign.width / 2, stage.clientWidth - sign.width - 8))
      const box: [number, number, number, number] = [left, point.y - sign.height, left + sign.width, point.y]
      const free = !taken.some(([x0, y0, x1, y1]) => box[0] < x1 + 3 && box[2] > x0 - 3 && box[1] < y1 + 3 && box[3] > y0 - 3)
      const visible = shown && point.visible && free
      if (visible) taken.push(box)
      sign.element.style.transform = `translate(${left.toFixed(1)}px, ${point.y.toFixed(1)}px) translate(0, -100%)`
      sign.element.style.visibility = visible ? 'visible' : 'hidden'
      sign.element.style.zIndex = String(Math.round((1 - point.z) * 10000))
    }
    overlay.dataset.moving = move ? 'true' : 'false'
  }

  let framed = false
  const resize = (): void => {
    const width = Math.max(1, stage.clientWidth)
    const height = Math.max(1, stage.clientHeight)
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    if (!framed && stage.clientWidth > 0) {
      framed = true
      // Coming in: from a little further out and higher, the camera settles on the place.
      const to = home()
      setCamera({ ...to, radius: to.radius * 1.45, polar: Math.max(0.35, to.polar - 0.18), azimuth: to.azimuth + 0.3 })
      limit()
      fly(to, ARRIVE_SECONDS)
    }
  }
  const observer = new ResizeObserver(() => {
    resize()
    wake()
  })
  observer.observe(stage)
  resize()

  // Picking: a click (not a drag) on someone or on something the place made pickable.
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  let down: { x: number; y: number } | null = null
  let handledUntil = 0
  const pickAt = (event: PointerEvent): string | null => {
    if (move) return null
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    const people = [...members.values()].map((member) => member.person.root)
    for (const found of raycaster.intersectObjects([...people, ...pickables], true)) {
      const personId = found.object.userData.personId as string | undefined
      const byInstance = found.object.userData.pickInstance as ((instance: number) => string | undefined) | undefined
      const pick = personId ? members.get(personId)?.actor.pick
        : byInstance && found.instanceId !== undefined ? byInstance(found.instanceId) : found.object.userData.pick as string | undefined
      if (pick) return pick
    }
    return null
  }
  const onDown = (event: PointerEvent): void => {
    down = { x: event.clientX, y: event.clientY }
    handledUntil = performance.now() + 1500
    wake()
  }
  const onUp = (event: PointerEvent): void => {
    if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 5) {
      const pick = pickAt(event)
      if (pick) handlers.pick(pick)
    }
    down = null
  }
  const onMove = (event: PointerEvent): void => {
    if (event.buttons) {
      handledUntil = performance.now() + 1500
      wake()
      return
    }
    const pick = pickAt(event)
    renderer.domElement.style.cursor = pick ? 'pointer' : 'grab'
    if (pick !== hovered) {
      hovered = pick
      const sign = pick ? place.hover?.(pick) ?? null : null
      showSigns(sign ? { ...shownLabels, [HOVER]: sign } : shownLabels)
    }
  }
  const onLeave = (): void => {
    if (hovered === null) return
    hovered = null
    showSigns(shownLabels)
  }
  const onWheel = (): void => {
    handledUntil = performance.now() + 1500
    wake()
  }
  const onLost = (event: Event): void => event.preventDefault()
  renderer.domElement.addEventListener('pointerdown', onDown)
  renderer.domElement.addEventListener('pointerup', onUp)
  renderer.domElement.addEventListener('pointermove', onMove)
  renderer.domElement.addEventListener('pointerleave', onLeave)
  renderer.domElement.addEventListener('wheel', onWheel, { passive: true })
  renderer.domElement.addEventListener('webglcontextlost', onLost)

  /** The next frame asked for, 0 while drawing has stopped (calm, hidden or disposed). */
  let frame = 0
  let drawn = 0
  let last = performance.now()
  let lively = true
  let measured = 0
  let spent = 0
  /** Since when nothing has moved, worked or been touched; drawing stops SLEEP_AFTER_MS later. */
  let calmSince = performance.now()
  let shadowsStale = true
  const busy = (): boolean => [...members.values()].some((member) => member.actor.state === 'working' || member.actor.state === 'waiting')
  function wake(): void {
    calmSince = performance.now()
    shadowsStale = true
    stage.dataset.sleeping = 'false'
    if (frame === 0 && !disposed && !document.hidden) {
      last = performance.now()
      frame = requestAnimationFrame(loop)
    }
  }
  const loop = (time: number): void => {
    frame = 0
    if (disposed || document.hidden) return
    const interval = lively || time < handledUntil || move ? FRAME_MS : RESTING_FRAME_MS
    if (time - drawn < interval - 2) {
      frame = requestAnimationFrame(loop)
      return
    }
    drawn = time
    const began = performance.now()
    const dt = Math.min(0.05, (time - last) / 1000)
    last = time
    const now = time / 1000
    let walking = false
    if (!paused) {
      for (const member of members.values()) {
        const { actor, person } = member
        const keyed = `${actor.place.x.toFixed(2)},${actor.place.z.toFixed(2)}`
        if (keyed !== member.key) {
          member.key = keyed
          person.goTo(actor.place, place.floor ? place.floor.grid.path(person.position, actor.place) : [actor.place])
        }
        person.action = actor.action
        person.update(dt, now, still)
        walking ||= person.walking
      }
      walking = place.tick(now, dt) || walking
    }
    lively = walking || move !== null
    if (move) stepMove(now)
    else controls.update()
    if (lively || shadowsStale) {
      renderer.shadowMap.needsUpdate = true
      shadowsStale = false
    }
    renderer.render(scene, camera)
    lay()
    spent += performance.now() - began
    measured += 1
    if (measured >= 60) {
      stage.dataset.drawCalls = String(renderer.info.render.calls)
      stage.dataset.triangles = String(renderer.info.render.triangles)
      stage.dataset.frameMs = (spent / measured).toFixed(2)
      measured = 0
      spent = 0
    }
    // Nothing moves, nobody works and nobody touches the view: stop drawing until something changes.
    const clock = performance.now()
    if (lively || clock < handledUntil || (busy() && !paused)) calmSince = clock
    if (clock - calmSince < SLEEP_AFTER_MS) frame = requestAnimationFrame(loop)
    else stage.dataset.sleeping = 'true'
  }
  // Out of sight (the app in the background, the screen off): no frames until it is back.
  const onVisibility = (): void => { if (!document.hidden) wake() }
  document.addEventListener('visibilitychange', onVisibility)
  frame = requestAnimationFrame(loop)

  return {
    update(next) {
      if (disposed) return
      update(next)
      wake()
    },
    setPaused(next) {
      paused = next
      wake()
    },
    resetView() {
      fly(home(), 0.9)
      wake()
    },
    approach(id) {
      const point = place.target?.(id)
      if (!point || disposed) return Promise.resolve()
      const view = current()
      wake()
      return new Promise((resolve) => fly({ target: new THREE.Vector3(point.x, point.y, point.z), radius: view.radius * 0.35, polar: Math.min(view.polar + 0.15, 1.3), azimuth: view.azimuth }, APPROACH_SECONDS, resolve))
    },
    dispose() {
      disposed = true
      cancelAnimationFrame(frame)
      document.removeEventListener('visibilitychange', onVisibility)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onDown)
      renderer.domElement.removeEventListener('pointerup', onUp)
      renderer.domElement.removeEventListener('pointermove', onMove)
      renderer.domElement.removeEventListener('pointerleave', onLeave)
      renderer.domElement.removeEventListener('wheel', onWheel)
      renderer.domElement.removeEventListener('webglcontextlost', onLost)
      controls.dispose()
      for (const member of members.values()) removeMember(member)
      members.clear()
      for (const sign of signs.values()) sign.element.remove()
      signs.clear()
      place.dispose()
      for (const lamp of lamps) lamp.dispose()
      root.removeFromParent()
      disposeFinishes(finishes)
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    },
  }
}

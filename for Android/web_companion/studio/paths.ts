import { ROOM, type Box, type Point } from './layout'

const CELL = 0.2
/** How far a person keeps from furniture, in metres. */
const CLEARANCE = 0.18

/** A walking grid over the floor; cells inside furniture (plus clearance) are blocked. */
export class FloorGrid {
  readonly columns: number
  readonly rows: number
  private readonly blocked: Uint8Array
  /** The floor's edges: the studio's room unless a place has a floor of another size. */
  private readonly bounds: Box

  constructor(boxes: readonly Box[], bounds: Box = ROOM) {
    this.bounds = { x0: bounds.x0, x1: bounds.x1, z0: bounds.z0, z1: bounds.z1 }
    this.columns = Math.round((bounds.x1 - bounds.x0) / CELL)
    this.rows = Math.round((bounds.z1 - bounds.z0) / CELL)
    this.blocked = new Uint8Array(this.columns * this.rows)
    for (let row = 0; row < this.rows; row += 1) {
      for (let column = 0; column < this.columns; column += 1) {
        const { x, z } = this.center(column, row)
        const edge = x < bounds.x0 + 0.25 || x > bounds.x1 - 0.15 || z < bounds.z0 + 0.25 || z > bounds.z1 - 0.15
        const inside = boxes.some((box) => x > box.x0 - CLEARANCE && x < box.x1 + CLEARANCE && z > box.z0 - CLEARANCE && z < box.z1 + CLEARANCE)
        this.blocked[row * this.columns + column] = edge || inside ? 1 : 0
      }
    }
  }

  center(column: number, row: number): Point {
    return { x: this.bounds.x0 + (column + 0.5) * CELL, z: this.bounds.z0 + (row + 0.5) * CELL }
  }

  cell(point: Point): [number, number] {
    const column = Math.min(this.columns - 1, Math.max(0, Math.floor((point.x - this.bounds.x0) / CELL)))
    const row = Math.min(this.rows - 1, Math.max(0, Math.floor((point.z - this.bounds.z0) / CELL)))
    return [column, row]
  }

  isBlocked(column: number, row: number): boolean {
    if (column < 0 || row < 0 || column >= this.columns || row >= this.rows) return true
    return this.blocked[row * this.columns + column] === 1
  }

  /** The nearest free cell to a point (seats sit right against their furniture). */
  private nearestFree(point: Point): [number, number] {
    const [column, row] = this.cell(point)
    if (!this.isBlocked(column, row)) return [column, row]
    for (let radius = 1; radius < 12; radius += 1) {
      let best: [number, number] | null = null
      let bestDistance = Infinity
      for (let dz = -radius; dz <= radius; dz += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== radius || this.isBlocked(column + dx, row + dz)) continue
          const center = this.center(column + dx, row + dz)
          const distance = (center.x - point.x) ** 2 + (center.z - point.z) ** 2
          if (distance < bestDistance) { bestDistance = distance; best = [column + dx, row + dz] }
        }
      }
      if (best) return best
    }
    return [column, row]
  }

  private clear(from: Point, to: Point): boolean {
    const steps = Math.ceil(Math.hypot(to.x - from.x, to.z - from.z) / (CELL / 2))
    for (let step = 1; step < steps; step += 1) {
      const t = step / steps
      const [column, row] = this.cell({ x: from.x + (to.x - from.x) * t, z: from.z + (to.z - from.z) * t })
      if (this.isBlocked(column, row)) return false
    }
    return true
  }

  /**
   * A walk from one point to another: A* over the grid, then straightened wherever a straight
   * line is free. Starts and ends exactly at the given points; [to] when no way is found.
   */
  path(from: Point, to: Point): Point[] {
    if (this.clear(from, to)) return [to]
    const [startColumn, startRow] = this.nearestFree(from)
    const [goalColumn, goalRow] = this.nearestFree(to)
    const size = this.columns * this.rows
    const start = startRow * this.columns + startColumn
    const goal = goalRow * this.columns + goalColumn
    const cost = new Float32Array(size).fill(Infinity)
    const came = new Int32Array(size).fill(-1)
    const closed = new Uint8Array(size)
    const open: number[] = [start]
    const score = new Float32Array(size).fill(Infinity)
    const heuristic = (index: number): number => {
      const dx = Math.abs((index % this.columns) - goalColumn)
      const dz = Math.abs(Math.floor(index / this.columns) - goalRow)
      return Math.max(dx, dz) + (Math.SQRT2 - 1) * Math.min(dx, dz)
    }
    cost[start] = 0
    score[start] = heuristic(start)
    while (open.length > 0) {
      let bestAt = 0
      for (let index = 1; index < open.length; index += 1) if (score[open[index]!]! < score[open[bestAt]!]!) bestAt = index
      const current = open[bestAt]!
      open[bestAt] = open[open.length - 1]!
      open.pop()
      if (current === goal) break
      if (closed[current]) continue
      closed[current] = 1
      const column = current % this.columns
      const row = Math.floor(current / this.columns)
      for (let dz = -1; dz <= 1; dz += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
          if (!dx && !dz) continue
          const nextColumn = column + dx
          const nextRow = row + dz
          if (this.isBlocked(nextColumn, nextRow)) continue
          // No cutting corners past furniture.
          if (dx && dz && (this.isBlocked(column + dx, row) || this.isBlocked(column, row + dz))) continue
          const next = nextRow * this.columns + nextColumn
          const tentative = cost[current]! + (dx && dz ? Math.SQRT2 : 1)
          if (tentative < cost[next]!) {
            cost[next] = tentative
            came[next] = current
            score[next] = tentative + heuristic(next)
            open.push(next)
          }
        }
      }
    }
    if (came[goal] === -1 && goal !== start) return [to]
    const cells: Point[] = []
    for (let index = goal; index !== -1 && index !== start; index = came[index]!) {
      cells.push(this.center(index % this.columns, Math.floor(index / this.columns)))
    }
    cells.reverse()
    const route = [...cells, to]
    // Straighten: from each point go to the farthest one in plain sight.
    const smooth: Point[] = []
    let at = from
    let index = 0
    while (index < route.length) {
      let farthest = index
      for (let probe = route.length - 1; probe > index; probe -= 1) {
        if (this.clear(at, route[probe]!)) { farthest = probe; break }
      }
      at = route[farthest]!
      smooth.push(at)
      index = farthest + 1
    }
    return smooth
  }
}

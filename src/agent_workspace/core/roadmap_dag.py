"""Directed Acyclic Graph (DAG) dependency checker and parallel wave planner."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DAGStep:
    step_id: str
    title: str
    dependencies: tuple[str, ...] = ()
    can_parallel: bool = True
    metadata: dict[str, Any] | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "dependencies": list(self.dependencies),
            "can_parallel": self.can_parallel,
            "metadata": self.metadata or {},
        }


class RoadmapDAG:
    """Manages task execution dependencies, cycles, and parallel ready states."""

    def __init__(self, steps: list[DAGStep] | None = None) -> None:
        self._steps: dict[str, DAGStep] = {}
        if steps:
            for s in steps:
                self.add_step(s)
            self.validate()

    @property
    def steps(self) -> dict[str, DAGStep]:
        return dict(self._steps)

    def add_step(self, step: DAGStep) -> None:
        if step.step_id in self._steps:
            raise ValueError(f"Duplicate step id '{step.step_id}'")
        self._steps[step.step_id] = step

    def validate(self) -> None:
        """Validate dependencies and cycle-free property."""
        # 1. Check all dependencies exist
        for s in self._steps.values():
            for dep in s.dependencies:
                if dep not in self._steps:
                    raise ValueError(f"Step '{s.step_id}' depends on non-existent step '{dep}'")

        # 2. Check cycles using Kahn's algorithm
        in_degree: dict[str, int] = {k: 0 for k in self._steps}
        adj: dict[str, list[str]] = {k: [] for k in self._steps}

        for s in self._steps.values():
            in_degree[s.step_id] = len(s.dependencies)
            for dep in s.dependencies:
                adj[dep].append(s.step_id)

        queue = deque([k for k, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(self._steps):
            raise ValueError("Cycle detected in task roadmap DAG")

    def topological_sort(self) -> list[str]:
        """Return a valid linear topological execution order."""
        self.validate()
        in_degree: dict[str, int] = {k: len(s.dependencies) for k, s in self._steps.items()}
        adj: dict[str, list[str]] = {k: [] for k in self._steps}
        for s in self._steps.values():
            for dep in s.dependencies:
                adj[dep].append(s.step_id)

        queue = deque(sorted([k for k, deg in in_degree.items() if deg == 0]))
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in sorted(adj[node]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def ready_steps(self, completed_step_ids: set[str]) -> list[DAGStep]:
        """Return steps whose dependencies are all satisfied and not yet completed."""
        self.validate()
        ready: list[DAGStep] = []
        for s in self._steps.values():
            if s.step_id in completed_step_ids:
                continue
            if all(dep in completed_step_ids for dep in s.dependencies):
                ready.append(s)
        return ready

    def execution_layers(self) -> list[list[str]]:
        """Group steps into parallel executable waves (layers)."""
        self.validate()
        in_degree: dict[str, int] = {k: len(s.dependencies) for k, s in self._steps.items()}
        adj: dict[str, list[str]] = {k: [] for k in self._steps}
        for s in self._steps.values():
            for dep in s.dependencies:
                adj[dep].append(s.step_id)

        current_layer = sorted([k for k, deg in in_degree.items() if deg == 0])
        layers: list[list[str]] = []

        while current_layer:
            layers.append(current_layer)
            next_layer: list[str] = []
            for node in current_layer:
                for neighbor in adj[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_layer.append(neighbor)
            current_layer = sorted(next_layer)

        return layers

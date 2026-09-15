"""Scheduled task management for automated monitoring and reporting."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
import json


class TaskType(Enum):
    DEVICE_READ = "device_read"
    FLEET_CHECK = "fleet_check"
    THRESHOLD_CHECK = "threshold_check"
    REPORT_GENERATION = "report_generation"
    DATA_EXPORT = "data_export"
    ANALYTICS_RUN = "analytics_run"
    CUSTOM = "custom"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class ScheduledTask:
    """Represents a scheduled task configuration."""
    task_id: str
    name: str
    task_type: TaskType
    schedule_cron: str | None = None  # Simple cron: "*/5 * * * *" (every 5 minutes)
    interval_seconds: int | None = None  # Alternative to cron: run every N seconds
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    last_run: str | None = None
    next_run: str | None = None
    run_count: int = 0
    last_status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TaskExecution:
    """Record of a task execution."""
    execution_id: str
    task_id: str
    started_at: str
    completed_at: str | None = None
    status: TaskStatus = TaskStatus.RUNNING
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskScheduler:
    """Manages scheduled tasks for automated monitoring."""

    def __init__(self, operations, store=None, company_id="demo-factory"):
        self.operations = operations
        self._store = store
        self._company_id = company_id
        self._tasks: dict[str, ScheduledTask] = {}
        self._executions: dict[str, list[TaskExecution]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._callbacks: dict[str, Callable] = {}
        self._running = False
        self._scheduler_task: asyncio.Task | None = None
        self._load_from_store()

    def _load_from_store(self) -> None:
        if self._store:
            for data in self._store.get_scheduled_tasks(self._company_id):
                data["task_type"] = TaskType(data["task_type"])
                data["last_status"] = TaskStatus(data["last_status"])
                task = ScheduledTask(**data)
                self._tasks[task.task_id] = task

    def _save_to_store(self) -> None:
        if self._store:
            data = [{**asdict(t), "task_type": t.task_type.value,
                     "last_status": t.last_status.value} for t in self._tasks.values()]
            self._store.save_scheduled_tasks(self._company_id, data)

    def create_task(self, task_id: str, name: str, task_type: TaskType,
                    schedule_cron: str | None = None, interval_seconds: int | None = None,
                    config: dict[str, Any] | None = None, enabled: bool = True) -> ScheduledTask:
        """Create a new scheduled task."""
        if task_id in self._tasks:
            raise ValueError(f"Task {task_id} already exists")

        if schedule_cron:
            raise ValueError("Cron schedules are not implemented; use interval_seconds")
        if interval_seconds is not None and not 1 <= interval_seconds <= 86400:
            raise ValueError("interval_seconds must be 1..86400")
        if task_type not in {TaskType.DEVICE_READ, TaskType.FLEET_CHECK, TaskType.THRESHOLD_CHECK}:
            raise ValueError("Supported tasks: device_read, fleet_check, threshold_check")
        if not schedule_cron and not interval_seconds:
            raise ValueError("Either schedule_cron or interval_seconds must be provided")

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            task_type=task_type,
            schedule_cron=schedule_cron,
            interval_seconds=interval_seconds,
            enabled=enabled,
            config=config or {},
            next_run=self._calculate_next_run(schedule_cron, interval_seconds),
        )

        self._tasks[task_id] = task
        self._executions[task_id] = []
        self._save_to_store()
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a scheduled task."""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()

        self._tasks.pop(task_id, None)
        self._executions.pop(task_id, None)
        self._save_to_store()
        return True

    def update_task(self, task_id: str, **kwargs) -> ScheduledTask | None:
        """Update a scheduled task."""
        if task_id not in self._tasks:
            return None

        task = self._tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        if "schedule_cron" in kwargs or "interval_seconds" in kwargs:
            task.next_run = self._calculate_next_run(task.schedule_cron, task.interval_seconds)

        self._save_to_store()
        return task

    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._save_to_store()
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._save_to_store()
            return True
        return False

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, enabled_only: bool = False, task_type: TaskType | None = None) -> list[ScheduledTask]:
        """List all tasks with optional filtering."""
        tasks = list(self._tasks.values())
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        return tasks

    def get_task_history(self, task_id: str, limit: int = 50) -> list[TaskExecution]:
        """Get execution history for a task."""
        executions = self._executions.get(task_id, [])
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        return executions[-limit:]

    def register_callback(self, task_type: TaskType, callback: Callable) -> None:
        """Register a callback function for a task type."""
        self._callbacks[task_type.value] = callback

    def _calculate_next_run(self, cron: str | None, interval: int | None) -> str:
        """Calculate next run time."""
        now = datetime.now(timezone.utc)
        if cron:
            raise ValueError("Cron schedules are not implemented")
        if interval and 1 <= interval <= 86400:
            return (now + timedelta(seconds=interval)).isoformat()
        # Simple cron parsing (would need a proper cron library for full support)
        return (now + timedelta(minutes=1)).isoformat()

    async def run_task_now(self, task_id: str) -> TaskExecution:
        """Immediately execute a task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        execution = TaskExecution(
            execution_id=f"exec-{task_id}-{datetime.now(timezone.utc).timestamp()}",
            task_id=task_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            result = await self._execute_task(task)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.status = TaskStatus.COMPLETED
            execution.result = result
            task.last_status = TaskStatus.COMPLETED
        except Exception as e:
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.status = TaskStatus.FAILED
            execution.error = str(e)
            task.last_status = TaskStatus.FAILED

        task.last_run = execution.completed_at
        task.run_count += 1
        task.next_run = self._calculate_next_run(task.schedule_cron, task.interval_seconds)

        self._executions.setdefault(task_id, []).append(execution)
        if len(self._executions[task_id]) > 100:
            self._executions[task_id] = self._executions[task_id][-100:]

        self._save_to_store()
        return execution

    async def _execute_task(self, task: ScheduledTask) -> dict[str, Any]:
        """Execute a task based on its type and configuration."""
        if task.task_type == TaskType.DEVICE_READ:
            device_id = task.config.get("device_id")
            if not device_id:
                raise ValueError("device_id required for device_read task")
            return await self.operations.read(device_id)

        elif task.task_type == TaskType.FLEET_CHECK:
            limit = task.config.get("limit", 20)
            return await self.operations.fleet_health(limit)

        elif task.task_type == TaskType.THRESHOLD_CHECK:
            device_id = task.config.get("device_id")
            metric = task.config.get("metric")
            maximum = task.config.get("maximum")
            unit = task.config.get("unit")
            if not device_id or not metric or maximum is None or not unit:
                raise ValueError("device_id, metric, maximum, and unit required")
            return await self.operations.threshold(device_id, metric, maximum, unit)

        elif task.task_type == TaskType.REPORT_GENERATION:
            device_id = task.config.get("device_id")
            if not device_id:
                raise ValueError("device_id required for report_generation task")
            readings = await self.operations.read(device_id)
            return {"report": f"Generated for {device_id}", "readings_count": len(readings.get("readings", []))}

        elif task.task_type == TaskType.ANALYTICS_RUN:
            device_id = task.config.get("device_id")
            metric = task.config.get("metric")
            if not device_id or not metric:
                raise ValueError("device_id and metric required for analytics_run task")
            history = self.operations.history(device_id,
                                             (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
                                             datetime.now(timezone.utc).isoformat(), 500)
            return {"analytics": f"Analyzed {metric} for {device_id}", "samples": len(history)}

        else:
            raise ValueError("Task type is not implemented")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks and runs due tasks."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                for task in list(self._tasks.values()):
                    if not task.enabled or task.task_type in [TaskType.CUSTOM]:
                        continue

                    if task.next_run:
                        try:
                            next_run = datetime.fromisoformat(task.next_run)
                            if now >= next_run:
                                if task.task_id not in self._running_tasks:
                                    self._running_tasks[task.task_id] = asyncio.create_task(
                                        self._run_scheduled_task(task)
                                    )
                        except ValueError:
                            pass

                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _run_scheduled_task(self, task: ScheduledTask) -> None:
        """Run a task that's due for execution."""
        try:
            await self.run_task_now(task.task_id)
        finally:
            self._running_tasks.pop(task.task_id, None)

    async def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self._running = True
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        for task_id, task in self._running_tasks.items():
            task.cancel()
        self._running_tasks.clear()
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        enabled_tasks = [t for t in self._tasks.values() if t.enabled]
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "enabled_tasks": len(enabled_tasks),
            "running_tasks": len(self._running_tasks),
            "tasks": {
                task_id: {
                    "name": task.name,
                    "type": task.task_type.value,
                    "enabled": task.enabled,
                    "last_status": task.last_status.value,
                    "run_count": task.run_count,
                    "next_run": task.next_run,
                }
                for task_id, task in self._tasks.items()
            },
        }

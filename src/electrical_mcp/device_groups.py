"""Device grouping and hierarchy support for organizing telemetry devices."""
import json
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class DeviceGroup:
    """Represents a group of devices."""
    group_id: str
    name: str
    description: str = ""
    parent_group_id: str | None = None
    device_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DeviceHierarchy:
    """Represents the complete device hierarchy."""
    groups: dict[str, DeviceGroup] = field(default_factory=dict)
    device_to_groups: dict[str, list[str]] = field(default_factory=dict)


class DeviceGroupManager:
    """Manages device groups and hierarchy."""

    def __init__(self, store=None):
        self._hierarchy = DeviceHierarchy()
        self._store = store
        self._load_from_store()

    def _load_from_store(self) -> None:
        """Load groups from store if available."""
        if self._store:
            try:
                data = self._store.get_device_groups()
                for group_data in data:
                    group = DeviceGroup(**group_data)
                    self._hierarchy.groups[group.group_id] = group
                    for device_id in group.device_ids:
                        if device_id not in self._hierarchy.device_to_groups:
                            self._hierarchy.device_to_groups[device_id] = []
                        self._hierarchy.device_to_groups[device_id].append(group.group_id)
            except Exception:
                pass

    def _save_to_store(self) -> None:
        """Save groups to store if available."""
        if self._store:
            try:
                data = [
                    {
                        "group_id": g.group_id,
                        "name": g.name,
                        "description": g.description,
                        "parent_group_id": g.parent_group_id,
                        "device_ids": g.device_ids,
                        "metadata": g.metadata,
                        "created_at": g.created_at,
                    }
                    for g in self._hierarchy.groups.values()
                ]
                self._store.save_device_groups(data)
            except Exception:
                pass

    def create_group(self, group_id: str, name: str, description: str = "",
                     parent_group_id: str | None = None, metadata: dict[str, Any] | None = None) -> DeviceGroup:
        """Create a new device group."""
        if group_id in self._hierarchy.groups:
            raise ValueError(f"Group {group_id} already exists")

        if parent_group_id and parent_group_id not in self._hierarchy.groups:
            raise ValueError(f"Parent group {parent_group_id} does not exist")

        group = DeviceGroup(
            group_id=group_id,
            name=name,
            description=description,
            parent_group_id=parent_group_id,
            metadata=metadata or {},
        )

        self._hierarchy.groups[group_id] = group
        self._save_to_store()
        return group

    def delete_group(self, group_id: str, recursive: bool = False) -> bool:
        """Delete a device group."""
        if group_id not in self._hierarchy.groups:
            return False

        group = self._hierarchy.groups[group_id]

        # Check for child groups
        children = [g for g in self._hierarchy.groups.values() if g.parent_group_id == group_id]
        if children and not recursive:
            raise ValueError(f"Group has {len(children)} child groups. Use recursive=True to delete.")

        if recursive:
            for child in children:
                self.delete_group(child.group_id, recursive=True)

        # Remove from device mappings
        for device_id in group.device_ids:
            if device_id in self._hierarchy.device_to_groups:
                self._hierarchy.device_to_groups[device_id] = [
                    gid for gid in self._hierarchy.device_to_groups[device_id] if gid != group_id
                ]

        del self._hierarchy.groups[group_id]
        self._save_to_store()
        return True

    def add_device_to_group(self, device_id: str, group_id: str) -> bool:
        """Add a device to a group."""
        if group_id not in self._hierarchy.groups:
            return False

        group = self._hierarchy.groups[group_id]
        if device_id not in group.device_ids:
            group.device_ids.append(device_id)

        if device_id not in self._hierarchy.device_to_groups:
            self._hierarchy.device_to_groups[device_id] = []
        if group_id not in self._hierarchy.device_to_groups[device_id]:
            self._hierarchy.device_to_groups[device_id].append(group_id)

        self._save_to_store()
        return True

    def remove_device_from_group(self, device_id: str, group_id: str) -> bool:
        """Remove a device from a group."""
        if group_id not in self._hierarchy.groups:
            return False

        group = self._hierarchy.groups[group_id]
        if device_id in group.device_ids:
            group.device_ids.remove(device_id)

        if device_id in self._hierarchy.device_to_groups:
            self._hierarchy.device_to_groups[device_id] = [
                gid for gid in self._hierarchy.device_to_groups[device_id] if gid != group_id
            ]

        self._save_to_store()
        return True

    def get_group(self, group_id: str) -> DeviceGroup | None:
        """Get a group by ID."""
        return self._hierarchy.groups.get(group_id)

    def list_groups(self, parent_group_id: str | None = None) -> list[DeviceGroup]:
        """List groups, optionally filtered by parent."""
        groups = list(self._hierarchy.groups.values())
        if parent_group_id is not None:
            groups = [g for g in groups if g.parent_group_id == parent_group_id]
        return groups

    def get_device_groups(self, device_id: str) -> list[DeviceGroup]:
        """Get all groups containing a device."""
        group_ids = self._hierarchy.device_to_groups.get(device_id, [])
        return [self._hierarchy.groups[gid] for gid in group_ids if gid in self._hierarchy.groups]

    def get_group_devices(self, group_id: str, include_children: bool = False) -> list[str]:
        """Get all device IDs in a group, optionally including child groups."""
        if group_id not in self._hierarchy.groups:
            return []

        devices = set(self._hierarchy.groups[group_id].device_ids)

        if include_children:
            children = [g for g in self._hierarchy.groups.values() if g.parent_group_id == group_id]
            for child in children:
                devices.update(self.get_group_devices(child.group_id, include_children=True))

        return list(devices)

    def get_group_tree(self, group_id: str | None = None, depth: int = 0) -> dict[str, Any]:
        """Get hierarchical tree structure of groups."""
        if group_id is None:
            # Get root groups
            root_groups = [g for g in self._hierarchy.groups.values() if g.parent_group_id is None]
            return {
                "groups": [self.get_group_tree(g.group_id, depth + 1) for g in root_groups],
                "total_groups": len(self._hierarchy.groups),
            }

        group = self._hierarchy.groups.get(group_id)
        if not group:
            return {}

        children = [g for g in self._hierarchy.groups.values() if g.parent_group_id == group_id]

        return {
            "group_id": group.group_id,
            "name": group.name,
            "description": group.description,
            "device_count": len(group.device_ids),
            "device_ids": group.device_ids,
            "metadata": group.metadata,
            "children": [self.get_child_tree(c.group_id, depth + 1) for c in children],
        }

    def get_group_statistics(self, group_id: str) -> dict[str, Any]:
        """Get statistics for a group."""
        if group_id not in self._hierarchy.groups:
            return {"error": "Group not found"}

        group = self._hierarchy.groups[group_id]
        children = [g for g in self._hierarchy.groups.values() if g.parent_group_id == group_id]

        all_devices = self.get_group_devices(group_id, include_children=True)

        return {
            "group_id": group_id,
            "name": group.name,
            "direct_devices": len(group.device_ids),
            "total_devices_including_children": len(all_devices),
            "child_groups": len(children),
            "depth": self._calculate_depth(group_id),
        }

    def _calculate_depth(self, group_id: str) -> int:
        """Calculate the depth of a group in the hierarchy."""
        group = self._hierarchy.groups.get(group_id)
        if not group or not group.parent_group_id:
            return 0
        return 1 + self._calculate_depth(group.parent_group_id)

    def search_groups(self, query: str) -> list[DeviceGroup]:
        """Search groups by name or description."""
        query_lower = query.lower()
        return [
            g for g in self._hierarchy.groups.values()
            if query_lower in g.name.lower() or query_lower in g.description.lower()
        ]

    def update_group_metadata(self, group_id: str, metadata: dict[str, Any]) -> bool:
        """Update group metadata."""
        if group_id not in self._hierarchy.groups:
            return False

        self._hierarchy.groups[group_id].metadata.update(metadata)
        self._save_to_store()
        return True

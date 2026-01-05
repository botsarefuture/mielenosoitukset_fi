"""
Job definitions used by the background job manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from mielenosoitukset_fi.scripts.repeat_v2 import main as repeat_main
from mielenosoitukset_fi.scripts.update_demo_organizers import main as update_main
from mielenosoitukset_fi.scripts.in_past import hide_past
from mielenosoitukset_fi.scripts.CL import main as cl_main
from mielenosoitukset_fi.scripts.preview_image_creator import run as run_preview
from mielenosoitukset_fi.scripts.send_demo_reminders import main as demo_sche
from mielenosoitukset_fi.scripts.process_submission_notifications import (
    run as process_submit_notifications,
)
from mielenosoitukset_fi.utils.analytics import prep


@dataclass(frozen=True)
class JobDefinition:
    """Metadata for a background job."""

    key: str
    name: str
    description: str
    func: Callable[[], Any]
    default_trigger: Dict[str, Any]
    allow_manual_trigger: bool = True
    allow_interval_override: bool = True

    def to_document(self) -> Dict[str, Any]:
        """Return the MongoDB document fragment containing immutable job info."""
        return {
            "_id": self.key,
            "name": self.name,
            "description": self.description,
            "trigger": self.default_trigger.get("trigger", "interval"),
            "trigger_args": self.default_trigger.get("trigger_args", {}),
            "allow_manual_trigger": self.allow_manual_trigger,
            "allow_interval_override": self.allow_interval_override,
        }


def _interval(hours: int = 0, minutes: int = 0) -> Dict[str, Any]:
    return {"trigger": "interval", "trigger_args": {"hours": hours, "minutes": minutes}}


JOB_DEFINITIONS: List[JobDefinition] = [
    JobDefinition(
        key="repeat_main",
        name="Recurring demonstrations refresher",
        description="Processes recurring demonstrations and creates child events.",
        func=repeat_main,
        default_trigger=_interval(hours=24),
    ),
    JobDefinition(
        key="update_main",
        name="Organizer metadata updater",
        description="Refreshes demonstration organizer details.",
        func=update_main,
        default_trigger=_interval(hours=1),
    ),
    JobDefinition(
        key="cl_main",
        name="Cleanup and linking",
        description="Runs the CL maintenance script.",
        func=cl_main,
        default_trigger=_interval(hours=24),
    ),
    JobDefinition(
        key="prep",
        name="Analytics rollup",
        description="Aggregates analytics stats for dashboards.",
        func=prep,
        default_trigger=_interval(minutes=15),
    ),
    JobDefinition(
        key="run_preview",
        name="Preview image regeneration",
        description="Generates fresh preview images for demonstrations.",
        func=run_preview,
        default_trigger=_interval(hours=24),
        allow_interval_override=False,
    ),
    JobDefinition(
        key="demo_sche",
        name="Demonstration reminder emails",
        description="Sends reminder emails to subscribers.",
        func=demo_sche,
        default_trigger=_interval(hours=24),
    ),
    JobDefinition(
        key="hide_past",
        name="Past demonstration hider",
        description="Archives events that have already taken place.",
        func=hide_past,
        default_trigger=_interval(hours=24),
    ),
    JobDefinition(
        key="process_submit_notifications",
        name="New demo notification dispatcher",
        description="Sends confirmation + admin notification emails for submitted demonstrations.",
        func=process_submit_notifications,
        default_trigger=_interval(minutes=5),
    ),
]

JOB_DEFINITION_MAP: Dict[str, JobDefinition] = {job.key: job for job in JOB_DEFINITIONS}

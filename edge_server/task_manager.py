import uuid
from datetime import datetime, timezone

class TaskDescriptor:
    def __init__(self, requester_id, task_type, payload, resource_requirements, max_price_usd, deadline_utc, submission_url, signature=None):
        self.task_id = str(uuid.uuid4())
        self.requester_id = requester_id
        self.task_type = task_type  # e.g., 'docker_image', 'python_script'
        self.payload = payload      # task-specific data
        self.resource_requirements = resource_requirements  # dict: e.g., {"cpu_cores": 2, "ram_gb": 1.0}
        self.max_price_usd = max_price_usd
        self.deadline_utc = deadline_utc  # ISO 8601 string
        self.submission_url = submission_url
        self.timestamp_utc = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
        self.signature = signature  # Optional, for future use

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "requester_id": self.requester_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "resource_requirements": self.resource_requirements,
            "max_price_usd": self.max_price_usd,
            "deadline_utc": self.deadline_utc,
            "submission_url": self.submission_url,
            "timestamp_utc": self.timestamp_utc,
            "signature": self.signature,
        }

    @staticmethod
    def from_dict(d):
        return TaskDescriptor(
            requester_id=d["requester_id"],
            task_type=d["task_type"],
            payload=d["payload"],
            resource_requirements=d["resource_requirements"],
            max_price_usd=d["max_price_usd"],
            deadline_utc=d["deadline_utc"],
            submission_url=d["submission_url"],
            signature=d.get("signature")
        )

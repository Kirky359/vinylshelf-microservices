class Status:
    PLANNED = "Planned"
    LISTENING = "Listening"
    COMPLETION_PENDING = "CompletionPending"   # completed locally, the SAGA is not confirmed yet
    COMPLETED = "Completed"


LOCKED_STATUSES = (Status.COMPLETION_PENDING, Status.COMPLETED)

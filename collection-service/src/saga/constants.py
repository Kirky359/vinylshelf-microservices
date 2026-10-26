class State:
    STARTED = "started"
    SENT = "sent"
    PROCESSED = "processed"
    COMPENSATED = "compensated"


FINAL_STATES = (State.PROCESSED, State.COMPENSATED)

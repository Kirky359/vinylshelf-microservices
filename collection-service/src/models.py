"""Global DB schema: every module contributes its own tables."""
from src.collection.models import SCHEMA as COLLECTION_SCHEMA
from src.outbox.models import SCHEMA as OUTBOX_SCHEMA
from src.saga.models import SCHEMA as SAGA_SCHEMA

SCHEMA = COLLECTION_SCHEMA + OUTBOX_SCHEMA + SAGA_SCHEMA

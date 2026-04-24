"""Portable JSON type: JSONB on PostgreSQL, JSON elsewhere (tests)."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB(), "postgresql")

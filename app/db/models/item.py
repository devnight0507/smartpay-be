"""
Database model for items.
"""

import uuid
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base

# Association table for many-to-many relationship between items and tags
item_tag = Table(
    "item_tag",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """Tag for categorizing items."""

    __tablename__ = "tags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship with items
    items = relationship("Item", secondary=item_tag, back_populates="tags")


class ItemStatus(str, Enum):
    """
    Enumeration of possible item statuses.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ItemType(str, Enum):
    """
    Enumeration of possible item types.
    """

    PRODUCT = "product"
    SERVICE = "service"
    DIGITAL = "digital"
    SUBSCRIPTION = "subscription"
    BUNDLE = "bundle"


class Item(Base):
    """
    Database model for items.
    """

    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    meta_data = Column(JSON, nullable=True)  # Renamed from metadata to meta_data
    external_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default=ItemStatus.DRAFT.value, server_default=ItemStatus.DRAFT.value)
    type = Column(String(20), nullable=False, default=ItemType.PRODUCT.value, server_default=ItemType.PRODUCT.value)

    # Foreign keys
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    category = relationship("Category", back_populates="items")
    tags = relationship("Tag", secondary=item_tag, back_populates="items")

    # Soft delete support
    deleted_at = Column(DateTime, nullable=True)

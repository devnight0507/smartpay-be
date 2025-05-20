"""
Pydantic schemas for the items resource.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.models.item import ItemStatus, ItemType


class TagBase(BaseModel):
    """
    Base schema for tag data.
    """

    name: str = Field(..., min_length=1, max_length=50, description="Tag name")


class TagCreate(TagBase):
    """
    Schema for creating a new tag.
    """

    pass


class TagResponse(TagBase):
    """
    Schema for tag response.
    """

    id: UUID = Field(..., description="Tag ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class ItemBase(BaseModel):
    """
    Base schema for item data.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    status: ItemStatus = Field(default=ItemStatus.DRAFT, description="Item status")
    type: ItemType = Field(default=ItemType.PRODUCT, description="Item type")
    metadata: Optional[Dict[str, Union[str, int, float, bool]]] = Field(
        default=None, description="Additional item metadata"
    )
    external_id: Optional[str] = Field(None, max_length=255, description="External system ID")
    price: float = Field(0.0, ge=0, description="Item price")
    quantity: int = Field(0, ge=0, description="Item quantity")
    is_active: bool = Field(True, description="Whether the item is active")
    category_id: Optional[int] = Field(None, description="Category ID")


class ItemCreate(ItemBase):
    """
    Schema for creating a new item.
    """

    tag_ids: Optional[List[UUID]] = Field(None, description="List of tag IDs to associate with the item")


class ItemUpdate(BaseModel):
    """
    Schema for updating an existing item.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    status: Optional[ItemStatus] = Field(None, description="Item status")
    type: Optional[ItemType] = Field(None, description="Item type")
    metadata: Optional[Dict[str, Union[str, int, float, bool]]] = Field(None, description="Additional item metadata")
    external_id: Optional[str] = Field(None, max_length=255, description="External system ID")
    tag_ids: Optional[List[UUID]] = Field(None, description="List of tag IDs to associate with the item")
    price: Optional[float] = Field(None, ge=0, description="Item price")
    quantity: Optional[int] = Field(None, ge=0, description="Item quantity")
    is_active: Optional[bool] = Field(None, description="Whether the item is active")
    category_id: Optional[int] = Field(None, description="Category ID")


class ItemResponse(ItemBase):
    """
    Schema for item response.
    """

    id: int = Field(..., description="Item ID")  # Changed from UUID to int to match DB model
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[UUID] = Field(None, description="User ID who created the item")
    tags: List[TagResponse] = Field(default_factory=list, description="Associated tags")

    # Custom model config for attribute mapping
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Test Item",
                    "description": "A test item",
                    "price": 19.99,
                    "quantity": 10,
                    "is_active": True,
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z",
                    "metadata": {},
                }
            ]
        },
    }

    # Map meta_data from database to metadata for schema
    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> "ItemResponse":
        # Handle both SQLAlchemy model instances and dictionaries
        if hasattr(obj, "__dict__") and hasattr(obj, "meta_data"):
            # If the object has meta_data attribute, copy it to metadata
            # Ensure meta_data is a dictionary or convert to empty dict if None
            meta_data_value = obj.meta_data if obj.meta_data is not None else {}
            setattr(obj, "metadata", meta_data_value)
        return super().model_validate(obj, *args, **kwargs)


class ItemFilter(BaseModel):
    """
    Schema for filtering items.
    """

    status: Optional[List[ItemStatus]] = Field(None, description="Filter by status")
    type: Optional[List[ItemType]] = Field(None, description="Filter by type")
    tag_ids: Optional[List[UUID]] = Field(None, description="Filter by tags")
    search: Optional[str] = Field(None, min_length=1, description="Search term for name and description")
    created_after: Optional[datetime] = Field(None, description="Created after this timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before this timestamp")

    @field_validator("search")
    def validate_search(cls, v: Optional[str]) -> Optional[str]:
        """Validate search term."""
        if v is not None:
            return v.strip()
        return v

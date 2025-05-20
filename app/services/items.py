"""Business logic for items."""

from typing import List, Optional

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.item import Item
from app.schemas.items import ItemCreate, ItemResponse, ItemUpdate


class ItemService:
    """Service for item-related operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def get_items(
        self,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
    ) -> List[ItemResponse]:
        """Get a list of items with optional filtering."""
        query = select(Item).offset(skip).limit(limit)

        # Apply filters if provided
        if name:
            query = query.where(Item.name.ilike(f"%{name}%"))

        result = await self.db.execute(query)
        items = result.scalars().all()

        return [ItemResponse.model_validate(item) for item in items]

    async def get_item(self, item_id: int) -> Optional[ItemResponse]:
        """Get a specific item by ID."""
        query = select(Item).where(Item.id == item_id)
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()

        if not item:
            return None

        # Explicitly type the returned value to match the function's return type
        return ItemResponse.model_validate(item)

    async def create_item(self, item_data: ItemCreate) -> ItemResponse:
        """Create a new item."""
        # Create new item instance
        item_dict = item_data.model_dump(exclude_unset=True)
        # Remove any fields that aren't in the model
        if "metadata" in item_dict:
            item_dict["meta_data"] = item_dict.pop("metadata") or {}
        if "tag_ids" in item_dict:
            item_dict.pop("tag_ids")

        item = Item(**item_dict)

        # Add to DB session
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Created new item with ID {item.id}")
        # Explicitly type the returned value to match the function's return type
        response: ItemResponse = ItemResponse.model_validate(item)
        return response

    async def update_item(self, item_id: int, item_data: ItemUpdate) -> ItemResponse:
        """Update an existing item."""
        # Get existing item
        query = select(Item).where(Item.id == item_id)
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()

        if not item:
            logger.error(f"Item with ID {item_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found",
            )

        # Update item attributes
        item_data_dict = item_data.model_dump(exclude_unset=True)
        for key, value in item_data_dict.items():
            setattr(item, key, value)

        # Commit changes
        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Updated item with ID {item.id}")
        # Explicitly type the returned value to match the function's return type
        response: ItemResponse = ItemResponse.model_validate(item)
        return response

    async def delete_item(self, item_id: int) -> None:
        """Delete an item."""
        # Get existing item
        query = select(Item).where(Item.id == item_id)
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()

        if not item:
            logger.error(f"Item with ID {item_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID {item_id} not found",
            )

        # Delete item
        await self.db.delete(item)
        await self.db.commit()

        logger.info(f"Deleted item with ID {item_id}")

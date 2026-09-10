from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.schemas.farmer import FarmerCreate, FarmerUpdate


class FarmerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, farmer_id: int) -> Farmer | None:
        return self.db.get(Farmer, farmer_id)

    def get_by_code(self, farmer_code: str) -> Farmer | None:
        result = self.db.execute(
            select(Farmer).where(Farmer.farmer_code == farmer_code)
        )
        return result.scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Farmer]:
        result = self.db.execute(select(Farmer).offset(skip).limit(limit))
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(Farmer.id)))
        return result.scalar_one()

    def get_by_district(self, district: str) -> list[Farmer]:
        result = self.db.execute(select(Farmer).where(Farmer.district == district))
        return list(result.scalars().all())

    def create(self, data: FarmerCreate) -> Farmer:
        farmer = Farmer(**data.model_dump())
        self.db.add(farmer)
        self.db.commit()
        self.db.refresh(farmer)
        return farmer

    def update(self, farmer_id: int, data: FarmerUpdate) -> Farmer | None:
        farmer = self.get_by_id(farmer_id)
        if not farmer:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(farmer, field, value)
        self.db.commit()
        self.db.refresh(farmer)
        return farmer

    def delete(self, farmer_id: int) -> bool:
        farmer = self.get_by_id(farmer_id)
        if not farmer:
            return False
        self.db.delete(farmer)
        self.db.commit()
        return True

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.repositories.farmer_repo import FarmerRepository
from backend.app.schemas.farmer import FarmerCreate, FarmerUpdate

logger = logging.getLogger("backend.services.farmer")


class FarmerService:
    def __init__(self, db: Session) -> None:
        self.repo = FarmerRepository(db)

    def get_farmer(self, farmer_id: int) -> Farmer:
        farmer = self.repo.get_by_id(farmer_id)
        if not farmer:
            raise ValueError(f"Farmer with ID {farmer_id} not found")
        return farmer

    def list_farmers(self, skip: int = 0, limit: int = 100) -> tuple[list[Farmer], int]:
        farmers = self.repo.get_all(skip=skip, limit=limit)
        total = self.repo.count()
        return farmers, total

    def create_farmer(self, data: FarmerCreate) -> Farmer:
        logger.info("Creating farmer: %s (%s) in %s", data.farmer_code, data.name, data.village)
        return self.repo.create(data)

    def update_farmer(self, farmer_id: int, data: FarmerUpdate) -> Farmer:
        farmer = self.repo.update(farmer_id, data)
        if not farmer:
            raise ValueError(f"Farmer with ID {farmer_id} not found")
        logger.info("Updated farmer %s", farmer_id)
        return farmer

    def delete_farmer(self, farmer_id: int) -> bool:
        deleted = self.repo.delete(farmer_id)
        if not deleted:
            raise ValueError(f"Farmer with ID {farmer_id} not found")
        logger.info("Deleted farmer %s", farmer_id)
        return True

    def get_farmers_by_district(self, district: str) -> list[Farmer]:
        return self.repo.get_by_district(district)

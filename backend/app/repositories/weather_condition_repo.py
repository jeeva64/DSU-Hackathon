from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.weather_condition import WeatherCondition


class WeatherConditionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, weather_id: int) -> WeatherCondition | None:
        return self.db.get(WeatherCondition, weather_id)

    def get_by_date_and_location(self, target_date: date, location: str) -> WeatherCondition | None:
        result = self.db.execute(
            select(WeatherCondition).where(
                WeatherCondition.date == target_date,
                WeatherCondition.location == location,
            )
        )
        return result.scalar_one_or_none()

    def get_by_location(self, location: str, limit: int = 30) -> list[WeatherCondition]:
        result = self.db.execute(
            select(WeatherCondition)
            .where(WeatherCondition.location == location)
            .order_by(WeatherCondition.date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[WeatherCondition]:
        result = self.db.execute(
            select(WeatherCondition).order_by(WeatherCondition.date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(WeatherCondition.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> WeatherCondition:
        weather = WeatherCondition(**kwargs)
        self.db.add(weather)
        self.db.commit()
        self.db.refresh(weather)
        return weather

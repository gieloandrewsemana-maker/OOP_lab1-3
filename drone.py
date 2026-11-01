# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-26

"""Optional drone extension; imports the existing fare-engine interfaces."""

from math import ceil
from fare_engine import DeliveryVehicle, Trackable, VehicleFactory


@VehicleFactory.register("drone")
class Drone(DeliveryVehicle, Trackable):
    """Lightweight tracked drone limited to short-distance deliveries."""

    @property
    def base_fare(self) -> float:
        """Return drone base fare."""
        return 80.0

    @property
    def rate_per_km(self) -> float:
        """Return drone price per kilometer."""
        return 20.0

    @property
    def max_load_kg(self) -> float:
        """Return drone load capacity."""
        return 5.0

    def surcharge(self, distance_km: float, load_kg: float) -> float:
        """Drones do not charge a surcharge."""
        return 0.0

    def _validate(self, distance_km: float, load_kg: float) -> None:
        """Apply common validation and enforce the 10 km flight limit."""
        super()._validate(distance_km, load_kg)
        if distance_km > 10:
            raise ValueError("Drone distance cannot exceed 10 km.")

    def eta_minutes(self, distance_km: float) -> int:
        """Estimate ETA at 60 km/h."""
        return ceil(distance_km / 60.0 * 60)

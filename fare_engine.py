# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-26

"""Extensible delivery fare engine using ABCs and capability interfaces."""

from abc import ABC, abstractmethod
from math import ceil
from typing import Any


class DeliveryVehicle(ABC):
    """Base template for all delivery vehicles."""

    PEAK_MULTIPLIER = 1.0

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Prevent subclasses from replacing the fare calculation algorithm."""
        super().__init_subclass__(**kwargs)
        if "compute_fare" in cls.__dict__:
            raise TypeError("Subclasses must not override compute_fare().")

    @property
    @abstractmethod
    def base_fare(self) -> float:
        """Return the fixed base fare."""

    @property
    @abstractmethod
    def rate_per_km(self) -> float:
        """Return the price charged per kilometer."""

    @property
    @abstractmethod
    def max_load_kg(self) -> float:
        """Return the maximum supported load."""

    @abstractmethod
    def surcharge(self, distance_km: float, load_kg: float) -> float:
        """Return the vehicle-specific surcharge."""

    def _validate(self, distance_km: float, load_kg: float) -> None:
        """Reject invalid distances and loads exceeding vehicle capacity."""
        if distance_km <= 0:
            raise ValueError("Distance must be greater than zero.")
        if load_kg < 0:
            raise ValueError("Load cannot be negative.")
        if load_kg > self.max_load_kg:
            raise ValueError(f"Load exceeds maximum capacity of {self.max_load_kg:g} kg.")

    def compute_fare(self, distance_km: float, load_kg: float) -> float:
        """Calculate the final fare using the shared template algorithm."""
        self._validate(distance_km, load_kg)
        fare = (self.base_fare + self.rate_per_km * distance_km
                + self.surcharge(distance_km, load_kg)) * DeliveryVehicle.PEAK_MULTIPLIER
        return round(fare, 2)


class Insurable(ABC):
    """Capability interface for vehicles that offer shipment insurance."""

    @abstractmethod
    def insurance_fee(self, declared_value: float) -> float:
        """Calculate insurance cost for the declared shipment value."""


class Trackable(ABC):
    """Capability interface for vehicles that provide an ETA."""

    @abstractmethod
    def eta_minutes(self, distance_km: float) -> int:
        """Estimate travel time in minutes, rounded up."""


class Motorcycle(DeliveryVehicle, Trackable):
    """Motorcycle delivery vehicle with GPS tracking."""

    @property
    def base_fare(self) -> float:
        """Return motorcycle base fare."""
        return 50.0

    @property
    def rate_per_km(self) -> float:
        """Return motorcycle rate per kilometer."""
        return 10.0

    @property
    def max_load_kg(self) -> float:
        """Return motorcycle load capacity."""
        return 20.0

    def surcharge(self, distance_km: float, load_kg: float) -> float:
        """Charge an extra fee for loads above 10 kg."""
        return 20.0 if load_kg > 10 else 0.0

    def eta_minutes(self, distance_km: float) -> int:
        """Estimate ETA at 30 km/h."""
        return ceil(distance_km / 30.0 * 60)


class Car(DeliveryVehicle, Insurable, Trackable):
    """Car delivery vehicle with insurance and GPS tracking."""

    @property
    def base_fare(self) -> float:
        """Return car base fare."""
        return 100.0

    @property
    def rate_per_km(self) -> float:
        """Return car rate per kilometer."""
        return 15.0

    @property
    def max_load_kg(self) -> float:
        """Return car load capacity."""
        return 200.0

    def surcharge(self, distance_km: float, load_kg: float) -> float:
        """Add five percent of base plus distance cost for long trips."""
        base_and_distance = self.base_fare + self.rate_per_km * distance_km
        return base_and_distance * 0.05 if distance_km > 15 else 0.0

    def insurance_fee(self, declared_value: float) -> float:
        """Charge one percent of declared value, at least PHP 50."""
        return max(50.0, declared_value * 0.01)

    def eta_minutes(self, distance_km: float) -> int:
        """Estimate ETA at 25 km/h."""
        return ceil(distance_km / 25.0 * 60)


class Truck(DeliveryVehicle, Insurable):
    """Truck delivery vehicle with shipment insurance."""

    @property
    def base_fare(self) -> float:
        """Return truck base fare."""
        return 300.0

    @property
    def rate_per_km(self) -> float:
        """Return truck rate per kilometer."""
        return 25.0

    @property
    def max_load_kg(self) -> float:
        """Return truck load capacity."""
        return 2000.0

    def surcharge(self, distance_km: float, load_kg: float) -> float:
        """Charge PHP 2 for every started 100 kg of load."""
        return ceil(load_kg / 100.0) * 2.0

    def insurance_fee(self, declared_value: float) -> float:
        """Charge 1.5 percent of declared shipment value."""
        return declared_value * 0.015


class VehicleFactory:
    """Register vehicle classes and create vehicles by key."""

    _registry: dict[str, type[DeliveryVehicle]] = {}

    @classmethod
    def register(cls, key: str):
        """Return a decorator that registers a concrete vehicle class."""
        def decorator(vehicle_class: type[DeliveryVehicle]) -> type[DeliveryVehicle]:
            from inspect import isabstract
            if isabstract(vehicle_class):
                raise TypeError("Cannot register an abstract vehicle class.")
            if key in cls._registry:
                raise TypeError(f"Vehicle key already registered: {key}")
            cls._registry[key] = vehicle_class
            return vehicle_class
        return decorator

    @classmethod
    def create(cls, key: str) -> DeliveryVehicle:
        """Create a vehicle, or explain which keys are available."""
        try:
            vehicle_class = cls._registry[key]
        except KeyError as err:
            available = ", ".join(sorted(cls._registry)) or "(none)"
            raise KeyError(f"Unknown vehicle '{key}'. Available keys: {available}") from err
        return vehicle_class()

    @classmethod
    def registered(cls) -> dict[str, type[DeliveryVehicle]]:
        """Return a copy of the current vehicle registry."""
        return dict(cls._registry)


@VehicleFactory.register("motorcycle")
class RegisteredMotorcycle(Motorcycle):
    """Registered motorcycle factory entry."""


@VehicleFactory.register("car")
class RegisteredCar(Car):
    """Registered car factory entry."""


@VehicleFactory.register("truck")
class RegisteredTruck(Truck):
    """Registered truck factory entry."""


def fleet_quote(distance_km: float, load_kg: float,
                declared_value: float) -> list[dict[str, Any]]:
    """Return valid fleet quotes sorted by total cost."""
    quotes: list[dict[str, Any]] = []
    for key, vehicle_class in VehicleFactory.registered().items():
        vehicle = vehicle_class()
        try:
            fare = vehicle.compute_fare(distance_km, load_kg)
        except ValueError:
            continue
        insurance = vehicle.insurance_fee(declared_value) if isinstance(vehicle, Insurable) else None
        eta = vehicle.eta_minutes(distance_km) if isinstance(vehicle, Trackable) else None
        total = round(fare + (insurance or 0.0), 2)
        quotes.append({
            "vehicle": key,
            "fare": fare,
            "insurance": round(insurance, 2) if insurance is not None else None,
            "eta_minutes": eta,
            "total": total,
        })
    return sorted(quotes, key=lambda quote: quote["total"])


def main() -> None:
    """Print a sample fleet quote."""
    DeliveryVehicle.PEAK_MULTIPLIER = 1.0
    for quote in fleet_quote(12, 8, 5000):
        print(quote)


if __name__ == "__main__":
    main()

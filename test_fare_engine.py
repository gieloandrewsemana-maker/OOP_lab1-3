# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-26

"""Unit tests for the delivery fare engine."""

import unittest
from abc import abstractmethod
from fare_engine import (
    DeliveryVehicle, Motorcycle, Car, Truck, Insurable, Trackable,
    VehicleFactory, fleet_quote
)
import drone


class FareEngineTests(unittest.TestCase):
    """Test abstract rules, vehicle fare rules, factory, and quotes."""

    def setUp(self):
        """Reset peak multiplier before each test."""
        DeliveryVehicle.PEAK_MULTIPLIER = 1.0

    def test_abstract_base_cannot_be_instantiated(self):
        """Ensure abstract classes cannot be instantiated."""
        with self.assertRaises(TypeError):
            DeliveryVehicle()

    def test_missing_property_keeps_subclass_abstract(self):
        """Ensure missing required properties prevent instantiation."""
        class IncompleteVehicle(DeliveryVehicle):
            @property
            def base_fare(self): return 1
            @property
            def rate_per_km(self): return 1
            def surcharge(self, distance_km, load_kg): return 0
            @property
            def max_load_kg(self): return 10
        # This class is complete; the test below checks a truly incomplete class.
        class MissingProperty(DeliveryVehicle):
            @property
            def base_fare(self): return 1
            @property
            def rate_per_km(self): return 1
            def surcharge(self, distance_km, load_kg): return 0
        with self.assertRaises(TypeError):
            MissingProperty()

    def test_compute_fare_override_rejected_at_definition(self):
        """Ensure subclasses cannot replace the template method."""
        with self.assertRaises(TypeError):
            class BadVehicle(Motorcycle):
                def compute_fare(self, distance_km, load_kg):
                    return 0

    def test_motorcycle_base_fare(self):
        """Check motorcycle fare without a load surcharge."""
        self.assertEqual(Motorcycle().compute_fare(6, 3), 110.0)

    def test_motorcycle_surcharge(self):
        """Check motorcycle surcharge above 10 kg."""
        self.assertEqual(Motorcycle().compute_fare(12, 15), 190.0)

    def test_car_short_trip(self):
        """Check car fare on a short trip."""
        self.assertEqual(Car().compute_fare(6, 3), 190.0)

    def test_car_long_trip_surcharge(self):
        """Check car surcharge for trips longer than 15 km."""
        self.assertEqual(Car().compute_fare(20, 10), 420.0)

    def test_truck_started_100kg_surcharge(self):
        """Check truck charges per started 100 kg."""
        self.assertEqual(Truck().compute_fare(6, 101), 454.0)

    def test_peak_multiplier_is_shared(self):
        """Check the class-level peak multiplier."""
        DeliveryVehicle.PEAK_MULTIPLIER = 1.2
        self.assertEqual(Motorcycle().compute_fare(6, 3), 132.0)

    def test_invalid_distance(self):
        """Reject zero distance."""
        with self.assertRaises(ValueError):
            Motorcycle().compute_fare(0, 1)

    def test_over_capacity(self):
        """Reject loads exceeding capacity."""
        with self.assertRaises(ValueError):
            Motorcycle().compute_fare(2, 21)

    def test_drone_distance_limit(self):
        """Reject drone trips longer than 10 km."""
        with self.assertRaises(ValueError):
            drone.Drone().compute_fare(11, 2)

    def test_drone_load_limit(self):
        """Reject drone loads above 5 kg."""
        with self.assertRaises(ValueError):
            drone.Drone().compute_fare(5, 6)

    def test_factory_unknown_key(self):
        """Unknown factory keys report registered keys."""
        with self.assertRaisesRegex(KeyError, "Available keys"):
            VehicleFactory.create("spaceship")

    def test_factory_duplicate_key(self):
        """Duplicate registration keys are rejected."""
        with self.assertRaises(TypeError):
            VehicleFactory.register("car")(Car)

    def test_quotes_sorted_by_total(self):
        """Quotes are sorted from lowest to highest total."""
        quotes = fleet_quote(6, 3, 1000)
        totals = [quote["total"] for quote in quotes]
        self.assertEqual(totals, sorted(totals))

    def test_capability_fields(self):
        """Vehicles without capabilities receive None for those fields."""
        quotes = {quote["vehicle"]: quote for quote in fleet_quote(6, 3, 0)}
        self.assertIsNone(quotes["motorcycle"]["insurance"])
        self.assertIsNone(quotes["truck"]["eta_minutes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

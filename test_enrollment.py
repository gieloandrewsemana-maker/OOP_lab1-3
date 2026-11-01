# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-28

import unittest
from unittest.mock import patch

import enrollment as system


# Tests the course enrollment system and its exception handling.
class TestEnrollmentSystem(unittest.TestCase):

    # Resets student and course data before every test.
    def setUp(self):
        system.students.clear()
        system.students.update({
            "2024-0001": {
                "passed": ["IT112"],
                "units": 18,
                "enrolled": []
            },
            "2024-0002": {
                "passed": ["IT112", "IT211"],
                "units": 19,
                "enrolled": []
            }
        })

        system.courses.clear()
        system.courses.update({
            "IT211": {
                "title": "Data Structures",
                "units": 3,
                "prerequisites": ["IT112"],
                "schedule": "MWF 08:00-09:00",
                "capacity": 30,
                "enrolled": 0
            },
            "IT212": {
                "title": "Object-Oriented Programming",
                "units": 3,
                "prerequisites": ["IT112"],
                "schedule": "MWF 08:00-09:00",
                "capacity": 30,
                "enrolled": 0
            },
            "IT213": {
                "title": "Discrete Mathematics",
                "units": 3,
                "prerequisites": [],
                "schedule": "TTh 10:00-11:30",
                "capacity": 1,
                "enrolled": 1
            },
            "IT221": {
                "title": "Database Systems",
                "units": 3,
                "prerequisites": ["IT211"],
                "schedule": "TTh 13:00-14:30",
                "capacity": 30,
                "enrolled": 0
            },
            "IT222": {
                "title": "Networking 1",
                "units": 3,
                "prerequisites": [],
                "schedule": "Sat 08:00-11:00",
                "capacity": 30,
                "enrolled": 0
            },
            "PE3": {
                "title": "Physical Education 3",
                "units": 2,
                "prerequisites": [],
                "schedule": "Sat 13:00-15:00",
                "capacity": 30,
                "enrolled": 0
            }
        })

    # Checks that an unknown student raises the correct error.
    def test_student_not_found(self):
        with self.assertRaises(system.StudentNotFoundError) as result:
            system.get_student("2024-9999")

        self.assertIsInstance(result.exception.__cause__, KeyError)

    # Checks that an unknown course raises the correct error.
    def test_course_not_found(self):
        with self.assertRaises(system.CourseNotFoundError) as result:
            system.get_course("2024-0001", "CS999")

        self.assertIsInstance(result.exception.__cause__, KeyError)

    # Checks that a student can successfully enroll in IT211.
    def test_successful_enrollment(self):
        registrar = system.RegistrarAPI(seed=10)

        system.enroll_student(
            "2024-0001", ["IT211"], registrar
        )

        self.assertEqual(system.students["2024-0001"]["units"], 21)
        self.assertIn(
            "IT211",
            system.students["2024-0001"]["enrolled"]
        )
        self.assertEqual(system.courses["IT211"]["enrolled"], 1)

    # Checks that two courses with the same schedule conflict.
    def test_schedule_conflict(self):
        with self.assertRaises(ExceptionGroup) as result:
            system.enroll_student(
                "2024-0001",
                ["IT211", "IT212"],
                system.RegistrarAPI(seed=10)
            )

        errors = result.exception.exceptions

        self.assertTrue(
            any(isinstance(e, system.ScheduleConflictError)
                for e in errors)
        )

        self.assertEqual(system.students["2024-0001"]["units"], 18)

    # Checks that a missing prerequisite is reported.
    def test_missing_prerequisite(self):
        with self.assertRaises(ExceptionGroup) as result:
            system.enroll_student(
                "2024-0001",
                ["IT221"],
                system.RegistrarAPI(seed=10)
            )

        errors = result.exception.exceptions

        self.assertTrue(
            any(isinstance(e, system.PrerequisiteNotMetError)
                for e in errors)
        )

    # Checks that a full course section is reported.
    def test_section_full(self):
        with self.assertRaises(ExceptionGroup) as result:
            system.enroll_student(
                "2024-0001",
                ["IT213"],
                system.RegistrarAPI(seed=10)
            )

        errors = result.exception.exceptions

        self.assertTrue(
            any(isinstance(e, system.SectionFullError)
                for e in errors)
        )

    # Checks that the student cannot exceed the unit limit.
    def test_unit_limit(self):
        with self.assertRaises(ExceptionGroup) as result:
            system.enroll_student(
                "2024-0002",
                ["IT222"],
                system.RegistrarAPI(seed=10)
            )

        errors = result.exception.exceptions

        self.assertTrue(
            any(isinstance(e, system.UnitLimitExceededError)
                for e in errors)
        )

    # Checks that multiple validation errors are collected together.
    def test_exception_group_contains_three_errors(self):
        with self.assertRaises(ExceptionGroup) as result:
            system.enroll_student(
                "2024-0001",
                ["IT221", "IT213", "IT222"],
                system.RegistrarAPI(seed=10)
            )

        errors = result.exception.exceptions

        self.assertEqual(len(errors), 3)

        self.assertEqual(
            [type(error) for error in errors],
            [
                system.PrerequisiteNotMetError,
                system.SectionFullError,
                system.UnitLimitExceededError
            ]
        )

    # Checks that failed validation does not change student units.
    def test_failed_request_does_not_change_student_data(self):
        original_units = system.students["2024-0001"]["units"]
        original_courses = system.students["2024-0001"]["enrolled"].copy()

        with self.assertRaises(ExceptionGroup):
            system.enroll_student(
                "2024-0001",
                ["IT221", "IT213", "IT222"],
                system.RegistrarAPI(seed=10)
            )

        self.assertEqual(
            system.students["2024-0001"]["units"],
            original_units
        )
        self.assertEqual(
            system.students["2024-0001"]["enrolled"],
            original_courses
        )

    # Checks that IT221 and PE3 can be enrolled together.
    def test_student_two_successful_enrollment(self):
        registrar = system.RegistrarAPI(seed=10)

        system.enroll_student(
            "2024-0002",
            ["IT221", "PE3"],
            registrar
        )

        self.assertEqual(system.students["2024-0002"]["units"], 24)
        self.assertEqual(
            len(system.students["2024-0002"]["enrolled"]), 2
        )

    # Checks that registrar failure restores the original data.
    def test_rollback_after_connection_failure(self):
        original_units = system.students["2024-0001"]["units"]
        original_count = system.courses["IT211"]["enrolled"]

        class FailedRegistrar:
            # Always raises a connection error.
            @system.retry(
                times=3,
                delay=0.5,
                backoff=2,
                exceptions=(ConnectionError,)
            )
            def submit(self, student_id, course_codes):
                raise ConnectionError("Server unavailable")

        with patch("enrollment.time.sleep"):
            with self.assertRaises(ConnectionError):
                system.enroll_student(
                    "2024-0001",
                    ["IT211"],
                    FailedRegistrar()
                )

        self.assertEqual(
            system.students["2024-0001"]["units"],
            original_units
        )
        self.assertEqual(
            system.courses["IT211"]["enrolled"],
            original_count
        )
        self.assertEqual(
            system.students["2024-0001"]["enrolled"], []
        )

    # Checks that retry stops after the third failed attempt.
    def test_retry_three_failures(self):
        class FailedRegistrar:
            def __init__(self):
                self.calls = 0

            # Simulates a registrar that always fails.
            @system.retry(
                times=3,
                delay=0.5,
                backoff=2,
                exceptions=(ConnectionError,)
            )
            def submit(self, student_id, course_codes):
                self.calls += 1
                raise ConnectionError("Server unavailable")

        registrar = FailedRegistrar()

        with patch("enrollment.time.sleep") as sleep_mock:
            with self.assertRaises(ConnectionError):
                registrar.submit("2024-0001", ["IT211"])

        self.assertEqual(registrar.calls, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    # Checks that the retry succeeds on the third attempt.
    def test_retry_succeeds_on_third_attempt(self):
        class SometimesFailedRegistrar:
            def __init__(self):
                self.calls = 0

            # Fails twice and succeeds on the third attempt.
            @system.retry(
                times=3,
                delay=0.5,
                backoff=2,
                exceptions=(ConnectionError,)
            )
            def submit(self, student_id, course_codes):
                self.calls += 1

                if self.calls < 3:
                    raise ConnectionError("Temporary failure")

                return True

        registrar = SometimesFailedRegistrar()

        with patch("enrollment.time.sleep") as sleep_mock:
            result = registrar.submit("2024-0001", ["IT211"])

        self.assertTrue(result)
        self.assertEqual(registrar.calls, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    # Checks that enrollment errors are not retried.
    def test_retry_does_not_retry_enrollment_error(self):
        class InvalidRegistrar:
            def __init__(self):
                self.calls = 0

            # Raises an enrollment error immediately.
            @system.retry(
                times=3,
                delay=0.5,
                backoff=2,
                exceptions=(ConnectionError,)
            )
            def submit(self, student_id, course_codes):
                self.calls += 1
                raise system.SectionFullError(
                    student_id, "IT213"
                )

        registrar = InvalidRegistrar()

        with patch("enrollment.time.sleep") as sleep_mock:
            with self.assertRaises(system.SectionFullError):
                registrar.submit("2024-0001", ["IT213"])

        self.assertEqual(registrar.calls, 1)
        sleep_mock.assert_not_called()


# Runs all unit tests when this file is executed.
if __name__ == "__main__":
    unittest.main(verbosity=2)

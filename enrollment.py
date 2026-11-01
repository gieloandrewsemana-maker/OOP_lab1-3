# Name: Gielo Andrew L. Semaña
# Section: CJWZ2
# Date: 2026-10-28

import random
import time
import logging
from functools import wraps


# Sets up the log file for enrollment errors and rollbacks.
logging.basicConfig(
    filename="enrollment_errors.log",
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)


# Base exception class for all enrollment errors.
class EnrollmentError(Exception):
    def __init__(self, message, code, student_id):
        super().__init__(message)
        self.code = code
        self.student_id = student_id

    # Returns the readable enrollment error message.
    def __str__(self):
        return f"{self.code}: {self.args[0]} (Student: {self.student_id})"


# Raised when the requested student does not exist.
class StudentNotFoundError(EnrollmentError):
    def __init__(self, student_id):
        super().__init__(
            f"Student {student_id} was not found.",
            "E-STUDENT",
            student_id
        )


# Raised when a requested course does not exist.
class CourseNotFoundError(EnrollmentError):
    def __init__(self, student_id, course_code):
        self.course_code = course_code
        super().__init__(
            f"Course {course_code} does not exist.",
            "E-COURSE",
            student_id
        )


# Raised when the student has not completed a prerequisite.
class PrerequisiteNotMetError(EnrollmentError):
    def __init__(self, student_id, course_code, missing_courses):
        self.missing_courses = list(missing_courses)
        self.course_code = course_code
        super().__init__(
            f"{course_code} requires: {', '.join(missing_courses)}.",
            "E-PREREQ",
            student_id
        )


# Raised when two requested courses have the same schedule.
class ScheduleConflictError(EnrollmentError):
    def __init__(self, student_id, course_one, course_two):
        self.course_one = course_one
        self.course_two = course_two
        super().__init__(
            f"Schedule conflict between {course_one} and {course_two}.",
            "E-SCHEDULE",
            student_id
        )


# Raised when a course section has no available slots.
class SectionFullError(EnrollmentError):
    def __init__(self, student_id, course_code):
        self.course_code = course_code
        super().__init__(
            f"Course {course_code} is already full.",
            "E-FULL",
            student_id
        )


# Raised when enrollment exceeds the student's unit limit.
class UnitLimitExceededError(EnrollmentError):
    def __init__(self, student_id, current, requested, limit):
        self.current = current
        self.requested = requested
        self.limit = limit
        super().__init__(
            f"Unit limit exceeded: {current} + {requested} = "
            f"{current + requested}, maximum is {limit}.",
            "E-UNITS",
            student_id
        )


UNIT_LIMIT = 24


# Stores the available students and their completed courses.
students = {
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
}


# Stores course information and section enrollment counts.
courses = {
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
}


# Gets a student and preserves the original lookup error.
def get_student(student_id):
    try:
        return students[student_id]
    except KeyError as err:
        error = StudentNotFoundError(student_id)
        logging.error("%s | Code: %s", error, error.code)
        raise error from err


# Gets a course and preserves the original lookup error.
def get_course(student_id, course_code):
    try:
        return courses[course_code]
    except KeyError as err:
        error = CourseNotFoundError(student_id, course_code)
        logging.error("%s | Code: %s", error, error.code)
        raise error from err


# Checks all enrollment rules and collects every problem.
def validate(student, course_codes, student_id):
    errors = []
    requested_courses = []
    requested_units = 0

    for course_code in course_codes:
        try:
            course = get_course(student_id, course_code)
            requested_courses.append((course_code, course))
            requested_units += course["units"]

            missing = [
                prerequisite
                for prerequisite in course["prerequisites"]
                if prerequisite not in student["passed"]
                and prerequisite not in student["enrolled"]
                and prerequisite not in course_codes
            ]

            if missing:
                errors.append(
                    PrerequisiteNotMetError(
                        student_id, course_code, missing
                    )
                )

            if course["enrolled"] >= course["capacity"]:
                errors.append(
                    SectionFullError(student_id, course_code)
                )

        except CourseNotFoundError as error:
            errors.append(error)

    # Checks schedule conflicts between requested courses.
    for index, (code_one, course_one) in enumerate(requested_courses):
        for code_two, course_two in requested_courses[index + 1:]:
            if course_one["schedule"] == course_two["schedule"]:
                errors.append(
                    ScheduleConflictError(
                        student_id, code_one, code_two
                    )
                )

    # Checks the total number of requested units.
    if student["units"] + requested_units > UNIT_LIMIT:
        errors.append(
            UnitLimitExceededError(
                student_id,
                student["units"],
                requested_units,
                UNIT_LIMIT
            )
        )

    # Logs all validation errors and raises them together.
    if errors:
        for error in errors:
            logging.error("%s | Code: %s", error, error.code)

        raise ExceptionGroup(
            f"Enrollment failed for {student_id}", errors
        )

    return requested_courses


# Saves the student's and sections' original data for rollback.
class EnrollmentTransaction:
    def __init__(self, student, requested_courses):
        self.student = student
        self.requested_courses = requested_courses
        self.original_units = None
        self.original_enrolled = None
        self.original_courses = None

    # Takes a snapshot before enrollment begins.
    def __enter__(self):
        self.original_units = self.student["units"]
        self.original_courses = self.student["enrolled"].copy()

        self.original_enrolled = {
            code: course["enrolled"]
            for code, course in self.requested_courses
        }

        return self

    # Restores the original data if an error happens.
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.student["units"] = self.original_units
            self.student["enrolled"] = self.original_courses

            for code, course in self.requested_courses:
                course["enrolled"] = self.original_enrolled[code]

            logging.warning(
                "Rollback completed | Code: E-ROLLBACK | Student: %s",
                self.student.get("student_id", "Unknown")
            )

        return False


# Creates a decorator that retries selected errors.
def retry(times=3, delay=0.5, backoff=2, exceptions=(ConnectionError,)):

    # Wraps a function with retry behavior.
    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):
            current_delay = delay

            for attempt in range(times):
                try:
                    return function(*args, **kwargs)

                except exceptions as error:
                    logging.warning(
                        "Retry attempt %s/%s | Code: E-CONNECTION | %s",
                        attempt + 1, times, error
                    )

                    if attempt == times - 1:
                        raise

                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper

    return decorator


# Simulates the registrar server with a 40% failure chance.
class RegistrarAPI:
    def __init__(self, seed=None):
        self.random = random.Random(seed)

    # Submits an enrollment request to the registrar.
    @retry(times=3, delay=0.5, backoff=2,
           exceptions=(ConnectionError,))
    def submit(self, student_id, course_codes):
        if self.random.random() < 0.40:
            raise ConnectionError("Registrar server connection failed.")

        return True


# Enrolls a student in all requested courses or none.
def enroll_student(student_id, course_codes, registrar):
    student = get_student(student_id)
    student["student_id"] = student_id

    requested_courses = validate(student, course_codes, student_id)

    with EnrollmentTransaction(student, requested_courses):
        registrar.submit(student_id, course_codes)

        for course_code, course in requested_courses:
            student["units"] += course["units"]
            student["enrolled"].append(course_code)
            course["enrolled"] += 1

    return True


# Displays the current enrollment information.
def display_student(student_id):
    try:
        student = get_student(student_id)
        print("\nStudent ID:", student_id)
        print("Current units:", student["units"])
        print("Enrolled courses:", student["enrolled"])

    except StudentNotFoundError as error:
        print(error)


# Runs the menu-driven enrollment system.
def main():
    registrar = RegistrarAPI(seed=42)

    while True:
        print("\n===== COURSE ENROLLMENT SYSTEM =====")
        print("1. Enroll in courses")
        print("2. View student enrollment")
        print("3. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            student_id = input("Enter Student ID: ")
            course_input = input(
                "Enter course codes separated by commas: "
            )
            course_codes = [
                code.strip().upper()
                for code in course_input.split(",")
                if code.strip()
            ]

            try:
                enroll_student(student_id, course_codes, registrar)
                print("Enrollment successful!")

            except* PrerequisiteNotMetError as group:
                for error in group.exceptions:
                    print(
                        "Missing prerequisite:",
                        error.course_code,
                        "requires",
                        ", ".join(error.missing_courses)
                    )

            except* ScheduleConflictError as group:
                for error in group.exceptions:
                    print(
                        "Schedule conflict:",
                        error.course_one,
                        "and",
                        error.course_two,
                        "cannot be taken together."
                    )

            except* (SectionFullError, UnitLimitExceededError) as group:
                for error in group.exceptions:
                    print(error)

            except* CourseNotFoundError as group:
                for error in group.exceptions:
                    print(error)

            except* ConnectionError:
                print("Registrar unavailable, try again later")

            finally:
                display_student(student_id)

        elif choice == "2":
            student_id = input("Enter Student ID: ")
            display_student(student_id)

        elif choice == "3":
            print("Thank you for using the system!")
            break

        else:
            print("Invalid choice. Please try again.")


# Starts the program when this file is executed directly.
if __name__ == "__main__":
    main()

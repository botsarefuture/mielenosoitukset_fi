### Documentation for Demonstration Management System

---

#### Table of Contents
1. [Class Overview](#class-overview)
2. [Functionality Overview](#functionality-overview)
3. [Classes](#classes)
   - [BaseModel](#basemodel)
   - [RepeatSchedule](#repeatschedule)
   - [Organizer](#organizer)
   - [Organization](#organization)
   - [Demonstration](#demonstration)
   - [RecurringDemonstration](#recurringdemonstration)

---

### Class Overview
This documentation covers a set of classes designed for managing demonstrations, organizers, and organizations within a Flask application using MongoDB.

### Functionality Overview
- **Data Management**: Easily manage demonstration events and their associated data (organizers, organizations).
- **Recurring Events**: Support for scheduling and handling recurring demonstrations.
- **Validation**: Ensure data integrity with built-in validation methods.

---

### Classes

#### BaseModel
A mixin class providing common methods for data serialization and deserialization.

**Methods:**
- `from_dict(data: dict)`: Creates an instance from a dictionary.
- `to_dict(json: bool = False)`: Converts an instance to a dictionary format.

---

#### RepeatSchedule
Represents the scheduling frequency for recurring events.

**Attributes:**
- `frequency (str)`: Type of frequency (daily, weekly, monthly, yearly).
- `interval (int)`: Interval count for the frequency.
- `weekday (Optional[datetime])`: Day of the week for weekly events.

**Methods:**
- `__str__()`: Returns a string representation of the repeat schedule.
- `to_dict()`: Converts the schedule to a dictionary.
- `from_dict(data: dict)`: Creates a RepeatSchedule instance from a dictionary.

---

#### Organizer
Represents an organizer for demonstrations.

**Attributes:**
- `name (str)`: Name of the organizer.
- `email (str)`: Email of the organizer.
- `organization_id (ObjectId)`: Reference to the associated organization.
- `website (str)`: Website of the organizer.
- `url (str)`: URL to the organizer’s page.

**Methods:**
- `to_dict(json: bool = False)`: Converts the organizer to a dictionary.
- `fetch_organization_details()`: Retrieves organization details from the database.
- `validate_organization_id()`: Validates the existence of the associated organization.

---

#### Organization
Represents an organization involved in demonstrations.

**Attributes:**
- `name (str)`: Name of the organization.
- `description (str)`: Description of the organization.
- `website (str)`: Website link for the organization.
- `social_media (dict)`: Social media links for the organization.
- `demonstrations (list)`: List of associated demonstrations.
- `users (dict)`: User data associated with the organization.
- `_id (ObjectId)`: Unique identifier for the organization.

**Methods:**
- `save()`: Saves or updates the organization in the database.

---

#### Demonstration
Represents a demonstration event.

**Attributes:**
- `title (str)`: Title of the demonstration.
- `date (str)`: Date of the event.
- `start_time (str)`: Start time of the event.
- `end_time (str)`: End time of the event.
- `facebook (str)`: Facebook link for the event.
- `city (str)`: City where the event will take place.
- `address (str)`: Address of the event.
- `route (str)`: Route for the demonstration if applicable.
- `organizers (list)`: List of organizers associated with the demonstration.
- `approved (bool)`: Approval status of the demonstration.
- `linked_organizations (dict)`: Associated organizations.
- `img (str)`: Image link for the demonstration.
- `_id (ObjectId)`: Unique identifier for the demonstration.
- `description (str)`: Description of the demonstration.
- `tags (list)`: Tags related to the event.
- `created_datetime`: Date and time when the event was created.
- `recurring (bool)`: Indicates if the event is recurring.
- `repeat_schedule (RepeatSchedule)`: Schedule for recurring events.

**Deprecation Notice:**
- The `topic` field has been deprecated since version **2.2.0** and will be completely removed in version **2.3.0**.

**Methods:**
- `to_dict(json: bool = False)`: Converts the demonstration to a dictionary.
- `validate_fields(...)`: Validates required fields for the demonstration.
- `save()`: Saves or updates the demonstration in the database.

---

#### RecurringDemonstration
Extends the `Demonstration` class for managing recurring demonstrations.

**Attributes:**
- `created_until (datetime)`: End date for the recurring events.
- `repeat_schedule (RepeatSchedule)`: Schedule for the recurring events.

**Methods:**
- `calculate_next_dates()`: Calculates the next occurrence dates based on the frequency and interval.

---

### Example Usage

```python
# Creating an Organizer
organizer_data = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "organization_id": ObjectId("60d5f9d1e3d1e73f1c9d7201"),
    "website": "http://example.com"
}
organizer = Organizer.from_dict(organizer_data)

# Creating a Demonstration
demo = Demonstration(
    title="Climate March",
    date="2024-03-01",
    start_time="12:00",
    end_time="15:00",
    facebook="http://facebook.com/event",
    city="Helsinki",
    address="Main Street",
    route="Route 66",
    organizers=[organizer],
    approved=True,
    img="http://example.com/image.jpg"
)
demo.save()
```

### Conclusion
This documentation provides a comprehensive overview of the classes and their functionalities within the demonstration management system. You can extend this documentation further based on your specific implementation details or user needs.

Feel free to adjust any sections or add specific examples that are relevant to your use case! 💖
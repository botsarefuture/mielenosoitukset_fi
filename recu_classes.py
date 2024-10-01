from datetime import datetime
from dateutil.relativedelta import relativedelta

class RepeatSchedule:
    def __init__(self, frequency, interval, weekday=None):
        self.frequency = frequency
        self.interval = interval
        self.weekday = weekday
        print(self.weekday)  # Optional, to specify the weekday for weekly repeats

    def __str__(self):
        frequency_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "yearly": "yearly"
        }
        
        # Check for weekday if frequency is weekly
        weekday_str = ""
        if self.frequency == "weekly" and self.weekday is not None:
            weekday_name = self.weekday.strftime("%A")  # Get the full name of the weekday
            weekday_str = f" on {weekday_name}"

        if self.frequency in frequency_map:
            if self.interval == 1:
                return frequency_map[self.frequency] + weekday_str
            else:
                return f"every {self.interval} {frequency_map[self.frequency]}{'s' if self.interval > 1 else ''}{weekday_str}"
        
        return "unknown frequency"
    
    def to_dict(self):
        return {
            "frequency": self.frequency,
            "interval": self.interval,
            "weekday": self.weekday if self.weekday else None,
            "as_string": self.__str__()
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(frequency=data["frequency"], interval=data["interval"], weekday=data["weekday"])


class RecurringDemonstration:
    def __init__(self, title, start_time, end_time, topic, facebook, city, address, demo_type, route, organizers=None, linked_organizations=None, repeat_schedule: RepeatSchedule = None, created_until=None, _id=None):
        self.title = title
        self.start_time = start_time  # Should be a datetime object
        self.end_time = end_time  # Should be a datetime object
        self.topic = topic
        self.facebook = facebook
        self.city = city
        self.address = address
        self.type = demo_type
        self.route = route
        self.organizers = organizers or []  # Default to empty list if not provided
        self.linked_organizations = linked_organizations or []  # Default to empty list if not provided
        self.repeat_schedule = repeat_schedule  
        self.created_until = created_until or datetime.now()  # Default to now if not provided
        self.created_datetime = datetime.now()  # Time of creation
        self._id = _id  # This will be set when stored in the database

    def calculate_next_dates(self):
        """Calculate the next demonstration dates based on the frequency and interval."""
        current_date = datetime.now()
        next_dates = []
        end_date = current_date + relativedelta(years=1)

        demo_date = self.start_time
        while demo_date <= end_date:
            if demo_date > self.created_until:
                next_dates.append(demo_date)
            
            if self.repeat_schedule.frequency == "daily":
                demo_date += relativedelta(days=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "weekly":
                if self.repeat_schedule.weekday:
                    # Calculate next occurrence on the specified weekday
                    days_ahead = (self.repeat_schedule.weekday - demo_date.weekday() + 7) % 7
                    demo_date += relativedelta(weeks=self.repeat_schedule.interval, days=days_ahead)
                else:
                    demo_date += relativedelta(weeks=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "monthly":
                demo_date += relativedelta(months=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "yearly":
                demo_date += relativedelta(years=self.repeat_schedule.interval)

        return next_dates


    def update_demo(self, title=None, start_time=None, end_time=None, topic=None, facebook=None, city=None, address=None, demo_type=None, route=None, organizers=None, linked_organizations=None):
        """Update demonstration details."""
        if title:
            self.title = title
        if start_time:
            self.start_time = start_time
        if end_time:
            self.end_time = end_time
        if topic:
            self.topic = topic
        if facebook:
            self.facebook = facebook
        if city:
            self.city = city
        if address:
            self.address = address
        if demo_type:
            self.type = demo_type
        if route:
            self.route = route
        if organizers is not None:  # Allow updating to empty list
            self.organizers = organizers or []
        if linked_organizations is not None:  # Allow updating to empty list
            self.linked_organizations = linked_organizations or []

    def to_dict(self):
        """Convert the object to a dictionary for easy storage in a database."""
        return {
            "title": self.title,
            "start_time": self.start_time.strftime("%d.%m.%Y %H:%M"),
            "end_time": self.end_time.strftime("%d.%m.%Y %H:%M"),
            "topic": self.topic,
            "facebook": self.facebook,
            "city": self.city,
            "address": self.address,
            "type": self.type,
            "route": self.route,
            "organizers": self.organizers,
            "linked_organizations": self.linked_organizations,
            "repeat_schedule": self.repeat_schedule.to_dict(),
            "created_until": self.created_until.strftime("%d.%m.%Y") if self.created_until and not self.created_until is None else datetime.now(),
            "created_datetime": self.created_datetime.strftime("%d.%m.%Y %H:%M"),
            "_id": str(self._id if not self._id is not None else "None")
        }

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary."""
        start_time_str = data["start_time"]
        end_time_str = data["end_time"]
        
        # Attempt to parse the datetime strings
        start_time = datetime.strptime(start_time_str, "%d.%m.%Y %H:%M") if len(start_time_str) > 5 else None
        end_time = datetime.strptime(end_time_str, "%d.%m.%Y %H:%M") if len(end_time_str) > 5 else None
        
        created_until = datetime.strptime(data["created_until"], "%d.%m.%Y") if data.get("created_until") and data.get("created_until") is not None else datetime.now()
        


        return cls(
            title=data["title"],
            start_time=start_time,
            end_time=end_time,
            topic=data["topic"],
            facebook=data["facebook"],
            city=data["city"],
            address=data["address"],
            demo_type=data["type"],
            route=data["route"],
            organizers=data.get("organizers", []),
            linked_organizations=data.get("linked_organizations", []),
            repeat_schedule=RepeatSchedule.from_dict(data.get("repeat_schedule")),
            created_until=created_until,
            _id=data["_id"]
        )

    def __repr__(self):
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"

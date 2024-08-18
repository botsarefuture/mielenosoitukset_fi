from database_manager import DatabaseManager
from bson.objectid import ObjectId

class Organizer:
    def __init__(self, name: str = None, email: str = None, organization_id: str = None, website: str = None):
        self.name = name
        self.email = email
        self.organization_id = organization_id
        self.website = website

        if organization_id:
            self.fetch_organization_details()

    def fetch_organization_details(self):
        """Fetch the organization details from the database using the organization_id."""
        db_manager = DatabaseManager()
        db = db_manager.get_db()

        # Fetch organization details
        organization = db['organizations'].find_one({"_id": ObjectId(self.organization_id)})

        if organization:
            self.name = organization.get('name')
            self.email = organization.get('email')
            self.website = organization.get('website')

    def to_dict(self):
        return {
            'name': self.name,
            'email': self.email,
            'organization_id': self.organization_id,
            'website': self.website
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get('name'),
            email=data.get('email'),
            organization_id=data.get('organization_id'),
            website=data.get('website')
        )


class Demonstration:
    def __init__(self, title: str, date: str, start_time: str, end_time: str, topic: str, 
                 facebook: str, city: str, address: str, event_type: str, route: str, 
                 organizers: list[Organizer] = None, approved: bool = False, 
                 linked_organizations: dict = None):
        self.title = title
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.topic = topic
        self.facebook = facebook
        self.city = city
        self.address = address
        self.event_type = event_type
        self.route = route
        self.organizers = organizers if organizers is not None else []
        self.approved = approved
        # Dictionary to store organizations and their editing rights
        self.linked_organizations = linked_organizations if linked_organizations is not None else {}

    def to_dict(self):
        return {
            'title': self.title,
            'date': self.date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'topic': self.topic,
            'facebook': self.facebook,
            'city': self.city,
            'address': self.address,
            'type': self.event_type,
            'route': self.route,
            'organizers': [organizer.to_dict() for organizer in self.organizers],
            'approved': self.approved,
            # Convert linked_organizations to a serializable format
            'linked_organizations': self.linked_organizations
        }

    @classmethod
    def from_dict(cls, data):
        organizers = [Organizer.from_dict(org) for org in data.get('organizers', [])] if data.get('organizers') else []
        return cls(
            title=data['title'],
            date=data['date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            topic=data['topic'],
            facebook=data.get('facebook'),
            city=data['city'],
            address=data['address'],
            event_type=data['type'],
            route=data.get('route'),
            organizers=organizers,
            approved=data.get('approved', False),
            # Convert linked_organizations back from the dictionary format
            linked_organizations=data.get('linked_organizations', {})
        )

    def link_organization(self, organization_id: str, can_edit: bool):
        self.linked_organizations[organization_id] = can_edit

    def can_edit(self, organization_id: str) -> bool:
        return self.linked_organizations.get(organization_id, False)

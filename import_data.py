from app import app, db, User, Event, Registration
import json
from datetime import datetime

def import_data():
    with app.app_context():
        with open('data_backup.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # מחיקת כל הנתונים הקיימים
        Registration.query.delete()
        Event.query.delete()
        User.query.delete()
        
        # יבוא משתמשים
        for user_data in data['users']:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                is_admin=user_data['is_admin']
            )
            db.session.add(user)
        
        # יבוא אירועים
        for event_data in data['events']:
            event = Event(
                id=event_data['id'],
                title=event_data['title'],
                description=event_data['description'],
                date=datetime.fromisoformat(event_data['date']),
                location=event_data['location'],
                capacity=event_data['capacity'],
                image_url=event_data['image_url']
            )
            db.session.add(event)
        
        # יבוא הרשמות
        for reg_data in data['registrations']:
            reg = Registration(
                id=reg_data['id'],
                user_id=reg_data['user_id'],
                event_id=reg_data['event_id'],
                registration_date=datetime.fromisoformat(reg_data['registration_date'])
            )
            db.session.add(reg)
        
        db.session.commit()

if __name__ == '__main__':
    import_data() 
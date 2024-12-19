from app import app, db, User, Event, Registration
import json

def export_data():
    with app.app_context():
        # יצירת הטבלאות אם הן לא קיימות
        db.create_all()
        
        users = User.query.all()
        events = Event.query.all()
        registrations = Registration.query.all()

        data = {
            'users': [{
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'password_hash': user.password_hash,
                'is_admin': user.is_admin
            } for user in users],
            
            'events': [{
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': event.date.isoformat(),
                'location': event.location,
                'capacity': event.capacity,
                'image_url': event.image_url
            } for event in events],
            
            'registrations': [{
                'id': reg.id,
                'user_id': reg.user_id,
                'event_id': reg.event_id,
                'registration_date': reg.registration_date.isoformat()
            } for reg in registrations]
        }

        with open('data_backup.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("Data exported successfully!")

if __name__ == '__main__':
    export_data() 
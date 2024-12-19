from app import app, db, User
from werkzeug.security import generate_password_hash
from datetime import datetime, UTC

def init_database():
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Check if admin user already exists
        existing_admin = User.query.filter_by(email='motiwolff@gmail.com').first()
        if not existing_admin:
            # Create an initial admin user
            admin = User(
                email='motiwolff@gmail.com',
                password=generate_password_hash('MotiSterni5784'),
                is_admin=True,
                created_at=datetime.now(UTC)
            )
            
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        else:
            print("Admin user already exists!")

if __name__ == '__main__':
    init_database()
    print("Database initialized!") 
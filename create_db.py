from flask import Flask
# CHỈ IMPORT các model cần thiết
from models import db, User, ActivityLog 

# Khởi tạo App tối thiểu và cấu hình DB
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def create_initial_data():
    """Tạo database và tài khoản Admin mặc định."""
    # Khởi tạo DB với app object
    db.init_app(app) 
    
    with app.app_context():
        # 1. Tạo tất cả các bảng (User và ActivityLog)
        db.create_all()
        print("Database tables created/updated successfully.")

        # 2. Tạo tài khoản Admin nếu chưa tồn tại
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', email='admin@example.com', role='admin')
            u.set_password('AdminPass123')
            db.session.add(u)
            db.session.commit()
            print("Default Admin account created: admin/AdminPass123")
        else:
            print("Admin account already exists.")

if __name__ == '__main__':
    create_initial_data()
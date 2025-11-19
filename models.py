from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    # Định nghĩa cấu trúc bảng users
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(30), default='user')  # 'admin', 'user', 'manager'
    
    # Mối quan hệ với ActivityLog
    activities = db.relationship('ActivityLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

# Bảng lưu log hoạt động (Đáp ứng yêu cầu Báo cáo)
class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<ActivityLog {self.id}: {self.action} by {self.user_id}>'
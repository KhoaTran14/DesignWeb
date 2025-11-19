from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
# CHỈ IMPORT db VÀ User TẠI ĐÂY. BỎ ActivityLog để tránh lỗi cache/ImportError.
from models import db, User 
import os
from functools import wraps
from sqlalchemy.exc import IntegrityError 

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# init extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# HÀM MỚI: Ghi lại hoạt động vào DB
def log_activity(user_id, action, details=''):
    # IMPORT ActivityLog BÊN TRONG HÀM để tránh lỗi module cấp cao
    from models import ActivityLog 
    try:
        log_entry = ActivityLog(user_id=user_id, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        # Nếu ghi log lỗi, chỉ in ra console, không làm sập request chính
        print(f"Error logging activity: {e}")
        db.session.rollback()


# user loader cho flask-login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home -> redirect to dashboard hoặc login
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        
        # validate minimal
        if not username or not email or not password:
            flash('Vui lòng điền đủ thông tin', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter((User.username==username) | (User.email==email)).first():
            flash('Username hoặc Email đã tồn tại', 'warning')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        
        try:
            db.session.commit()
            log_activity(user.id, 'User Registered', f'New user {username} created.')
        except IntegrityError:
            db.session.rollback()
            flash('Lỗi hệ thống: Không thể đăng ký.', 'danger')
            return redirect(url_for('register'))
        
        flash('Đăng ký thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

# Login
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            log_activity(user.id, 'User Login') # LOG ĐĂNG NHẬP
            flash('Đăng nhập thành công', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
            
        flash('Sai username hoặc password', 'danger')
        return redirect(url_for('login'))
        
    return render_template('login.html')

# Dashboard (cho tất cả user đã đăng nhập)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# Decorator kiểm tra quyền admin
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Bạn không có quyền truy cập (Chỉ dành cho Admin)', 'danger')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/admin')
@admin_required
def admin():
    users = User.query.all()
    return render_template('admin.html', users=users)

# NEW: Route xem báo cáo hoạt động (chỉ Admin)
@app.route('/admin/logs')
@admin_required
def activity_logs():
    # IMPORT ActivityLog BÊN TRONG HÀM
    from models import ActivityLog 
    # Lấy 100 log gần nhất
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('activity_logs.html', logs=logs)


# Change role (admin only)
@app.route('/admin/role/<int:user_id>/<role>')
@admin_required
def change_role(user_id, role):
    user = User.query.get_or_404(user_id)
    valid_roles = ['admin', 'manager', 'user']
    if role not in valid_roles:
        flash('Vai trò không hợp lệ.', 'danger')
        return redirect(url_for('admin'))
    
    old_role = user.role
    user.role = role
    db.session.commit()
    log_activity(current_user.id, 'Role Changed', f'Admin changed {user.username} role from {old_role} to {role}.')
    flash(f'Đã cập nhật role cho {user.username} thành {role}.', 'success')
    return redirect(url_for('admin'))

# Delete user (admin only)
@app.route('/admin/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Bạn không thể tự xóa tài khoản của chính mình.', 'warning')
        return redirect(url_for('admin'))

    username = user.username # Lưu lại tên trước khi xóa
    db.session.delete(user)
    db.session.commit()
    log_activity(current_user.id, 'User Deleted', f'Admin deleted user: {username} (ID: {user_id}).')
    flash(f'Đã xóa user {username}.', 'success')
    return redirect(url_for('admin'))

# Edit User Profile
@app.route('/profile/edit', defaults={'user_id': None}, methods=['GET', 'POST'])
@app.route('/admin/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Xác định user cần chỉnh sửa (tài khoản của chính mình hoặc Admin sửa người khác)
    if user_id is None:
        user_to_edit = current_user
        redirect_url = url_for('dashboard')
    else:
        # Nếu user_id được cung cấp, chỉ Admin mới được phép
        if not current_user.is_admin():
            flash('Bạn không có quyền chỉnh sửa tài khoản người dùng khác.', 'danger')
            return redirect(url_for('dashboard'))
        user_to_edit = User.query.get_or_404(user_id)
        redirect_url = url_for('admin')

    if request.method == 'POST':
        new_username = request.form['username'].strip()
        new_email = request.form['email'].strip()
        new_password = request.form['password']
        
        # Kiểm tra username/email đã tồn tại (trừ chính user đang sửa)
        existing_user = User.query.filter(
            (User.username == new_username) | (User.email == new_email)
        ).filter(User.id != user_to_edit.id).first()
        
        if existing_user:
            flash('Username hoặc Email đã được người khác sử dụng.', 'warning')
            return redirect(request.url)

        is_password_changed = False
        if new_password:
            user_to_edit.set_password(new_password)
            is_password_changed = True

        user_to_edit.username = new_username
        user_to_edit.email = new_email
        
        db.session.commit()
        
        # Ghi log hoạt động
        if user_id is None:
            log_activity(current_user.id, 'Profile Updated', f'Updated own profile. Password changed: {is_password_changed}')
        else:
            log_activity(current_user.id, 'User Edited by Admin', f'Admin edited profile of {user_to_edit.username}. Password changed: {is_password_changed}')

        flash(f'Đã cập nhật thông tin cho {user_to_edit.username}.', 'success')
        return redirect(redirect_url)

    # Nếu là GET request
    return render_template('edit_user.html', user=user_to_edit)

# Logout
@app.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'User Logout') # LOG ĐĂNG XUẤT
    logout_user()
    flash('Đã đăng xuất', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Đảm bảo DB được tạo và Admin tồn tại khi chạy
    with app.app_context():
        # Phải gọi create_all ở đây để tạo cả bảng ActivityLog
        db.create_all() 
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', email='admin@example.com', role='admin')
            u.set_password('AdminPass123')
            db.session.add(u)
            db.session.commit()
            print("Đã tạo tài khoản Admin mặc định: admin/AdminPass123")
            
    app.run(debug=True)
from flask import render_template, flash, redirect, url_for, request
from app import app
from app.forms import LoginForm, RegistrationForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app import db
from app.models import User, Dialog, Message
from urllib.parse import urlsplit
from datetime import datetime


@app.route('/')
@app.route('/index')
@login_required
def index():
  user = {'username': 'Magomed'}
  posts = [
    {
      'author': {'username': 'John'},
      'body': 'Beautiful day in Portland!'
    },
    {
      'author': {'username': 'Susan'},
      'body': 'The Avengers movie was so cool!'
    }
  ]
  return render_template('index.html', title='Home', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
  if current_user.is_authenticated:
    return redirect(url_for('index'))
  form = LoginForm()
  if form.validate_on_submit():
    user = db.session.scalar(
      sa.select(User).where(User.username == form.username.data))
    if user is None or not user.check_password(form.password.data):
      flash('Invalid username or password')
      return redirect(url_for('login'))
    login_user(user, remember=form.remember_me.data)
    next_page = request.args.get('next')
    if not next_page or urlsplit(next_page).netloc != '':
      next_page = url_for('index')
    return redirect(next_page)
  return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

def get_or_create_dialog(user1_id, user2_id):
  small_id = min(user1_id, user2_id)
  large_id = max(user1_id, user2_id)
  
  # Ищем существующий диалог
  dialog = Dialog.query.filter_by(user1_id=small_id, user2_id=large_id).first()
  
  # Если нет — создаем
  if not dialog:
    dialog = Dialog(user1_id=small_id,user2_id=large_id)
    db.session.add(dialog)
    db.session.commit()
  
  return dialog

@app.route('/chats')
@login_required
def chats():
  #Ищем в бд диалоги 
  dialogs_as_user1 = Dialog.query.filter_by(user1_id=current_user.id).all()
  dialogs_as_user2 = Dialog.query.filter_by(user2_id=current_user.id).all()
  
  #Объединяем диалоги в один
  all_dialogs = dialogs_as_user1 + dialogs_as_user2
  #Сортируем диалоги от новых сообщений к старым 
  all_dialogs.sort(key=lambda x: x.updated_at, reverse=True)
  
  return render_template('chats.html', dialogs=all_dialogs)

@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):

  if user_id == current_user.id:
    flash('Нельзя начать чат с самим собой')
    return redirect(url_for('chats'))

  #Получаем или создаем диалог
  dialog = get_or_create_dialog(current_user.id, user_id)
  
  #Получаем собеседника
  other_user = User.query.get(user_id)
  
  if request.method == 'POST':
    content = request.form.get('message')
    if content:
      message = Message(content=content,dialog_id=dialog.id,sender_id=current_user.id)
      db.session.add(message)
      dialog.updated_at = datetime.utcnow()
      db.session.commit()
      return redirect(url_for('chat', user_id=user_id))
  
  # Получаем все сообщения диалога
  messages = Message.query.filter_by(dialog_id=dialog.id).order_by(Message.timestamp).all()
  
  # Помечаем сообщения как прочитанные
  for msg in messages:
    if msg.sender_id != current_user.id and not msg.is_read:
      msg.is_read = True
  db.session.commit()
  
  return render_template('chat.html', dialog=dialog,  messages=messages, other_user=other_user)

@app.route('/search_users', methods=['GET', 'POST'])
@login_required
def search_users():
  users = []
  if request.method == 'POST':
    #Достаем из формы значение поля 
    search = request.form.get('search')
    if search:
      users = User.query.filter(User.username.contains(search), User.id != current_user.id).limit(10).all()
  return render_template('search_users.html', users=users)

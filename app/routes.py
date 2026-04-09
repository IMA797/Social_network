from flask import render_template, flash, redirect, session, url_for, request, jsonify
from app import app, socketio
from app.forms import LoginForm, RegistrationForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app import db
from app.models import User, Dialog, Message
from urllib.parse import urlsplit
from datetime import datetime, timedelta
from flask_socketio import emit, join_room, disconnect
import json
from app.email_utils import generate_code, send_confirmation_email


@app.route('/')
@app.route('/index')
@login_required
def index():
  return render_template('index.html', title='Profile')

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    about_me = request.form.get('about_me', '').strip()
    current_user.about_me = about_me
    db.session.commit()
    flash('Профиль обновлён!', 'success')
    return redirect(url_for('index'))

#Функция просмотра (принимает запросы GET и POST)
@app.route('/login', methods=['GET', 'POST'])
def login():
  if current_user.is_authenticated:
    return redirect(url_for('index'))
  #Создаем экземпляр объекта
  form = LoginForm()
  #При GET запросе данное условие опускается, при POST выполняется
  #А также проверка, то что в файле forms.py в аргументе validators
  if form.validate_on_submit():
    user = db.session.scalar(
      sa.select(User).where(User.username == form.username.data))
    if user is None or not user.check_password(form.password.data):
      #Вывод ошибки пользователю
      flash('Invalid username or password', 'error')
      #Переход на другую страницу 
      return redirect(url_for('login'))
    login_user(user, remember=form.remember_me.data)
    #Получение параметра next из url
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
    # Проверяем, не занят ли email
    existing_user = User.query.filter_by(email=form.email.data).first()
    if existing_user:
      flash('Email уже зарегистрирован', 'error')
      return redirect(url_for('register'))
    
    # Проверяем, не занято ли имя
    existing_username = User.query.filter_by(username=form.username.data).first()
    if existing_username:
      flash('Имя пользователя уже занято', 'error'
            
            )
      return redirect(url_for('register'))
    
    session['pending_username'] = form.username.data
    session['pending_email'] = form.email.data
    session['pending_password'] = form.password.data
    
    # Генерируем код
    from app.email_utils import generate_code, send_confirmation_email
    code = generate_code()
    session['pending_code'] = code
    session['pending_code_expires'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()
    
    # Отправляем код на email
    if send_confirmation_email(form.email.data, code):
      flash('Код подтверждения отправлен на ваш email', 'info')
      return redirect(url_for('confirm_registration'))
    else:
      flash('Ошибка отправки письма. Попробуйте позже.', 'error')
  
  return render_template('register.html', title='Register', form=form) 

@app.route('/confirm_registration', methods=['GET', 'POST'])
def confirm_registration():
  # Проверяем, есть ли данные в сессии
  if not session.get('pending_username'):
      flash('Сессия истекла. Зарегистрируйтесь заново.')
      return redirect(url_for('register'))
  
  if request.method == 'POST':
    user_code = request.form.get('code')
    expected_code = session.get('pending_code')
    expires = session.get('pending_code_expires')
    
    # Проверяем код
    if user_code == expected_code and datetime.utcnow().timestamp() < expires:
      user = User(
          username=session['pending_username'],
          email=session['pending_email']
      )
      user.set_password(session['pending_password'])
      db.session.add(user)
      db.session.commit()
      
      # Очищаем сессию
      session.pop('pending_username', None)
      session.pop('pending_email', None)
      session.pop('pending_password', None)
      session.pop('pending_code', None)
      session.pop('pending_code_expires', None)
      
      flash('Регистрация завершена! Теперь вы можете войти.', 'success')
      return redirect(url_for('login'))
    else:
      flash('Неверный или истёкший код', 'error')
  
  return render_template('confirm_registration.html', email=session.get('pending_email'))

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
  # Находим диалоги
  dialogs_as_user1 = Dialog.query.filter_by(user1_id=current_user.id).all()
  dialogs_as_user2 = Dialog.query.filter_by(user2_id=current_user.id).all()
  
  # Объединяем все диалоги
  all_dialogs = dialogs_as_user1 + dialogs_as_user2
  
  # Для каждого диалога получаем последнее сообщение и собеседника
  dialog_data = []
  for dialog in all_dialogs:
    # Определяем собеседника
    if dialog.user1_id == current_user.id:
      other_user = dialog.user2
    else:
      other_user = dialog.user1
    
    # Получаем последнее сообщение
    last_message = Message.query.filter_by(dialog_id=dialog.id).order_by(Message.timestamp.desc()).first()
    
    dialog_data.append({'dialog': dialog,'other_user': other_user,'last_message': last_message})
  
  # Сортируем по времени последнего сообщения
  dialog_data.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
  
  return render_template('chats.html', dialog_data=dialog_data)


@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):

  if user_id == current_user.id:
    flash('Нельзя начать чат с самим собой', 'error')
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

@app.route('/confirm_email', methods=['GET', 'POST'])
def confirm_email():
  # Получаем ID пользователя из сессии
  user_id = session.get('pending_user_id')
  if not user_id:
      flash('Сессия истекла. Зарегистрируйтесь заново.', 'error')
      return redirect(url_for('register'))
  
  user = User.query.get(user_id)
  if not user:
      session.pop('pending_user_id', None)
      flash('Пользователь не найден', 'error')
      return redirect(url_for('register'))
  
  # Если уже подтверждён
  if user.email_confirmed:
      session.pop('pending_user_id', None)
      flash('Email уже подтверждён', 'success')
      return redirect(url_for('login'))
  
  # Проверяем, не истёк ли код
  if user.code_expires is None or datetime.utcnow() > user.code_expires:
      flash('Код истёк. Запросите новый.', 'error')
      return redirect(url_for('resend_code'))
  
  if request.method == 'POST':
      code = request.form.get('code')
      
      if code == user.confirmation_code:
          # Подтверждаем email
          user.email_confirmed = True
          user.confirmation_code = None
          user.code_expires = None
          db.session.commit()
          
          session.pop('pending_user_id', None)
          flash('Email подтверждён! Теперь вы можете войти.', 'success')
          return redirect(url_for('login'))
      else:
          flash('Неверный код', 'error')
  
  return render_template('confirm_email.html', email=user.email)

@app.route('/resend_code')
def resend_code():
  user_id = session.get('pending_user_id')
  if not user_id:
      return redirect(url_for('register'))
  
  user = User.query.get(user_id)
  if not user or user.email_confirmed:
      return redirect(url_for('register'))
  
  # Генерируем новый код
  new_code = generate_code()
  user.confirmation_code = new_code
  user.code_expires = datetime.utcnow() + timedelta(minutes=10)
  db.session.commit()
  
  if send_confirmation_email(user.email, new_code):
      flash('Новый код отправлен', 'info')
  else:
      flash('Ошибка отправки', 'error')
  
  return redirect(url_for('confirm_email'))

@socketio.on('join')
def handle_join(data):
  if not current_user.is_authenticated:
    return
  #Поиск диалога
  dialog = Dialog.query.get(data['dialog_id'])
  #Проверка на диалог
  if dialog and (dialog.user1_id == current_user.id or dialog.user2_id == current_user.id):
    #Создаем комнату и заходим в нее
    room = f'dialog_{data["dialog_id"]}'
    join_room(room)
  else:
    disconnect()

@socketio.on('send_message')
def handle_send_message(data):    
  #Проверка на зашифрованность сообщений
  if 'encrypted' in data:
    #Сохраняем зашифрованные данные
    encrypted_data = data['encrypted']
    #Преобраховываем данные в формат JSON для сохранения в бд
    content = json.dumps(encrypted_data)
  else:
    content = data['text']
  
  #Сохраненяем сообщения в бд
  msg = Message(
    content=content,
    dialog_id=data['dialog_id'],
    sender_id=data['user_id']
  )
  db.session.add(msg)
  
  #Достаем диалог по его id
  dialog = Dialog.query.get(data['dialog_id'])
  #Изменяем время последнего сообщения 
  if dialog:
    dialog.updated_at = datetime.utcnow()
  #Сохраняем все сообщения в бд
  db.session.commit()
  
  #Отправка сообщения всем участникам диалога
  room = f'dialog_{data["dialog_id"]}'
  emit('new_message', {
      'encrypted': encrypted_data if 'encrypted' in data else None,
      'text': data['text'] if 'text' in data else None,
      'user_id': data['user_id'],
      'username': current_user.username,
      'time': datetime.now().strftime('%H:%M')
  }, room=room)

@app.route('/save_public_key', methods=['POST'])
@login_required
def save_public_key():
  #Получаем json данные из тела запроса
  data = request.get_json()
  #Достаем публичный ключ
  public_key = data.get('public_key')
  
  #Если пришел публичный ключ и у пользователя его еще нет - то сохраняем его в бд
  if public_key and not current_user.public_key:
    current_user.public_key = public_key
    db.session.commit()
    return jsonify({'status': 'ok'})
  
  return jsonify({'status': 'already_exists'})

@app.route('/get_public_key/<int:user_id>')
@login_required
def get_public_key(user_id):
  #Достаем пользователя по его id
  user = User.query.get(user_id)
  #Если пользователь существует и у него имеется публичный ключ
  if user and user.public_key:
    return jsonify({'public_key': user.public_key})
  return jsonify({'error': 'No public key'}), 404
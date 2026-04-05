from flask import render_template, flash, redirect, url_for, request, jsonify
from app import app, socketio
from app.forms import LoginForm, RegistrationForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app import db
from app.models import User, Dialog, Message
from urllib.parse import urlsplit
from datetime import datetime
from flask_socketio import emit, join_room, disconnect
import json

@app.route('/')
@app.route('/index')
@login_required
def index():
  user = {'username': 'Magomed'}
  posts = [
    {
      'author': {'username': 'Roman'},
      'body': 'Beautiful day in Portland!'
    },
    {
      'author': {'username': 'Kalivan'},
      'body': 'The Avengers movie was so cool!'
    }
  ]
  return render_template('index.html', title='Home', posts=posts)

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
      flash('Invalid username or password')
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
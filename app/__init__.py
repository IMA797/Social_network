from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO

app = Flask(__name__)
app.config.from_object(Config)

#Flask-Login подключается к приложению и начинает отследивать пользователя,
#Предоставлять переменную current_user
login = LoginManager(app)
#Если незарегистрированный пользователь зайдет на сайт, его перенаправит на login
login.login_view = 'login'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

socketio = SocketIO(app)

from app import routes, models
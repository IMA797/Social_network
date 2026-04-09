from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime 

class User(UserMixin, db.Model):
  id: so.Mapped[int] = so.mapped_column(primary_key=True)
  username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
  email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
  password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
  
  public_key: so.Mapped[Optional[str]] = so.mapped_column(sa.Text, nullable=True)
  about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200), nullable=True)

  email_confirmed = db.Column(db.Boolean, default=False)   #подтверждён ли email (по умолчанию НЕТ)
  confirmation_code = db.Column(db.String(6), nullable=True)  #6-значный код
  code_expires = db.Column(db.DateTime, nullable=True)        #когда код истекает
  
  def __repr__(self):
    return '<User {}>'.format(self.username)
  
  def set_password(self, password):
    self.password_hash = generate_password_hash(password)

  def check_password(self, password):
    return check_password_hash(self.password_hash, password)
  
  dialogs_as_user1: so.Mapped[list['Dialog']] = so.relationship(
        foreign_keys='Dialog.user1_id', 
        back_populates='user1'
  )
  dialogs_as_user2: so.Mapped[list['Dialog']] = so.relationship(
      foreign_keys='Dialog.user2_id', 
      back_populates='user2'
  )
  sent_messages: so.Mapped[list['Message']] = so.relationship(
      foreign_keys='Message.sender_id', 
      back_populates='sender'
  )
  
@login.user_loader
def load_user(id):
  return db.session.get(User, int(id))

class Dialog(db.Model):
  id: so.Mapped[int] = so.mapped_column(primary_key=True)
  user1_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), nullable=False)
  user2_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), nullable=False)
  created_at: so.Mapped[datetime] = so.mapped_column(default=datetime.utcnow)
  updated_at: so.Mapped[datetime] = so.mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
  
  # Связи
  user1: so.Mapped[User] = so.relationship(
    foreign_keys=[user1_id], 
    back_populates='dialogs_as_user1'
  )
  user2: so.Mapped[User] = so.relationship(
    foreign_keys=[user2_id], 
    back_populates='dialogs_as_user2'
  )
  messages: so.Mapped[list['Message']] = so.relationship(
    back_populates='dialog', 
    lazy='dynamic'
  )
  
  __table_args__ = (sa.UniqueConstraint('user1_id', 'user2_id', name='unique_dialog'),)

class Message(db.Model):
  id: so.Mapped[int] = so.mapped_column(primary_key=True)
  content: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
  timestamp: so.Mapped[datetime] = so.mapped_column(index=True, default=datetime.utcnow)
  dialog_id: so.Mapped[int] = so.mapped_column(
    sa.ForeignKey('dialog.id'), 
    nullable=False
  )
  sender_id: so.Mapped[int] = so.mapped_column(
    sa.ForeignKey('user.id'), 
    nullable=False
  )
  is_read: so.Mapped[bool] = so.mapped_column(default=False)
  
  # Связи
  sender: so.Mapped[User] = so.relationship(
    foreign_keys=[sender_id],
    back_populates='sent_messages'
  )
  dialog: so.Mapped[Dialog] = so.relationship(
      back_populates='messages'
  )

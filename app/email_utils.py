import smtplib
import random
from email.mime.text import MIMEText
from datetime import datetime, timedelta

SMTP_SERVER = "smtp.mail.ru"      
SMTP_PORT = 587                   
LOGIN = "magomed.ima797@mail.ru"  
PASSWORD = "cx4aFfwWZ4DCJTxX4oEG"  

def generate_code():
    return str(random.randint(100000, 999999))

def send_confirmation_email(email, code):
    
    subject = "Подтверждение регистрации"
    message_text = f"""
    Здравствуйте!
    
    Вы зарегистрировались в Social Network.
    Ваш код подтверждения: {code}
    
    Код действителен 10 минут.
    
    Если вы не регистрировались, проигнорируйте это письмо.
    """
    
    # Создаём письмо в формате MIME (текст + заголовки)
    msg = MIMEText(message_text, 'plain', 'utf-8')
    msg['From'] = LOGIN
    msg['To'] = email
    msg['Subject'] = subject
    
    try:
        # Подключаемся к SMTP-серверу
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()              # Включаем шифрование TLS
            server.login(LOGIN, PASSWORD)  # Авторизуемся на сервере
            server.sendmail(LOGIN, email, msg.as_string())  # Отправляем письмо
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False
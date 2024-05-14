import os
import psycopg2
from datetime import datetime
from psycopg2.extras import Json

# Получение секретного URL базы данных из переменной окружения
my_secret = os.environ['DATABASE_URL']

# Контекстный менеджер для работы с базой данных
class DatabaseConnection:
    def __enter__(self):
        try:
            self.connection = psycopg2.connect(my_secret, sslmode='require')
            return self.connection
        except psycopg2.Error as error:
            print("Ошибка при подключении к PostgreSQL:", error)
            return None

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection is not None:
            self.connection.close()

# Функция для проверки существования и создания таблицы пользователей
def check_and_create_database():
    try:
        with DatabaseConnection() as connection:
            if connection is not None:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_users')")
                    row = cursor.fetchone()
                    if row is not None:
                        table_exists = row[0]

                        if not table_exists:
                            create_table_query = '''
                            CREATE TABLE IF NOT EXISTS chat_users (
                            telegram_id BIGINT PRIMARY KEY NOT NULL,
                            user_name VARCHAR(255),
                            first_name VARCHAR(255),
                            last_name VARCHAR(255),
                            user_type VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );
                            '''
                            cursor.execute(create_table_query)
                            connection.commit()
                            print("Таблица пользователей создана успешно!")
                        else:
                            print("Таблица пользователей уже существует.")
            else:
                print("Ошибка: соединение с базой данных не установлено")
    except psycopg2.Error as error:
        print("Ошибка при подключении к базе данных:", error)

# Вызов функции для проверки и создания базы данных
check_and_create_database()

# Функция для проверки существования и создания таблиц
def check_and_create_usage_table():
  try:
      with DatabaseConnection() as connection:
          if connection is not None:
              with connection.cursor() as cursor:
                  # Проверяем существование таблицы current_cost
                  cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'current_cost')")
                  row = cursor.fetchone()
                  if row is not None:
                      table_exists = row[0]
                      if not table_exists:
                          # Создаем таблицу current_cost
                          create_current_cost_table_query = '''
                          CREATE TABLE IF NOT EXISTS current_cost (
                              user_id BIGINT PRIMARY KEY,
                              day_cost NUMERIC(10, 6),
                              month_cost NUMERIC(10, 6),
                              all_time_cost NUMERIC(10, 6),
                              last_update DATE
                          );
                          '''
                          cursor.execute(create_current_cost_table_query)

                          # Создаем таблицу chat_tokens_history
                          create_chat_tokens_table_query = '''
                          CREATE TABLE IF NOT EXISTS chat_tokens_history (
                              user_id BIGINT,
                              date DATE,
                              tokens_used INTEGER,
                              PRIMARY KEY (user_id, date),
                              FOREIGN KEY (user_id) REFERENCES current_cost(user_id)
                          );
                          '''
                          cursor.execute(create_chat_tokens_table_query)
  
                          # Создаем таблицу transcription_seconds_history
                          create_transcription_seconds_table_query = '''
                          CREATE TABLE IF NOT EXISTS transcription_seconds_history (
                              user_id BIGINT,
                              date DATE,
                              seconds_used NUMERIC(10, 6),
                              PRIMARY KEY (user_id, date),
                              FOREIGN KEY (user_id) REFERENCES current_cost(user_id)
                          );
                          '''
                          cursor.execute(create_transcription_seconds_table_query)
  
                          # Создаем таблицу number_images_history
                          create_number_images_table_query = '''
                          CREATE TABLE IF NOT EXISTS number_images_history (
                              user_id BIGINT,
                              date DATE,
                              image_data JSONB,
                              PRIMARY KEY (user_id, date),
                              FOREIGN KEY (user_id) REFERENCES current_cost(user_id)
                          );
                          '''
                          cursor.execute(create_number_images_table_query)

                          connection.commit()
                          print("Таблицы успешно созданы!")
                      else:
                          print("Таблицы уже существуют.")
          else:
              print("Ошибка: соединение с базой данных не установлено")
  except psycopg2.Error as error:
      print("Ошибка при подключении к базе данных:", error)

# Вызов функции для создания таблицы
check_and_create_usage_table()

# Функции добавления пользователя
def add_user(telegram_id: int, user_name: str, first_name: str, last_name: str, user_type: str = "guest"):
    try:
        # Подключение к базе данных PostgreSQL с помощью контекстного менеджера
        with DatabaseConnection() as connection:
            if connection is not None:
                with connection.cursor() as cursor:
                    # Проверка, есть ли уже пользователь с таким telegram_id в базе данных
                    cursor.execute("SELECT COUNT(*) FROM chat_users WHERE telegram_id = %s", (telegram_id,))
                    row = cursor.fetchone()
                    if row is not None:
                        count = row[0]
                        if count == 0:
                            # Запрос для вставки новой записи о пользователе в таблицу chat_users
                            insert_query = '''
                            INSERT INTO chat_users (telegram_id, user_name, first_name, last_name, user_type, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            '''
                            # Получение текущей даты и времени
                            created_at = datetime.now()

                            # Выполнение запроса с передачей параметров
                            cursor.execute(insert_query, (telegram_id, user_name, first_name, last_name, user_type, created_at))

                            # Фиксация изменений в базе данных
                            connection.commit()

                            print("Пользователь успешно добавлен в базу данных!")
                        else:
                            print("Пользователь уже существует в базе данных")
                    else:
                        print("Результат не найден в базе данных")
            else:
                print("Ошибка: соединение с базой данных не установлено")
    except psycopg2.Error as error:
        print("Ошибка при добавлении пользователя в базу данных:", error)

def is_admin(user_id: int) -> tuple:
    try:
        admins = []
        # Подключение к базе данных с использованием вашего контекстного менеджера
        with DatabaseConnection() as connection:
            if connection is not None:
                with connection.cursor() as cursor:
                    # Ищем пользователя в базе данных по user_id и проверяем его user_type
                    cursor.execute("SELECT user_type, telegram_id FROM chat_users WHERE telegram_id = %s", (user_id,))
                    rows = cursor.fetchall()

                    for row in rows:
                        user_type, telegram_id = row
                        if user_type == 'admin':
                            admins.append(telegram_id)

                    if len(admins) > 0:
                        return True, admins
                    else:
                        return False, []
            else:
                print("Ошибка: соединение с базой данных не установлено")
    except psycopg2.Error as error:
        # Обработка ошибок при подключении к базе данных
        print("Ошибка при подключении к базе данных:", error)

    return False, []

# Функция для сохранения данных использования в базу данных
def save_to_database(user_id, usage_data):
    try:
        with DatabaseConnection() as connection:
            if connection is not None:
                with connection.cursor() as cursor:
                    # Сохраняем данные в таблицу current_cost
                    cursor.execute("""
                        INSERT INTO current_cost (user_id, day_cost, month_cost, all_time_cost, last_update)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                        day_cost = EXCLUDED.day_cost,
                        month_cost = EXCLUDED.month_cost,
                        all_time_cost = EXCLUDED.all_time_cost,
                        last_update = EXCLUDED.last_update
                    """, (
                        user_id,
                        usage_data["current_cost"]["day"],
                        usage_data["current_cost"]["month"],
                        usage_data["current_cost"]["all_time"],
                        usage_data["current_cost"]["last_update"]
                    ))

                    # Сохраняем данные из usage_history в соответствующие таблицы

                    # Сохраняем данные из usage_history["chat_tokens"] в таблицу chat_tokens_history
                    for date, tokens_used in usage_data["usage_history"]["chat_tokens"].items():
                        try:
                            cursor.execute("""
                                INSERT INTO chat_tokens_history (user_id, date, tokens_used)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (user_id, date) DO UPDATE SET
                                tokens_used = EXCLUDED.tokens_used
                            """, (
                                user_id,
                                date,
                                tokens_used
                            ))
                            # print("Данные успешно сохранены в таблице chat_tokens_history!")
                        except psycopg2.Error as chat_tokens_error:
                            print("Ошибка при сохранении в таблице chat_tokens_history:", chat_tokens_error)

                    # Сохраняем данные из usage_history["transcription_seconds"] в таблицу transcription_seconds_history
                    for date, seconds_used in usage_data["usage_history"]["transcription_seconds"].items():
                        try:
                            cursor.execute("""
                                INSERT INTO transcription_seconds_history (user_id, date, seconds_used)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (user_id, date) DO UPDATE SET
                                seconds_used = EXCLUDED.seconds_used
                            """, (
                                user_id,
                                date,
                                seconds_used
                            ))
                            # print("Данные успешно сохранены в таблице transcription_seconds_history!")
                        except psycopg2.Error as transcription_seconds_error:
                            print("Ошибка при сохранении в таблице transcription_seconds_history:", transcription_seconds_error)

                    # Сохраняем данные из usage_history["number_images"] в таблицу number_images_history
                    for date, image_data in usage_data["usage_history"]["number_images"].items():
                        try:
                            cursor.execute("""
                                INSERT INTO number_images_history (user_id, date, image_data)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (user_id, date) DO UPDATE SET
                                image_data = EXCLUDED.image_data
                            """, (
                                user_id,
                                date,
                                Json(image_data)
                            ))
                            # print("Данные успешно сохранены в таблице number_images_history!")
                        except psycopg2.Error as number_images_error:
                            print("Ошибка при сохранении в таблице number_images_history:", number_images_error)

                    connection.commit()
            else:
                print("Ошибка: соединение с базой данных не установлено")
    except psycopg2.Error as error:
        print("Общая ошибка при сохранении в базе данных:", error)

# Функция для получения данных использования из бд
def get_user_usage(user_id):
    try:
        with DatabaseConnection() as connection:
            if connection is not None:
                with connection.cursor() as cursor:
                    # Получаем данные пользователя из таблицы current_cost
                    cursor.execute("SELECT * FROM current_cost WHERE user_id = %s", (user_id,))
                    current_cost = cursor.fetchone()

                    # Получаем данные из таблицы chat_tokens_history
                    cursor.execute("SELECT * FROM chat_tokens_history WHERE user_id = %s", (user_id,))
                    chat_tokens_history = cursor.fetchall()

                    # Получаем данные из таблицы transcription_seconds_history
                    cursor.execute("SELECT * FROM transcription_seconds_history WHERE user_id = %s", (user_id,))
                    transcription_seconds_history = cursor.fetchall()

                    # Получаем данные из таблицы number_images_history
                    cursor.execute("SELECT * FROM number_images_history WHERE user_id = %s", (user_id,))
                    number_images_history = cursor.fetchall()

                    return current_cost, chat_tokens_history, transcription_seconds_history, number_images_history
            else:
                print("Ошибка: соединение с базой данных не установлено")
                return None
    except psycopg2.Error as error:
        print("Ошибка при подключении к базе данных:", error)
        return None  
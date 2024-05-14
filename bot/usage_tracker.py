import os.path
import pathlib
import json
from datetime import date
from bd import save_to_database, get_user_usage

def year_month(date_str):
    # извлекаем строку года-месяца из даты, например: '2023-03'
    return str(date_str)[:7]

def save_usage_to_cash(user_file, usage):
  """Сохраняет данные использования в файл пользователя."""
  with open(user_file, "w") as outfile:
      json.dump(usage, outfile)

class UsageTracker:
    """
    Класс UsageTracker
    Позволяет отслеживать ежедневное/месячное использование для каждого пользователя.
    Данные пользователя хранятся в формате JSON в директории /usage_logs.
    JSON example:
    {
        "user_name": "@user_name",
        "current_cost": {
            "day": 0.45,
            "month": 3.23,
            "all_time": 3.23,
            "last_update": "2023-03-14"},
        "usage_history": {
            "chat_tokens": {
                "2023-03-13": 520,
                "2023-03-14": 1532
            },
            "transcription_seconds": {
                "2023-03-13": 125,
                "2023-03-14": 64
            },
            "number_images": {
                "2023-03-12": [0, 2, 3],
                "2023-03-13": [1, 2, 3],
                "2023-03-14": [0, 1, 2]
            }
        }
    }
    """

    def __init__(self, user_id, user_name, logs_dir="usage_logs"):
      """
      Инициализирует объект UsageTracker для пользователя с текущей датой.
      Загружает данные использования из файла журнала использования.
      :param user_id: ID пользователя в Telegram
      :param user_name: Имя пользователя в Telegram
      :param logs_dir: Путь к директории с журналами использования, по умолчанию "usage_logs"
      """
      self.user_id = user_id
      self.logs_dir = logs_dir
      # Путь к файлу использования для данного пользователя
      self.user_file = f"{logs_dir}/{user_id}.json"

      if not self.load_usage_from_database(user_name):
          self.load_usage_from_cache(user_name)

    def load_usage_from_database(self, user_name):
        """Загружает данные использования из базы данных и сохраняет их в атрибут usage."""
        # Получаем данные использования из базы данных
        user_data = get_user_usage(self.user_id)
        if user_data:
            # Преобразуем данные в нужный формат
            current_cost, chat_tokens_history, transcription_seconds_history, number_images_history = user_data
            if current_cost:
                formatted_data = {
                    "user_name": user_name,  # Использует переданный user_name
                    "current_cost": {
                        "day": float(current_cost[1]),
                        "month": float(current_cost[2]),
                        "all_time": float(current_cost[3]),
                        "last_update": str(date.today())
                    },
                    "usage_history": {
                        "chat_tokens": {str(row[1]): row[2] for row in chat_tokens_history},
                        "transcription_seconds": {str(row[1]): float(row[2]) for row in transcription_seconds_history},
                        "number_images": {str(row[1]): [int(row[2][0]), int(row[2][1]), int(row[2][2])] for row in number_images_history},
                        "tts_characters": {},
                        "vision_tokens": {}
                    }
                }
                self.usage = formatted_data
                return True
        return False
  
    def load_usage_from_cache(self, user_name):
      """Загружает данные использования из файла журнала использования."""
      if os.path.isfile(self.user_file):
          with open(self.user_file, "r") as file:
              self.usage = json.load(file)
          if 'vision_tokens' not in self.usage['usage_history']:
              self.usage['usage_history']['vision_tokens'] = {}
          if 'tts_characters' not in self.usage['usage_history']:
              self.usage['usage_history']['tts_characters'] = {}
      else:
          # Убедимся, что директория существует
          pathlib.Path(self.logs_dir).mkdir(exist_ok=True)
          # Создаем новый словарь для данного пользователя
          self.usage = {
              "user_name": user_name,
              "current_cost": {"day": 0.0, "month": 0.0, "all_time": 0.0, "last_update": str(date.today())},
              "usage_history": {"chat_tokens": {}, "transcription_seconds": {}, "number_images": {}, "tts_characters": {}, "vision_tokens": {}}
          }
          # Сохраняем новые данные использования в файл пользователя
          save_usage_to_cash(self.user_file, self.usage)
          # Сохраняем данные в базу данных
          save_to_database(self.user_id, self.usage)
  
    # Функции использования токенов:
  
    def add_chat_tokens(self, tokens, tokens_price=0.002):
      """Добавляет использованные токены из запроса в историю использования пользователя и обновляет текущую стоимость."""
      today = date.today()
      token_cost = round(float(tokens) * tokens_price / 1000, 6)
      self.add_current_costs(token_cost)
  
      # Обновляем историю использования
      if str(today) in self.usage["usage_history"]["chat_tokens"]:
          # Добавляем использование токенов к существующей дате
          self.usage["usage_history"]["chat_tokens"][str(today)] += tokens
      else:
          # Создаем новую запись для текущей даты
          self.usage["usage_history"]["chat_tokens"][str(today)] = tokens
  
      # Сохраняем обновленное использование токенов в файл пользователя
      save_usage_to_cash(self.user_file, self.usage)
      # Сохраняем данные в базу данных
      save_to_database(self.user_id, self.usage)

    def get_current_token_usage(self):
        """Получить количество токенов, использованных за сегодня и за месяц
  
        :return: общее количество токенов, использованных за день и за месяц
        """
        today = date.today()
        if str(today) in self.usage["usage_history"]["chat_tokens"]:
            usage_day = self.usage["usage_history"]["chat_tokens"][str(today)]
        else:
            usage_day = 0
        month = str(today)[:7]  # year-month as string
        usage_month = 0
        for today, tokens in self.usage["usage_history"]["chat_tokens"].items():
            if today.startswith(month):
                usage_month += tokens
        return usage_day, usage_month

    # функции использования изображений:

    def add_image_request(self, image_size, image_prices="0.016,0.018,0.02"):
        """Добавляет запрос изображения в историю использования и обновляет текущие расходы.
  
        :param image_size: размер запрашиваемого изображения
        :param image_prices: цены на изображения размером ["256x256", "512x512", "1024x1024"],
                             по умолчанию [0.016, 0.018, 0.02]
        """
        sizes = ["256x256", "512x512", "1024x1024"]
        requested_size = sizes.index(image_size)
        image_cost = image_prices[requested_size]
        today = date.today()
        self.add_current_costs(image_cost)

        # update usage_history
        if str(today) in self.usage["usage_history"]["number_images"]:
            # add token usage to existing date
            self.usage["usage_history"]["number_images"][str(today)][requested_size] += 1
        else:
            # create new entry for current date
            self.usage["usage_history"]["number_images"][str(today)] = [0, 0, 0]
            self.usage["usage_history"]["number_images"][str(today)][requested_size] += 1

        # Сохраняем новые данные использования в файл пользователя
        save_usage_to_cash(self.user_file, self.usage)
        # Сохраняем данные в базу данных
        save_to_database(self.user_id, self.usage)

    def get_current_image_count(self):
        """Получите количество изображений, запрошенных за сегодня и за месяц.
  
        :возврат: общее количество изображений, запрошенных за день и за месяц
        """
        today = date.today()
        if str(today) in self.usage["usage_history"]["number_images"]:
            usage_day = sum(self.usage["usage_history"]["number_images"][str(today)])
        else:
            usage_day = 0
        month = str(today)[:7]  # год-месяц как строка
        usage_month = 0
        for today, images in self.usage["usage_history"]["number_images"].items():
            if today.startswith(month):
                usage_month += sum(images)
        return usage_day, usage_month


    # функции использования зрения
    def add_vision_tokens(self, tokens, vision_token_price=0.01):
        """
         Добавляет запрошенные токены зрения в историю использования пользователя и обновляет текущую стоимость.
        :param tokens: общее количество токенов, использованных в последнем запросе
        :param vision_token_price: цена за транскрипцию 1K токенов, по умолчанию 0.01
        """
        today = date.today()
        token_price = round(tokens * vision_token_price / 1000, 2)
        self.add_current_costs(token_price)

        # update usage_history
        if str(today) in self.usage["usage_history"]["vision_tokens"]:
            # add requested seconds to existing date
            self.usage["usage_history"]["vision_tokens"][str(today)] += tokens
        else:
            # create new entry for current date
            self.usage["usage_history"]["vision_tokens"][str(today)] = tokens

        # Сохраняем новые данные использования в файл пользователя
        save_usage_to_cash(self.user_file, self.usage)
        # Сохраняем данные в базу данных
        save_to_database(self.user_id, self.usage)
      
    def get_current_vision_tokens(self):
        """Get vision tokens for today and this month.

        :return: total amount of vision tokens per day and per month
        """
        today = date.today()
        if str(today) in self.usage["usage_history"]["vision_tokens"]:
            tokens_day = self.usage["usage_history"]["vision_tokens"][str(today)]
        else:
            tokens_day = 0
        month = str(today)[:7]  # year-month as string
        tokens_month = 0
        for today, tokens in self.usage["usage_history"]["vision_tokens"].items():
            if today.startswith(month):
                tokens_month += tokens
        return tokens_day, tokens_month

    # tts usage functions:

    def add_tts_request(self, text_length, tts_model, tts_prices):
        tts_models = ['tts-1', 'tts-1-hd']
        price = tts_prices[tts_models.index(tts_model)]
        today = date.today()
        tts_price = round(text_length * price / 1000, 2)
        self.add_current_costs(tts_price)

        if 'tts_characters' not in self.usage['usage_history']:
            self.usage['usage_history']['tts_characters'] = {}
        
        if tts_model not in self.usage['usage_history']['tts_characters']:
            self.usage['usage_history']['tts_characters'][tts_model] = {}

        # update usage_history
        if str(today) in self.usage["usage_history"]["tts_characters"][tts_model]:
            # add requested text length to existing date
            self.usage["usage_history"]["tts_characters"][tts_model][str(today)] += text_length
        else:
            # create new entry for current date
            self.usage["usage_history"]["tts_characters"][tts_model][str(today)] = text_length

        # Сохраняем новые данные использования в файл пользователя
        save_usage_to_cash(self.user_file, self.usage)
        # Сохраняем данные в базу данных
        save_to_database(self.user_id, self.usage)

    def get_current_tts_usage(self):
        """Get length of speech generated for today and this month.

        :return: total amount of characters converted to speech per day and per month
        """

        tts_models = ['tts-1', 'tts-1-hd']
        today = date.today()
        characters_day = 0
        for tts_model in tts_models:
            if tts_model in self.usage["usage_history"]["tts_characters"] and \
                str(today) in self.usage["usage_history"]["tts_characters"][tts_model]:
                characters_day += self.usage["usage_history"]["tts_characters"][tts_model][str(today)]

        month = str(today)[:7]  # year-month as string
        characters_month = 0
        for tts_model in tts_models:
            if tts_model in self.usage["usage_history"]["tts_characters"]: 
                for today, characters in self.usage["usage_history"]["tts_characters"][tts_model].items():
                    if today.startswith(month):
                        characters_month += characters
        return int(characters_day), int(characters_month)


    # transcription usage functions:

    def add_transcription_seconds(self, seconds, minute_price=0.006):
        """Adds requested transcription seconds to a users usage history and updates current cost.
        :param seconds: total seconds used in last request
        :param minute_price: price per minute transcription, defaults to 0.006
        """
        today = date.today()
        transcription_price = round(seconds * minute_price / 60, 2)
        self.add_current_costs(transcription_price)

        # update usage_history
        if str(today) in self.usage["usage_history"]["transcription_seconds"]:
            # add requested seconds to existing date
            self.usage["usage_history"]["transcription_seconds"][str(today)] += seconds
        else:
            # create new entry for current date
            self.usage["usage_history"]["transcription_seconds"][str(today)] = seconds

        # Сохраняем новые данные использования в файл пользователя
        save_usage_to_cash(self.user_file, self.usage)
        # Сохраняем данные в базу данных
        save_to_database(self.user_id, self.usage)

    def add_current_costs(self, request_cost):
      """
      Добавляет текущие затраты к общим, дневным и месячным затратам и обновляет дату последнего обновления.
      """
      today = date.today()  # Получаем текущую дату
      last_update = date.fromisoformat(self.usage["current_cost"]["last_update"])  # Получаем последнюю дату обновления
    
      # Добавляем текущие затраты к общим затратам, инициализируем, если ключ не существует
      self.usage["current_cost"]["all_time"] = \
          self.usage["current_cost"].get("all_time", self.initialize_all_time_cost()) + request_cost
    
      # Добавляем текущие затраты и обновляем день или месяц
      if today == last_update:
          # Если сегодняшний день совпадает с последним обновлением, добавляем затраты к текущему дню и месяцу
          self.usage["current_cost"]["day"] += request_cost
          self.usage["current_cost"]["month"] += request_cost
      else:
          # Если это новый день или месяц, обновляем соответственно
          if today.month == last_update.month:
              # Если это тот же месяц, просто обновляем месячные затраты
              self.usage["current_cost"]["month"] += request_cost
          else:
              # Если это новый месяц, сбрасываем месячные затраты
              self.usage["current_cost"]["month"] = request_cost
          # Обновляем дневные затраты и дату последнего обновления
          self.usage["current_cost"]["day"] = request_cost
          self.usage["current_cost"]["last_update"] = str(today)

    def get_current_transcription_duration(self):
        """Get minutes and seconds of audio transcribed for today and this month.

        :return: total amount of time transcribed per day and per month (4 values)
        """
        today = date.today()
        if str(today) in self.usage["usage_history"]["transcription_seconds"]:
            seconds_day = self.usage["usage_history"]["transcription_seconds"][str(today)]
        else:
            seconds_day = 0
        month = str(today)[:7]  # year-month as string
        seconds_month = 0
        for today, seconds in self.usage["usage_history"]["transcription_seconds"].items():
            if today.startswith(month):
                seconds_month += seconds
        minutes_day, seconds_day = divmod(seconds_day, 60)
        minutes_month, seconds_month = divmod(seconds_month, 60)
        return int(minutes_day), round(seconds_day, 2), int(minutes_month), round(seconds_month, 2)

    # general functions
    def get_current_cost(self):
        """Get total USD amount of all requests of the current day and month

        :return: cost of current day and month
        """
        today = date.today()
        last_update = date.fromisoformat(self.usage["current_cost"]["last_update"])
        if today == last_update:
            cost_day = self.usage["current_cost"]["day"]
            cost_month = self.usage["current_cost"]["month"]
        else:
            cost_day = 0.0
            if today.month == last_update.month:
                cost_month = self.usage["current_cost"]["month"]
            else:
                cost_month = 0.0
        # add to all_time cost, initialize with calculation of total_cost if key doesn't exist
        cost_all_time = self.usage["current_cost"].get("all_time", self.initialize_all_time_cost())
        return {"cost_today": cost_day, "cost_month": cost_month, "cost_all_time": cost_all_time}

    def initialize_all_time_cost(self, tokens_price=0.002, image_prices="0.016,0.018,0.02", minute_price=0.006, vision_token_price=0.01, tts_prices='0.015,0.030'):
        """Get total USD amount of all requests in history
        
        :param tokens_price: price per 1000 tokens, defaults to 0.002
        :param image_prices: prices for images of sizes ["256x256", "512x512", "1024x1024"],
            defaults to [0.016, 0.018, 0.02]
        :param minute_price: price per minute transcription, defaults to 0.006
        :param vision_token_price: price per 1K vision token interpretation, defaults to 0.01
        :param tts_prices: price per 1K characters tts per model ['tts-1', 'tts-1-hd'], defaults to [0.015, 0.030]
        :return: total cost of all requests
        """
        total_tokens = sum(self.usage['usage_history']['chat_tokens'].values())
        token_cost = round(total_tokens * tokens_price / 1000, 6)

        total_images = [sum(values) for values in zip(*self.usage['usage_history']['number_images'].values())]
        image_prices_list = [float(x) for x in image_prices.split(',')]
        image_cost = sum([count * price for count, price in zip(total_images, image_prices_list)])

        total_transcription_seconds = sum(self.usage['usage_history']['transcription_seconds'].values())
        transcription_cost = round(total_transcription_seconds * minute_price / 60, 2)

        total_vision_tokens = sum(self.usage['usage_history']['vision_tokens'].values())
        vision_cost = round(total_vision_tokens * vision_token_price / 1000, 2)

        total_characters = [sum(tts_model.values()) for tts_model in self.usage['usage_history']['tts_characters'].values()]
        tts_prices_list = [float(x) for x in tts_prices.split(',')]
        tts_cost = round(sum([count * price / 1000 for count, price in zip(total_characters, tts_prices_list)]), 2)

        all_time_cost = token_cost + transcription_cost + image_cost + vision_cost + tts_cost
        return all_time_cost

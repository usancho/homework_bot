import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка токенов."""
    token_dict = {
        'practicum_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
    }
    for key, token in token_dict.items():
        if token is None:
            logging.critical(f'{key} не найден!')
            return False
    logging.info('Токены найдены, работаем...')
    return True


def send_message(bot, message):
    """Отправка сообщения пользователю."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error('Сообщение не было отправлено!')
    else:
        logging.debug('Сообщение отправлено...')


def get_api_answer(timestamp):
    """Запрос ответа сервера."""
    payload = {'from_date': timestamp}
    try:
        homework_info = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if homework_info.status_code != HTTPStatus.OK:
            homework_info.raise_for_status()
        logging.info('Запрос к API выполнен...')
        return homework_info.json()
    except requests.exceptions.RequestException as req_exc:
        message = f'Запрос к API не выполнен! {homework_info.status_code}'
        logging.error(message)
        raise req_exc(message)


def check_response(response):
    """Проверка ответа API на соответствие."""
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                return response.get('homeworks')
            raise TypeError('По запросу получен не список!')
        raise KeyError('Ключ homeworks не найден!')
    raise TypeError('Ответ API не является словарем!')


def parse_status(homework):
    """Парсинг статуса домашки."""
    if isinstance(homework, dict):
        if 'status' in homework:
            if 'homework_name' in homework:
                if isinstance(homework.get('status'), str):
                    homework_name = homework.get('homework_name')
                    homework_status = homework.get('status')
                    if homework_status in HOMEWORK_VERDICTS:
                        verdict = HOMEWORK_VERDICTS.get(homework_status)
                        return ('Изменился статус проверки работы '
                                f'"{homework_name}". {verdict}')
                    else:
                        raise Exception('Статус работы неизвестен!')
                raise TypeError('Объект status не является str!')
            raise KeyError('Ответом не получен ключ homework_name!')
        raise KeyError('Ответом не получен ключ status!')
    raise KeyError('Ответ API не является словарем!')


def main():
    """Основная логика работы бота."""
    logging.info('Бот начал работать.')
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        # timestamp = 0
        while True:
            try:
                response_result = get_api_answer(timestamp)
                homeworks = check_response(response_result)
                logging.info('Список домашних работ получен...')
                if len(homeworks) > 0:
                    send_message(bot, parse_status(homeworks[0]))
                    timestamp = response_result['current_date']
                else:
                    logging.info('Новые задания не обнаружены!')
                time.sleep(RETRY_PERIOD)

            except Exception as error:
                message = f'При работе программы обнаружена ошибка: {error}!'
                send_message(bot, message)
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

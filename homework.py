import logging
import os
import time
import sys
from http import HTTPStatus

import requests
from exceptions import EmptyAPIResponseError
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
)
logger = logging.getLogger(__name__)

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
            logger.critical(f'{key} не найден!')
            return False
    logger.info('Токены найдены, работаем...')
    return True


def send_message(bot, message):
    """Отправка сообщения пользователю."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logger.error('Сообщение не было отправлено!')
    else:
        logger.debug('Сообщение отправлено...')


def get_api_answer(timestamp):
    """Запрос ответа сервера."""
    payload = {'from_date': timestamp}
    try:
        homework_info = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if homework_info.status_code != HTTPStatus.OK:
            raise KeyError(
                f'Ошибка! Запрос к {ENDPOINT} вернул {homework_info.headers}!'
            )
        logger.info('Запрос к API выполнен...')
        return homework_info.json()
    except requests.exceptions.RequestException:
        message = f'Запрос к API не выполнен! {homework_info.status_code}'
        logger.error(message)
        raise EmptyAPIResponseError('{message}')


def check_response(response):
    """Проверка ответа API на соответствие."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем!')
    valid_response = response
    homeworks = valid_response.get('homeworks')
    if not homeworks:
        raise KeyError('Ключ homeworks не найден!')
    if 'current_date' not in valid_response:
        raise KeyError('Ключ current_date не найден!')
    if not isinstance(homeworks, list):
        raise TypeError('По запросу получен не список!')
    return homeworks


def parse_status(homework):
    """Парсинг статуса домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not isinstance(homework, dict):
        raise KeyError('Ответ API не является словарем!')
    if 'status' not in homework:
        raise KeyError('Ответом не получен ключ status!')
    if 'homework_name' not in homework:
        raise KeyError('Ответом не получен ключ homework_name!')
    if not isinstance(homework.get('status'), str):
        raise TypeError('Объект status не является str!')
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        return ('Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    raise Exception('Статус работы неизвестен!')


def main():
    """Основная логика работы бота."""
    logger.info('Бот начал работать.')
    if not check_tokens():
        message = 'Программа остановлена... Токены не прошли проверку!'
        logger.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_report = {}
    current_report = {'homework_name': '', 'output': ''}
    while True:
        try:
            response_result = get_api_answer(timestamp)
            homeworks = check_response(response_result)[0]
            current_report.update(
                homework_name=homeworks.get('homework_name'),
                output=parse_status(homeworks)
            )
            logger.info('Список домашних работ получен...')
            if homeworks and prev_report != current_report:
                send_message(bot, parse_status(homeworks))
                prev_report = current_report.copy()
                timestamp = response_result['current_date']
            else:
                logger.debug('Новые задания не обнаружены!')
        except Exception as error:
            message = f'При работе программы обнаружена ошибка: {error}!'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

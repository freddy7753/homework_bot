import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NoneInVariables

load_dotenv()

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
    """Проверяем доступность переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    token_available = True
    for token in tokens:
        if token is None:
            logger.critical(f'token is unavailable {token}')
            token_available = False
    return token_available


def send_message(bot, message):
    """Отправляем сообщение в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logger.error('message not send error')
    else:
        logger.debug('message send')


def get_api_answer(timestamp: int):
    """Получаем ответ response из Практикума."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except Exception:
        raise ConnectionError(
            f'endpoint is unreachable. status: {response.status_code}'
        )
    else:
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            raise AssertionError(
                f'endpoint is unreachable. status: {response.status_code}'
            )


def check_response(response):
    """Проверяем ответ сервера на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'response is not type dict{type(response)}')

    if 'homeworks' not in response:
        raise KeyError('key homeworks not found')

    if not isinstance(response['homeworks'], list):
        raise TypeError('key homeworks is not list')

    homeworks = response['homeworks']
    if not homeworks:
        raise IndexError('key homeworks empty list')

    return homeworks


def parse_status(homework):
    """Извлекаем статус определенной домашней работы."""
    if not homework.get('homework_name'):
        # Почему-то только с get pytest пропускает
        raise KeyError('key homework_name not found')

    if not homework['status']:
        raise KeyError('key status not found')

    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('status not in HOMEWORK_VERDICTS')

    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('tokens unavailable')
        raise NoneInVariables('tokens unavailable')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    first_status = ''
    repeated_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks[0])
            if message != first_status:
                send_message(bot, message)
                first_status = message
            # logging.debug('new status missing')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error('program run error')
            if repeated_error != message:
                send_message(bot, message)
                repeated_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s'
        ),
        handlers=[
            logging.StreamHandler(stream=sys.stdout),
            logging.handlers.RotatingFileHandler(
                'my_logger.log', maxBytes=10000000, backupCount=3
                # тут ошибка какая-то, не смог разобраться
            )
        ]
    )
    main()

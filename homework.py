import logging
import os
import sys
import time
from http import HTTPStatus

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
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    token_available = True
    for value, token in tokens.items():
        if token is None:
            logger.critical(f'token is unavailable {value}')
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
        if response.status_code != HTTPStatus.OK:
            raise AssertionError(
                f'endpoint is unreachable. status: {response.status_code}'
            )
        return response.json()


def check_response(response):
    """Проверяем ответ сервера на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'expected type dict, got type: {type(response)}')

    if 'homeworks' not in response:
        raise KeyError('key homeworks not found')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'key homeworks is type: {type(homeworks)}, expected type: list'
        )

    if not homeworks:
        raise IndexError('key homeworks empty list')

    return homeworks


def parse_status(homework):
    """Извлекаем статус определенной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('key homework_name not found')

    if 'status' not in homework:
        raise KeyError('key status not found')

    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'{status} not in HOMEWORK_VERDICTS.'
                       f' Available keys is {HOMEWORK_VERDICTS.keys()}')

    verdict = HOMEWORK_VERDICTS[status]
    return (f'Изменился статус проверки работы '  # Строка была в заготовке
            f'"{homework_name}". {verdict}')


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
            logging.FileHandler(
                f'{os.path.dirname(os.path.abspath(__file__))}/output.log'
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()

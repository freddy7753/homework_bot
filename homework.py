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
    return all(
        (env is not None for env in (
            PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    )


def send_message(bot, message):
    """Отправляем сообщение в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('message send')
    except Exception:
        logger.error('message not send error')


def get_api_answer(timestamp: int):
    """Получаем ответ response из Практикума."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            logger.error('error response API')
            raise AssertionError(
                f'endpoint is unreachable. status: {response.status_code}'
            )
    except Exception as error_response_api:
        logger.error(f'error {error_response_api}')
        raise AssertionError(
            f'endpoint is unreachable. status: {response.status_code}'
        )


def check_response(response):
    """Проверяем ответ сервера на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('response is not dict')
        raise TypeError('response is not type dict')

    if 'homeworks' not in response:
        logger.error('key homeworks not found in response')
        raise KeyError('key homeworks not found')

    if not isinstance(response.get('homeworks'), list):
        logger.error('key homeworks is not list')
        raise TypeError('key homeworks is not list')

    if not response.get('homeworks'):
        logger.error('key homeworks is empty')
        raise IndexError('key homeworks empty list')

    return response.get('homeworks')


def parse_status(homework):
    """Извлекаем статус определенной домашней работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError():
        logger.error('key homework_name not found')
        raise KeyError('key homework_name not found')

    try:
        status = homework['status']
    except KeyError():
        logger.error('key status not found')
        raise KeyError('key status not found')

    if status not in HOMEWORK_VERDICTS:
        logger.error('status not in HOMEWORK_VERDICTS')
        raise KeyError('status not in HOMEWORK_VERDICTS')
    else:
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
    timestamp = int(time.time())
    first_status = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework[0])
            if message != first_status:
                send_message(bot, message)
                first_status = message
            logger.debug('new status missing')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error('program run error')
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s %(name)s')
    )
    logger.addHandler(handler)
    main()

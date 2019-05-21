# -*- coding: utf-8 -*-

import logging
import sqlite3

import yaml

import telegram
from response import *
from utils import *

logger = logging.getLogger('secretsanta')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('secretsanta.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class SecretSanta:
    help = f'''Привет! Это бот *Secret Santa*!

Список команд:

1. /cng [ID] - Создает новыю группу. Если не указан ID, то ID генерируется рандомным образом.
2. /dlt ID - Удалить группу ID 
3. /ctg ID - Присоединиться к группе ID
4. /wtw ID - Распределить кто кому дарит подарки из группы ID
5. /info [ID] - Получить информацию о ваших группах. Если указан ID, то ID выводится подробная информация о \
группе.
6. /help - Помощь
'''

    def __init__(self, token, database_path):
        self.api = telegram.TelegramAPI(token)
        self.conn = sqlite3.connect(database_path)
        self.cursor = self.conn.cursor()

        # self.api.send

        logger.info('SercetSanta created')

    def __del__(self):
        self.conn.close()

    def create_new_group(self, admin_id, group_id):
        if group_id is None:
            while True:
                group_id = rand_id()
                self.cursor.execute(f'SELECT * FROM groups WHERE uuid = "{group_id}"')
                if not self.cursor.fetchall():
                    break
        try:
            self.cursor.execute(f'INSERT INTO groups VALUES ("{group_id}", {admin_id})')
            self.cursor.execute(f'INSERT INTO groups_users VALUES ("{group_id}", {admin_id})')
            self.conn.commit()
            return Response(group_id, ResponseCode.OK, f'group "{group_id}" created')
        except sqlite3.IntegrityError as error:
            logger.error(error)
            return Response(None, ResponseCode.INVALID_DATA, f'group "{group_id}" already exists')
        except Exception as error:
            return Response(None, ResponseCode.FAILURE, f'unexpected error: {error}; group "{group_id}"')

    def start(self):
        offset = 0
        while True:
            api_response = self.api.getUpdates(offset=offset, timeout=20)
            if not len(api_response['result']):
                continue
            for update in api_response['result']:
                if 'message' not in update or 'text' not in update['message']:
                    continue
                user_id = update['message']['from']['id']
                message = update['message']['text'].split(' ')
                # help / start
                if message[0] in ['/start', '/help']:
                    self.api.sendMessage(chat_id=user_id, text=SecretSanta.help)

                # create_new_group
                elif message[0] == '/cng':
                    response = self.create_new_group(user_id, None if len(message) == 1 else message[1])
                    if response.code == ResponseCode.OK:
                        self.api.sendMessage(chat_id=user_id, text=f'Вы создали группу "{response.result}"')
                    else:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                    logger.debug(response.comment)

                # connect_to_group
                elif message[0] == '/ctg':
                    if len(message) == 1:
                        self.api.sendMessage(chat_id=user_id, text=f'Вы не ввели ID группы')
                    else:
                        response = self.add_new_member(user_id, message[1])
                        if response.code == ResponseCode.OK:
                            self.api.sendMessage(chat_id=user_id, text=f'Вы добавились в группу "{message[1]}"')
                        else:
                            self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                        logger.debug(response.comment)

                # who to whom
                elif message[0] == '/wtw':
                    if len(message) == 1:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                        logger.debug(f'user "{user_id}" enter wrong ID in "who to whom" method')
                    else:
                        response = self.who_to_whom(user_id=user_id, group_id=message[1])
                        if response.code == ResponseCode.OK:
                            logger.debug(response.comment)
                        elif response.code == ResponseCode.INVALID_DATA:
                            self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                            logger.debug(response.comment)
                        elif response.code == ResponseCode.FAILURE:
                            self.api.sendMessage(chat_id=user_id,
                                                 text=f'Вы не администратор группы или в группе <= 1 участника')
                            logger.debug(response.comment)

                # info
                elif message[0] == '/info':
                    if len(message) == 1:
                        response = self.get_info_user(user_id)
                        self.api.sendMessage(chat_id=user_id, text=response.result)
                        logger.debug(response.comment)
                    else:
                        response = self.get_info_group(user_id, message[1])
                        if response.code == ResponseCode.OK:
                            self.api.sendMessage(chat_id=user_id, text=response.result)
                            logger.debug(response.comment)
                        else:
                            self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                            logger.debug(response.comment)

                # delete group
                elif message[0] == '/dlt':
                    if len(message) == 1:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                        logger.debug(f'user "{user_id}" enter wrong ID in "delete" method')
                    else:
                        response = self.delete_group(user_id, message[1])
                        if response.code == ResponseCode.OK:
                            self.api.sendMessage(chat_id=user_id, text=f'Вы удалили группу "{message[1]}"')
                            logger.debug(response.comment)
                        else:
                            self.api.sendMessage(chat_id=user_id,
                                                 text=f'Вы не администратор группы или в группе <= 1 участника')
                            logger.debug(response.comment)

                else:
                    self.api.sendMessage(chat_id=user_id, text=f'Попутал че?')

            offset = api_response['result'][-1]['update_id'] + 1
            self.cursor.execute('SELECT * FROM groups')
            logger.debug(f'Current state of groups: {self.cursor.fetchall()}')

    def add_new_member(self, user_id, group_id):
        self.cursor.execute(f'SELECT admin_id FROM groups WHERE uuid = "{group_id}"')
        response = self.cursor.fetchall()
        if not response:
            return Response(None, ResponseCode.INVALID_DATA, f'group_id "{group_id}" not exists')
        admin_id = response[0][0]
        self.cursor.execute(f'SELECT * FROM groups_users WHERE group_id = "{group_id}" AND user_id = {user_id}')
        response = self.cursor.fetchall()
        if response:
            return Response(None, ResponseCode.INVALID_DATA, f'used_id "{user_id}" already in group "{group_id}"')
        self.cursor.execute(f'INSERT INTO groups_users VALUES ("{group_id}", {user_id})')
        self.conn.commit()
        self.api.sendMessage(chat_id=admin_id,
                             text=f'В группу "{group_id}" добавился новый участник - {self.get_full_user_name(user_id)}')

        return Response(user_id, ResponseCode.OK, f'user "{user_id}" connected to group "{group_id}"')

    def get_info_user(self, user_id):
        text = f'Список групп в которых вы состоите:\n'
        self.cursor.execute(f'SELECT group_id FROM groups_users WHERE user_id = {user_id}')

        for database_tuple in self.cursor.fetchall():
            group_id = database_tuple[0]
            self.cursor.execute(f'SELECT * FROM groups_users WHERE group_id = "{group_id}"')
            text += f'\tID: "{group_id}", Количество участников: {len(self.cursor.fetchall())};\n'
        text += f'Список групп в которых вы админ:\n'
        self.cursor.execute(f'SELECT uuid FROM groups WHERE admin_id = {user_id}')
        for database_tuple in self.cursor.fetchall():
            group_id = database_tuple[0]
            self.cursor.execute(f'SELECT * FROM groups_users WHERE group_id = "{group_id}"')
            text += f'\tID: "{group_id}", Количество участников: {len(self.cursor.fetchall())};\n'
        logger.debug(f'Get info for user "{user_id}"')

        return Response(text, ResponseCode.OK, f'info gor user "{user_id}" get it')

    def get_full_user_name(self, user_id):
        print(user_id)
        response = self.api.getChat(chat_id=user_id)
        print(response)
        response = response['result']
        name = f'{response["first_name"]} {response["last_name"]}'
        if 'username' in response:
            name += f' (@{response["username"]})'
        logger.debug(f'Full name of {user_id} user is {name}')

        return name

    def get_info_group(self, user_id, group_id):
        self.cursor.execute(f'SELECT admin_id FROM groups WHERE uuid = "{group_id}"')
        response = self.cursor.fetchall()
        if not response:
            return Response(None, ResponseCode.INVALID_DATA, f'group "{group_id}" not exists')
        text = f'ID: "{group_id}"'
        admin_id = response[0][0]
        text += f'\nАдминистратор группы: {self.get_full_user_name(admin_id)}'
        text += f'\nСписок участников:'
        self.cursor.execute(f'SELECT user_id FROM groups_users WHERE group_id = "{group_id}" AND user_id = {user_id}')
        response = self.cursor.fetchall()
        if not response != user_id:
            return Response(None, ResponseCode.FAILURE, f'user "{user_id}" not in group "{group_id}"')

        self.cursor.execute(f'SELECT user_id FROM groups_users WHERE group_id = "{group_id}"')
        response = self.cursor.fetchall()
        for i, database_tuple in enumerate(response):
            member_id = database_tuple[0]
            text += f'\n{i + 1}. {self.get_full_user_name(member_id)}'
        if user_id == admin_id:
            text += '\nТекущая жеребьевка:'
            self.cursor.execute(f'SELECT from_id, to_id FROM pairs WHERE group_id = "{group_id}"')
            response = self.cursor.fetchall()
            if not response:
                text += f'\nЖеребьевка еще не была составлена'
            else:
                for pair in response:
                    text += f'\n{self.get_full_user_name(pair[0])} -> {self.get_full_user_name(pair[1])}'

        return Response(text, ResponseCode.OK, f'user "{user_id}" get it info about group "{group_id}"')

    def is_admin(self, user_id, group_id):
        self.cursor.execute(f'SELECT admin_id FROM groups WHERE uuid = "{group_id}"')
        response = self.cursor.fetchall()
        if not response:
            return Response(None, ResponseCode.INVALID_DATA, f'group "{group_id}" not exists')
        if response[0][0] != user_id:
            return Response(None, ResponseCode.FAILURE, f'user "{user_id}" not admin of group "{group_id}"')
        return Response(None, ResponseCode.OK, f'user "{user_id}" is admin of group "{group_id}"')

    def who_to_whom(self, user_id, group_id):
        response = self.is_admin(user_id, group_id)['result']
        if response.code != ResponseCode.OK:
            return response
        self.cursor.execute(f'DELETE FROM pairs WHERE group_id = "{group_id}"')
        self.cursor.execute(f'SELECT user_id FROM groups_users WHERE group_id = "{group_id}"')
        response = self.cursor.fetchall()
        if len(response) <= 1:
            return Response(None, ResponseCode.FAILURE, f'group "{group_id}" has <= 1 member')
        members = [user[0] for user in response]
        without_gift = members.copy()
        for member in members:
            while True:
                index = random.randint(0, len(without_gift) - 1)
                if without_gift[index] != member:
                    break
            self.cursor.execute(f'INSERT INTO pairs VALUES ("{group_id}", {member}, {without_gift[index]})')
            text = f'Группа "{group_id}": ' + \
                   f'Вы готовите подарок для {self.get_full_user_name(without_gift[index])}'
            self.api.sendMessage(chat_id=member, text=text)
            del without_gift[index]
        self.conn.commit()
        return Response(None, ResponseCode.OK, f'user "{user_id}" created "who to whom"')

    def delete_group(self, user_id, group_id):
        response = self.is_admin(user_id, group_id)
        if response.code != ResponseCode.OK:
            return response
        self.cursor.execute(f'DELETE FROM groups WHERE uuid = "{group_id}"')
        self.cursor.execute(f'DELETE FROM groups_users WHERE group_id = "{group_id}"')
        self.cursor.execute(f'DELETE FROM pairs WHERE group_id = "{group_id}"')
        self.conn.commit()
        return Response(None, ResponseCode.OK, f'user "{user_id}" delete group "{group_id}"')


def main():
    config = yaml.safe_load(open('config.yaml'))
    token, database_path = config['secretsanta']['telegram-token'], config['secretsanta']['database-path']
    secret_santa = SecretSanta(token, database_path)
    secret_santa.start()


if __name__ == '__main__':
    main()

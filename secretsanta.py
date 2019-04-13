import telegram
import logging
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

1. /cng [ID группы] - Создает новыю группу. Если не указан ID, то ID генерируется рандомным образом.
2. /ctg ID - Присоединиться к группе ID
3. /wtw ID - Распределить кто кому дарит подарки из группы ID
4. /info [ID группы] - Получить информацию о ваших группах. Если указан ID, то ID выводится подробная информация о \
группе.
5. /help - Помощь 
'''

    class Group:
        def __init__(self, admin, group_id):
            self.admin = admin
            self.members = [admin]
            self.group_id = group_id

        def __repr__(self):
            return self.__str__()

        def __str__(self):
            return f'{{group_id: {self.group_id}, admin_id: {self.admin.user_id}}}'

    class User:
        def __init__(self, user_id):
            self.user_id = user_id
            self.groups = []
            self.admin_groups = []

        def __repr__(self):
            return self.__str__()

        def __str__(self):
            return f'{{user_id: {self.user_id}, admin_groups: {self.admin_groups}, groups: {self.groups}}}'

    def __init__(self, token):
        self.groups = dict()
        self.users = dict()
        self.api = telegram.TelegramAPI(token)

    def create_new_group(self, admin: User, group_id):
        if group_id is None:
            while True:
                group_id = rand_id()
                if group_id not in self.groups:
                    break
        if group_id in self.groups:
            return None
        group = SecretSanta.Group(admin, group_id)
        admin.groups.append(group)
        admin.admin_groups.append(group)
        self.groups[group_id] = group
        logger.info(f'Group {group_id} created by user {admin.user_id}')
        return group

    def start(self):
        offset = 0
        while True:
            response = self.api.getUpdates(offset=offset, timeout=10)
            if not len(response['result']):
                continue
            for update in response['result']:
                if 'message' not in update or 'text' not in update['message']:
                    continue
                user_id = update['message']['from']['id']
                if user_id not in self.users:
                    user = SecretSanta.User(user_id)
                    self.users[user_id] = user
                else:
                    user = self.users[user_id]
                message = update['message']['text'].split(' ')
                # help / start
                if message[0] in ['/start', '/help']:
                    self.api.sendMessage(chat_id=user_id, text=SecretSanta.help)

                # create_new_group
                if message[0] == '/cng':
                    group = self.create_new_group(user, None if len(message) == 1 else message[1])
                    if group is None:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID!')
                    else:
                        self.api.sendMessage(chat_id=user_id,
                                             text=f'Новая группа создана. Название: "{group.group_id}"')
                # connect_to_group
                if message[0] == '/ctg':
                    try:
                        group = self.groups[message[1]]
                    except:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID!')
                        continue
                    self.add_new_member(user, group)

                # who to whom
                if message[0] == '/wtw':
                    if len(message) <= 1 or message[1] not in self.groups:
                        self.api.sendMessage(chat_id=user_id, text=f'Неправильный ID')
                        logger.debug(f'User {user_id} enter wrong ID in "who to whom" method')
                    elif self.groups[message[1]].admin.user_id != user_id:
                        self.api.sendMessage(chat_id=user_id, text=f'Вы не админ группы "{message[1]}"')
                    else:
                        self.who_to_whom(self.groups[message[1]])

                # info
                if message[0] == '/info':
                    if len(message) == 1:
                        self.api.sendMessage(chat_id=user_id, text=self.get_info_user(user))
                    else:
                        self.api.sendMessage(chat_id=user_id,
                                             text=self.get_info_group(group=self.groups[message[1]]))
            offset = response['result'][-1]['update_id'] + 1
            logger.debug(f'Current state of groups: {self.groups}')

    def add_new_member(self, user: User, group):
        if user not in group.members:
            user.groups.append(group)
            group.members.append(user)
            response = self.api.getChat(chat_id=user.user_id)
            name = f'@{response["result"]["username"]}'
            self.api.sendMessage(chat_id=user.user_id, text=f'Вы добавились в группу "{group.group_id}"!')
            self.api.sendMessage(chat_id=group.admin.user_id,
                                 text=f'В группу "{group.group_id}" добавился новый участник - {name}')
            logger.info(f'User {user.user_id} connected to group {group.group_id}')
        else:
            self.api.sendMessage(chat_id=user.user_id, text=f'Вы уже состоите в группе "{group.group_id}"!')
            logger.debug(f'User {user.user_id} already exists in  group {group.group_id}')

    @staticmethod
    def get_info_user(user):
        text = f'Список групп в которых вы состоите:\n'
        for group in user.groups:
            text += f'\tID: {group.group_id}, Количество участников: {len(group.members)};\n'
        text += f'Список групп в которых вы админ:\n'
        for group in user.admin_groups:
            text += f'\tID: {group.group_id}, Количество участников: {len(group.members)};\n'
        return text

    def get_info_group(self, group):
        text = f'ID: {group.group_id}'
        text += f'\nСписок участников:'
        for i, member in enumerate(group.members):
            text += f'\n{i + 1}. @{self.api.getChat(chat_id=member.user_id)["result"]["username"]}'
        return text

    def who_to_whom(self, group):
        if len(group.members) <= 1:
            return self.api.sendMessage(chat_id=group.admin.user_id,
                                        text=f'В группе должно быть более двух участников!')
        without_gift = group.members.copy()
        for member in group.members:
            while True:
                index = random.randint(0, len(without_gift) - 1)
                if without_gift[index] != member:
                    break
            self.api.sendMessage(chat_id=member.user_id,
                                 text=f'Группа {group.group_id}: Вы готовите подарок для \
                                 @{self.api.getChat(chat_id=without_gift[index].user_id)["result"]["username"]}')
            del without_gift[index]


def main():
    with open('token.txt', 'r') as file:
        token = file.read()
    secret_santa = SecretSanta(token)
    secret_santa.start()


if __name__ == '__main__':
    main()

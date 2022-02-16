import datetime
import json
import os

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType

import requests

session = vk_api.VkApi(token=os.environ['VK_TOKEN'], api_version='5.131')

weekdays = {"пн": "понедельник", "вт": "вторник", "ср": "среду", "чт": "четверг", "пт": "пятницу", "сб": "субботу",
            "вс": "воскресенье"}
weekday = datetime.datetime.today().weekday()
message_history = {}

schedule_aliases = [
    "уроки",
    "расписание уроков"
]
timetable_aliases = [
    "звонки",
    "расписание звонков"
]
group_aliases = [
    "сменить класс",
    "класс",
]


def send_message(user_id, message, keyboard=None):
    post = {
        "user_id": user_id,
        "message": message,
        "random_id": 0
    }

    if keyboard is not None:
        post["keyboard"] = keyboard.get_keyboard()

    session.method("messages.send", post)


def send_weekday_keyboard(user_id):
    keyboard = VkKeyboard(inline=True)
    k = 0
    for d in weekdays.keys():
        c = VkKeyboardColor.SECONDARY
        if weekday == k:
            c = VkKeyboardColor.POSITIVE
        keyboard.add_button(d.capitalize(), c)
        k += 1
        if k == 5:
            keyboard.add_line()  # max 5 buttons on a line
    send_message(user_id, "Выберите день недели", keyboard)


def send_menu_keyboard(user_id):
    keyboard = VkKeyboard()
    keyboard.add_button("Расписание уроков", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Расписание звонков", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Посмотреть изменения", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Сменить класс", VkKeyboardColor.SECONDARY)
    send_message(user_id,
                 "Доступные команды:\n- \"уроки\" — узнать расписание уроков\n- \"звонки\" — узнать расписание "
                 "звонков\n- \"класс\" — установить класс для которого будет отображаться расписание\n- \"меню\" — "
                 "показать это меню\n- \"отмена\" — отменить какое-либо действие\n\nНапишите команду в чат с ботом "
                 "или воспользуйтесь кнопками. Все команды и аргументы нечувствительны к регистру",
                 keyboard)


def assign_group(user_id, group):
    f = open('requests/student_create_request.json')
    mydata = f.read().replace("%d", str(user_id)).replace("%s", group).encode('utf-8')  # todo properly format it
    insert_student_response = requests.put('http://localhost:8080/students', data=mydata,
                                           headers={'Content-Type': 'application/json'})
    f.close()
    return insert_student_response.status_code


def get_prev_message(user_id):
    if user_id in message_history:
        return message_history[user_id]
    return ""


def set_prev_message(user_id, message):
    message_history[user_id] = message


for event in VkLongPoll(session).listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        text = str(event.text.lower()).strip()
        user_id = event.user_id
        if text == "":  # filter only text messages
            send_message(user_id, 'Бот распознаёт только текстовые сообщения')
            continue

        if text == "." or text == "отмена":
            send_message(user_id, 'Действие отменено')
            set_prev_message(user_id, text)
            continue

        if get_prev_message(user_id) in group_aliases:
            group = text.upper()
            group_exist_response = requests.get(f'http://localhost:8080/groups/{group}')

            if group_exist_response.status_code == 200:
                assignment_status_code = assign_group(user_id, group)
                if assignment_status_code == 200:
                    send_message(user_id, f"Теперь все расписание будет отображаться для {group} класса")
                else:
                    send_message(user_id,
                                 f"༼ つ ◕_◕ ༽つ Произошла внутренняя ошибка. Код ошибки: {assignment_status_code}")
                set_prev_message(user_id, text)
            else:
                send_message(user_id, 'Такой класс не существует. Напишите "отмена" для отмены выбора класса')
            continue

        if text in group_aliases:
            send_message(user_id, 'Напишите свой класс в формате "цифра-буква". Например, "11Б" или "7А"')
            set_prev_message(user_id, 'класс')
            continue

        if text == "start" or text == "меню" or text == "menu" or text == "помощь" or text == "начать":
            send_menu_keyboard(user_id)
            set_prev_message(user_id, text)
            continue

        if text in schedule_aliases or text in timetable_aliases:
            send_weekday_keyboard(user_id)
            set_prev_message(user_id, text)
            continue

        if text in weekdays.keys():
            if get_prev_message(user_id) in schedule_aliases:
                group_exist_response = requests.get(f'http://localhost:8080/students/{user_id}')
                if group_exist_response.status_code == 404:
                    send_message(user_id, 'Напишите свой класс в формате "цифра-буква". Например, "11Б" или "7А"')
                    set_prev_message(user_id, 'класс')
                    continue
                if group_exist_response.status_code == 200:
                    content = json.loads(group_exist_response.content)
                    if content:
                        group = content['group']['display_name']
                        send_message(user_id, f"Расписание уроков у {group} класса на {weekdays[text]}")
                        day_of_week = list(weekdays.keys()).index(text) + 1

                        r_schedule = requests.get(f'http://localhost:8080/schedules/{group}/{day_of_week}')
                        if r_schedule.status_code == 200:
                            schedule_content = json.loads(r_schedule.content)
                            if schedule_content:
                                msg = ""
                                for entry in schedule_content:
                                    msg += f"{entry['lesson']}. {entry['subject']}\n"
                                send_message(user_id, msg)
                            else:
                                send_message(user_id, "Расписание отсутствует")
                        else:
                            send_message(user_id,
                                         f"༼ つ ◕_◕ ༽つ Произошла внутренняя ошибка. Код ошибки: {r_schedule.status_code}")
                    else:
                        send_message(user_id, f"༼ つ ◕_◕ ༽つ Произошла внутренняя ошибка. Код ошибки: empty content")
                else:
                    send_message(user_id,
                                 f"༼ つ ◕_◕ ༽つ Произошла внутренняя ошибка. Код ошибки: {group_exist_response.status_code}")

            if get_prev_message(user_id) in timetable_aliases:
                day_of_week = list(weekdays.keys()).index(text) + 1
                r_timetable = requests.get(f'http://localhost:8080/timetables/{day_of_week}')
                if r_timetable.status_code == 200:
                    timetable_content = json.loads(r_timetable.content)
                    send_message(user_id, f"Расписание звонков на {weekdays[text]}")
                    if timetable_content:
                        msg = ""
                        for entry in timetable_content:
                            break_duration = int(entry['break_duration'] // 60)
                            msg += f"{entry['lesson']}. {entry['start_time']} — {entry['end_time']}, перемена {break_duration} мин\n"
                        send_message(user_id, msg)
                    else:
                        send_message(user_id, "Расписание отсутствует")
                else:
                    send_message(user_id,
                                 f"༼ つ ◕_◕ ༽つ Произошла внутренняя ошибка. Код ошибки: {r_timetable.status_code}")

            continue
        else:
            send_message(user_id, '¯\_(ツ)_/¯ Неизвестная команда. Напишите "меню", чтобы отобразить список команд')

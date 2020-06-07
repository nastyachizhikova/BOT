#  Это бот-помощник и мотиватор. Если просто писать
#  ему сообщение, он ответит умным высказыванием, сгенерированным на
#  базе мотивирующих цитат из пабликов ВКонтакте
#  Также он может помочь сделать все дела за день:
#  для этого нужно выбрать команду "начать день"



import conf
import datetime
import markovify
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import sqlite3
import telebot

from telebot import types



bot = telebot.TeleBot(conf.TOKEN)

#  обучаем марковскую цепь на мотивирующих цитатах из ВК

with open('motivation_text.txt', encoding='utf-8') as f:
    motivation_text = f.read()
text_model = markovify.Text(motivation_text)

score_types = ["1 (наверное, получится завтра...)",
              "2 (бывало лучше, но что-то сегодня мне удалось!)",
              "3 (я был(-а) неплох(-а)!",
              "4 (я хорошо постарался(-ась)!",
              "5 (я супер молодец!)"]


''' db = sqlite3.connect('mot_bot.db')
c = db.cursor()

c.execute("DROP TABLE IF EXISTS success_score")

c.execute("""
        CREATE TABLE success_score (
            user TEXT,
            date TEXT,
            score INT
        )"""
        )

db.commit()
db.close()'''

#  эта функция строит график для выполненных и невыполненных за день дел
def create_piechart(todos_num, done_num):
    try:
        os.remove('todos.png')
    except FileNotFoundError:
        pass
    segm = np.ones(todos_num)
    colors = []
    explode = []
    for c in range(done_num):
        colors.append('purple')
        explode.append(0.05)
    for c in range(todos_num - done_num):
        colors.append('pink')
        explode.append(0.05)

    fig1, ax1 = plt.subplots(figsize=(15, 15))
    ax1.pie(segm, explode=explode, colors=colors)
    ax1.set_title('Дела на день')
    fig1.savefig('todos.png')


#  эта функция обращается к БД со всеми самооценками пользователя и строит статистику за последнее время
def create_success_graph(id):
    db = sqlite3.connect('mot_bot.db')
    c = db.cursor()

    c.execute("SELECT score FROM success_score WHERE user=? ORDER BY date ASC", (id, ))
    score = c.fetchall()
    c.execute("SELECT date FROM success_score WHERE user=? ORDER BY date ASC", (id, ))
    date = c.fetchall()

    dates = []
    scores = []
    for d in date:
        dates.append(d[0])
    for s in score:
        scores.append(s[0])
    db.commit()
    db.close()

    if len(scores) > 10:
        dates = dates[:-10:-1]
        scores = scores[:-10:-1]

    try:
        os.remove('success.png')
    except FileNotFoundError:
        pass

    fig, ax = plt.subplots(figsize=(15, 15))
    ax.plot(dates, scores, 'r-o')
    ax.set_title('График успешности')
    ax.set_xlabel("Дата")
    ax.set_ylabel("Баллы")
    fig.savefig('success.png')


#  приветствие
@bot.message_handler(commands=['start', 'help'])
def start(message):
    text = 'Здравствуйте! Это бот-мотиватор.'
    bot.send_message(message.chat.id, text)
    text = 'Если вы просто напишите мне текстовое сообщение, я отвечу глубокой мотивирующей цитатой. Стоит задуматься.'
    bot.send_message(message.chat.id, text)
    text = 'При вызове команды /start_day начнется наш рабочий день: вы напишите мне список дел, которые вам сегодня нужно сделать, а потом постепенно будете заполнять выполненные дела.'
    bot.send_message(message.chat.id, text)
    text = 'В конце вы оцените себя и сможете посмотреть статистику вашей успешности за последнее время. Успешной работы!'
    bot.send_message(message.chat.id, text)


#  начинаем день
@bot.message_handler(commands=['start_day'])
def welcome(message):
    text = 'Добрый день, ' + message.from_user.first_name + '!'
    bot.send_message(message.chat.id, text)

    variants = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
    item1 = types.InlineKeyboardButton("Работаем!")
    item2 = types.InlineKeyboardButton("Отдыхаем!")
    variants.add(item1, item2)
    today = bot.send_message(message.chat.id, 'Сегодня работаем или отдыхаем?', reply_markup=variants)
    bot.register_next_step_handler(today, ask_things)


#  спрашиваем список дел или заканчиваем
def ask_things(message):
    if message.text == 'Работаем!':
        things = bot.send_message(message.chat.id, 'Какие дела нужно сегодня сделать? (напишите одно дело на каждой строчке)')

        bot.register_next_step_handler(things, start_things)
    else:
        bot.send_message(message.chat.id, 'Супер, отличного отдыха!')


#  записываем список дел в БД и строим первый график
def start_things(message):
    todos = message.text.split('\n')
    todos_num = len(todos)
    bot.send_message(message.chat.id, 'Супер, всего ' + str(todos_num) + ' дел!')

    db = sqlite3.connect('mot_bot.db')
    c = db.cursor()
    c.execute("DROP TABLE IF EXISTS todos")

    c.execute("""
            CREATE TABLE todos (
                type TEXT,
                name TEXT,
                state INT
            )"""
              )
    for t in todos:
        t_ = t.lower().strip(' ')
        c.execute("INSERT INTO todos VALUES (?, ?, ?)", ('TODO', t_, 0))
    db.commit()
    db.close()

    create_piechart(todos_num, 0)
    todos = open('todos.png', 'rb')
    bot.send_photo(message.chat.id, todos)
    first_done = bot.send_message(message.chat.id, 'Сообщите, какое дело вы выполнили первым')
    bot.register_next_step_handler(first_done, complete_todos)


#  выполняем дела, пока несделанных дел в БД не станет 0
#  когда их станет 0, самооцениваемся
def complete_todos(message):
    t = message.text.lower().strip(' ')

    db = sqlite3.connect('mot_bot.db')
    c = db.cursor()
    c.execute("SELECT name FROM todos WHERE state=0")
    n = c.fetchall()
    not_done = [i[0] for i in n]
    c.execute("SELECT name FROM todos WHERE state=1")
    d = c.fetchall()
    done = [i[0] for i in d]
    if t in done:
        thing = bot.send_message(message.chat.id, 'Это мы и так уже сделали! Что еще?')
        db.commit()
        db.close()
        bot.register_next_step_handler(thing, complete_todos)
    elif t in not_done:
        c.execute('UPDATE todos SET state = 1 WHERE name = ?', (t,))
        bot.send_message(message.chat.id, 'Класс!')
        db.commit()
        db.close()
        if len(not_done) - 1 == 0:
            bot.send_message(message.chat.id, message.from_user.first_name + ', вы сделали все дела на сегодня!')
            create_piechart(len(not_done) + len(done), len(done) + 1)
            todos = open('todos.png', 'rb')
            bot.send_photo(message.chat.id, todos)

            variants = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)
            item1 = types.InlineKeyboardButton(score_types[0])
            item2 = types.InlineKeyboardButton(score_types[1])
            item3 = types.InlineKeyboardButton(score_types[2])
            item4 = types.InlineKeyboardButton(score_types[3])
            item5 = types.InlineKeyboardButton(score_types[4])
            variants.add(item1, item2, item3, item4, item5)
            score = bot.send_message(message.chat.id,
                             message.from_user.first_name + ', оцените, насколько вы сегодня молодец',
                             reply_markup=variants)
            bot.register_next_step_handler(score, end_day)
        else:
            bot.send_message(message.chat.id, 'Осталось всего ' + str(len(not_done) - 1) + ' дел')
            create_piechart(len(not_done) + len(done), len(done) + 1)
            todos = open('todos.png', 'rb')
            bot.send_photo(message.chat.id, todos)

            thing = bot.send_message(message.chat.id, message.from_user.first_name + ', cообщите, когда сделаете что-то еще')
            bot.register_next_step_handler(thing, complete_todos)
    else:
        thing = bot.send_message(message.chat.id, 'Такого в списке не было! Давайте по списку.')
        db.commit()
        db.close()
        bot.register_next_step_handler(thing, complete_todos)


#  записываем самооценку
#  и спрашиваем, хочет ли юзер знать статистику
def end_day(message):
    score = int(message.text[0])
    date = datetime.datetime.today()
    db = sqlite3.connect('mot_bot.db')
    c = db.cursor()
    c.execute("INSERT INTO success_score VALUES (?, ?, ?)", (message.from_user.id, date, score))
    db.commit()
    db.close()
    variants = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
    item1 = types.InlineKeyboardButton("Да")
    item2 = types.InlineKeyboardButton("Нет")
    variants.add(item1, item2)
    stat = bot.send_message(message.chat.id, 'Вы хотите узнать статистику вашей успешности?', reply_markup=variants)
    bot.register_next_step_handler(stat, build_statistics)


#  выдаем статистику или просто заканчиваем
def build_statistics(message):
    if message.text == 'Да':
        bot.send_message(message.chat.id, 'Посмотрим, как вы справлялись последнюю неделю')
        create_success_graph(message.from_user.id)

        suc_graph = open('success.png', 'rb')
        bot.send_photo(message.chat.id, suc_graph)
    else:
        bot.send_message(message.chat.id, 'Хорошо, приятного отдыха')


#  генератор цитат для текстовых сообщений вне рабочего дня
@bot.message_handler(content_types=['text'])
def motivation(message):
    mot = text_model.make_short_sentence(200)
    bot.send_message(message.chat.id, mot)


if __name__ == '__main__':
    bot.polling(none_stop=True)
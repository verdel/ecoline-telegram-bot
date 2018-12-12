#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
import logging
import re
import yaml
from functools import wraps
from datetime import datetime, timedelta
from collections import OrderedDict
from ecoline import Ecoline
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ChatAction
from emoji import emojize


def get_config():
    try:
        with open("config.yml", 'r') as ymlfile:
            cfg = yaml.load(ymlfile)
    except Exception as exc:
        logger.error('Config file error: {}'.format(exc))
        sys.exit(1)
    else:
        return cfg


def init_log(debug=None):
    if debug:
        consolelog_level = logging.DEBUG
        # filelog_level = logging.DEBUG
    else:
        consolelog_level = logging.INFO
        # filelog_level = logging.INFO

    logger = logging.getLogger('ecoline-telegram-bot')
    logger.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    consolelog = logging.StreamHandler()
    consolelog.setLevel(consolelog_level)

    # create file handler which logs even debug messages
    # filelog = logging.FileHandler('ecoline.log')
    # filelog.setLevel(filelog_level)

    # create formatter and add it to the handlers
    formatter = logging.Formatter(u'%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s')
    # filelog.setFormatter(formatter)
    consolelog.setFormatter(formatter)

    # add the handlers to logger
    logger.addHandler(consolelog)
    # logger.addHandler(filelog)

    return logger


def ecoline_auth(ecoline=None, debug=None):
    if not ecoline:
        try:
            ecoline = Ecoline(username=cfg['ecoline']['username'], password=cfg['ecoline']['password'], debug=debug)
        except Exception as exc:
            logger.error('Auth error "%s"' % exc)

    elif not ecoline.check_auth():
        try:
            ecoline = Ecoline(username=cfg['ecoline']['username'], password=cfg['ecoline']['password'], debug=debug)
        except Exception as exc:
            logger.error('Auth error "%s"' % exc)

    return ecoline


def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if cfg['telegram']['allow_chat']:
            allowed_group = chat_id in cfg['telegram']['allow_chat']
        else:
            allowed_group = False

        if cfg['telegram']['allow_user']:
            allowed_user = user_id in cfg['telegram']['allow_user']
        else:
            allowed_user = False

        if allowed_user or allowed_group:
            return func(bot, update, *args, **kwargs)
        else:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Ой! Вы не авторизованы для работы с ботом.'
            )
            return
    return wrapped


def sanitaize_time_periods(periods=None):
    tm_sanitaize = {}
    if isinstance(periods, dict):
        tm_sanitaize = {}
        now = int(datetime.now().hour)
        for k, v in periods.iteritems():
            start_hour = int(v.split('-')[0].split('.')[0])
            if start_hour > now:
                tm_sanitaize.update({k: v})
    return tm_sanitaize


def make_reply_keyboard():
    custom_keyboard = [[u'{}Заказ'.format(emojize(':moneybag:', use_aliases=True))],
                       [u'{}Бонус'.format(emojize(':gift:', use_aliases=True)), u'{}История'.format(emojize(':date:', use_aliases=True))]]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)
    return reply_markup


def make_date_keyboard():
    tm = sanitaize_time_periods(time_periods)
    if not tm:
        today = datetime.today().date() + timedelta(days=1)
    else:
        today = datetime.today().date()

    if today.isoweekday() > 5:
        first_date = today + timedelta(days=(8 - today.isoweekday()))
    else:
        first_date = today

    if first_date == datetime.today().date():
        first_button = InlineKeyboardButton('Сегодня', callback_data='date:{}'.format(first_date.strftime('%d.%m.%Y')))

    elif first_date == (datetime.today().date() + timedelta(days=1)):
        first_button = InlineKeyboardButton('Завтра', callback_data='date:{}'.format(first_date.strftime('%d.%m.%Y')))

    else:
        first_button = InlineKeyboardButton(first_date.strftime('%d.%m.%Y'), callback_data='date:{}'.format(first_date.strftime('%d.%m.%Y')))

    second_date = first_date + timedelta(days=1)

    if second_date.isoweekday() > 5:
        second_date = second_date + timedelta(days=(8 - second_date.isoweekday()))

    if second_date == (datetime.today().date() + timedelta(days=1)):
        second_button = InlineKeyboardButton('Завтра', callback_data='date:{}'.format(second_date.strftime('%d.%m.%Y')))
    else:
        second_button = InlineKeyboardButton(second_date.strftime('%d.%m.%Y'), callback_data='date:{}'.format(second_date.strftime('%d.%m.%Y')))

    reply_markup = InlineKeyboardMarkup([[first_button, second_button],
                                         [InlineKeyboardButton('Отменить заказ', callback_data='cancel')]])
    return reply_markup


def make_time_keyboard():
    if datetime.today().date().strftime('%d.%m.%Y') == order_properties['ORDER_PROP_6']:
        tm = sanitaize_time_periods(time_periods)
    else:
        tm = time_periods
    time = OrderedDict(sorted(tm.items(), key=lambda t: t[0]))
    count = 1
    keyboard_array = []
    line_array = []
    for i, (k, v) in enumerate(time.iteritems()):
        if count == 4 or i == (len(time) - 1):
            keyboard_array.append(line_array)
            count = 1
            line_array = [InlineKeyboardButton(v, callback_data='time:{}'.format(k))]
        else:
            line_array.append(InlineKeyboardButton(v, callback_data='time:{}'.format(k)))
        count += 1

    keyboard_array.append([InlineKeyboardButton('Отменить заказ', callback_data='cancel')])
    keyboard_array = InlineKeyboardMarkup(keyboard_array)
    return keyboard_array


def make_pay_keyboard():
    bonus = int(ecoline.get_bonus())
    keyboard_array = InlineKeyboardMarkup([[InlineKeyboardButton('Наличными', callback_data='pay:1')],
                                           [InlineKeyboardButton('Бонусами ({})'.format(bonus), callback_data='pay:2')],
                                           [InlineKeyboardButton('Отменить заказ', callback_data='cancel')]])
    return keyboard_array


def make_apply_keyboard():
    keyboard_array = InlineKeyboardMarkup([[InlineKeyboardButton('Подвердить', callback_data='apply')],
                                           [InlineKeyboardButton('Отменить заказ', callback_data='cancel')]])
    return keyboard_array


def order_handler(bot, update):
    bot.sendChatAction(update.callback_query.message.chat.id, action=ChatAction.TYPING)
    global ecoline
    ecoline = ecoline_auth(ecoline)

    if update.callback_query.data == 'order':
        bot.editMessageReplyMarkup(
            message_id=update.callback_query.message.message_id,
            chat_id=update.callback_query.message.chat.id,
            reply_markup=make_date_keyboard()
        )
    elif update.callback_query.data == 'cancel':
        ecoline.clear_basket()
        bot.delete_message(
            message_id=update.callback_query.message.message_id,
            chat_id=update.callback_query.message.chat.id,
        )

    elif re.match('^date:(\d+\.\d+\.\d+)', update.callback_query.data):
        date = re.search('^date:(\d+\.\d+\.\d+)', update.callback_query.data).group(1)
        order_properties['ORDER_PROP_6'] = date
        bot.editMessageText(
            message_id=update.callback_query.message.message_id,
            chat_id=update.callback_query.message.chat.id,
            text=update.callback_query.message.text + u'\r\n\r\nДата доставки: {}'.format(date),
            reply_markup=make_time_keyboard()
        )

    elif re.match('^time:CT[1-8]{1}', update.callback_query.data):
        time_id = re.search('^time:(CT[1-8]{1})', update.callback_query.data).group(1)
        order_properties['ORDER_PROP_7'] = time_id
        try:
            order_properties.update(ecoline.get_order_properties())
        except Exception as exc:
            error(bot, update, exc)
            bot.editMessageText(
                message_id=update.callback_query.message.message_id,
                chat_id=update.callback_query.message.chat.id,
                text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.',
                reply_markup=False
            )
            try:
                ecoline.clear_basket()
            except Exception as exc:
                error(bot, update, exc)

        else:
            try:
                bonus = int(ecoline.get_bonus())
                cost = int(unicode(ecoline.get_basket_cost()).replace(u' руб.', u''))
            except Exception as exc:
                logger.error('Pay error "%s"' % exc)
                order_properties['PAY_SYSTEM_ID'] = 1
                bot.editMessageText(
                    message_id=update.callback_query.message.message_id,
                    chat_id=update.callback_query.message.chat.id,
                    text=update.callback_query.message.text + u'\r\nВремя доставки: {}\r\nОплата: Наличными'.format(time_periods[time_id]),
                    reply_markup=make_apply_keyboard()
                )
            else:
                if bonus >= cost:
                    bot.editMessageText(
                        message_id=update.callback_query.message.message_id,
                        chat_id=update.callback_query.message.chat.id,
                        text=update.callback_query.message.text + u'\r\nВремя доставки: {}'.format(time_periods[time_id]),
                        reply_markup=make_pay_keyboard()
                    )
                else:
                    order_properties['PAY_SYSTEM_ID'] = 1
                    bot.editMessageText(message_id=update.callback_query.message.message_id,
                                        chat_id=update.callback_query.message.chat.id,
                                        text=update.callback_query.message.text + u'\r\nВремя доставки: {}\r\nОплата: Наличными'.format(time_periods[time_id]),
                                        reply_markup=make_apply_keyboard()
                                        )

    elif re.match('^pay:[1-2]{1}', update.callback_query.data):
        pay_id = int(re.search('^pay:([1-2]{1})', update.callback_query.data).group(1))
        if pay_id == 1:
            order_properties['PAY_SYSTEM_ID'] = 1
            bot.editMessageText(
                message_id=update.callback_query.message.message_id,
                chat_id=update.callback_query.message.chat.id,
                text=update.callback_query.message.text + u'\r\nОплата: Наличными',
                reply_markup=make_apply_keyboard()
            )
        elif pay_id == 2:
            order_properties['PAY_SYSTEM_ID'] = 2
            bot.editMessageText(
                message_id=update.callback_query.message.message_id,
                chat_id=update.callback_query.message.chat.id,
                text=update.callback_query.message.text + u'\r\nОплата: Бонусами',
                reply_markup=make_apply_keyboard()
            )

    elif update.callback_query.data == 'apply':
        try:
            order_status = ecoline.checkout(order_properties)
        except Exception as exc:
            error(bot, update, exc)
            bot.editMessageText(
                message_id=update.callback_query.message.message_id,
                chat_id=update.callback_query.message.chat.id,
                text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.',
                reply_markup=False
            )
            try:
                ecoline.clear_basket()
            except Exception as exc:
                error(bot, update, exc)
        else:
            if order_status['status'] == 'ok' and order_status['properties'] == 'ok':
                bot.editMessageText(
                    message_id=update.callback_query.message.message_id,
                    chat_id=update.callback_query.message.chat.id,
                    text=update.callback_query.message.text + u'\r\nСтатус заказа: {}'.format(emojize(':white_check_mark:', use_aliases=True)),
                    reply_markup=False
                )
            elif order_status['status'] == 'error':
                bot.editMessageText(
                    message_id=update.callback_query.message.message_id,
                    chat_id=update.callback_query.message.chat.id,
                    text=update.callback_query.message.text + u'\r\nСтатус заказа: {}'.format(emojize(':no_entry:', use_aliases=True)),
                    reply_markup=False
                )
            elif order_status['status'] == 'ok' and order_status['properties'] == 'error':
                bot.editMessageText(
                    message_id=update.callback_query.message.message_id,
                    chat_id=update.callback_query.message.chat.id,
                    text=update.callback_query.message.text + u'\r\nСтатус заказа: {} {}'.format(emojize(':rotating_light:', use_aliases=True), 'Заказ принят. Ошибка в выборе товара.'),
                    reply_markup=False
                )

            try:
                history = open(cfg['common']['history_path'], 'w')
            except:
                history = open('order.log', 'w')

            date_now = datetime.today().date().strftime('%d.%m.%Y')
            time_now = datetime.today().strftime('%H:%m:%S')
            order_date = order_properties['ORDER_PROP_6']
            order_time = time_periods[order_properties['ORDER_PROP_7']]
            order_pay = 'Наличными' if order_properties['PAY_SYSTEM_ID'] == 1 else 'Бонусами'
            history.write('{0};{1};{2};{3};{4};{5};{6}'.format(date_now,
                                                               time_now,
                                                               order_date,
                                                               order_time,
                                                               order_pay,
                                                               update.callback_query.from_user.first_name,
                                                               update.callback_query.from_user.id))
            history.close()
            logger.info(u'Order request: [Date: {0}, Time: {1}, Pay: {2}] from user {3}, id {4}, order id {5}, order status {6}, properties status: {7}'.format(order_date,
                                                                                                                                                                order_time,
                                                                                                                                                                order_pay.decode('utf-8'),
                                                                                                                                                                update.callback_query.from_user.first_name,
                                                                                                                                                                update.callback_query.from_user.id,
                                                                                                                                                                order_status['id'] if order_status['status'] == 'ok' else 'None',
                                                                                                                                                                order_status['status'],
                                                                                                                                                                order_status['properties']))


def message_handler(bot, update):
    routes = {u'Бонус': bonus,
              u'История': history,
              u'Заказ': order}

    try:
        route = next(v for k, v in routes.items() if k in update.message.text)
    except:
        unknown(bot, update)
    else:
        route(bot, update)


def error(bot, update, error):
    logger.error('Update "%s" caused error "%s"' % (update, '{}({})'.format(type(error).__name__, error)))


@restricted
def start(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'Добро пожаловать.',
        reply_markup=make_reply_keyboard()
    )


@restricted
def help(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'Заказ - произвести заказ воды\r\nБонус - просмотр бонусного баланса\r\nИстория - просмотр истории заказов'
    )


@restricted
def unknown(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'Простите, я не поддерживаю этот тип запросов.'
    )


@restricted
def bonus(bot, update):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global ecoline
        ecoline = ecoline_auth(ecoline)
        bonus = ecoline.get_bonus()
    except Exception as exc:
        error(bot, update, exc)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
        )
    else:
        if bonus:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Бонусный баланс: {}'.format(int(bonus))
            )
            logger.info('Bonus request from user {}, id {} complete success'.format(update.message.from_user.first_name,
                                                                                    update.message.from_user.id))


@restricted
def history(bot, update):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global ecoline
        ecoline = ecoline_auth(ecoline)
        orders_history = ecoline.get_last_order()
    except Exception as exc:
        error(bot, update, exc)
    else:
        if orders_history:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Информация с сайта:\r\nПредыдущий заказ был сделан: {}\r\nПрошло дней: {}'.format(orders_history['date'], orders_history['diff'])
            )
            try:
                history = open(cfg['common']['history_path'], 'r')
            except:
                history = open('order.log', 'r')
            history_item = history.readline().split(';')
            if history_item and history_item[0] != '':
                history_item.append((datetime.now() - datetime.strptime(history_item[0], '%d.%m.%Y')).days)
                history_item[4] = history_item[4].decode('utf-8')
                bot.sendMessage(
                    chat_id=update.message.chat_id,
                    text=u'Информация от бота:\r\nПредыдущий заказ был сделан: {} {}\r\nЗаказ на дату: {}\r\nЗаказ на время: {}\r\nОплата: {}\r\nПользователь: {} (id: {})\r\nПрошло дней: {}'''.format(*history_item)
                )
            logger.info('History request from user {}, id {} complete success'.format(update.message.from_user.first_name,
                                                                                      update.message.from_user.id))


@restricted
def order(bot, update):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global ecoline
        ecoline = ecoline_auth(ecoline)
        if ecoline.clear_basket():
            ecoline.add_to_basket(cfg['ecoline']['product']['name'], cfg['ecoline']['product']['quantity'])
            text = u'Содержимое корзины:'
            for item in ecoline.get_basket():
                text = u'{}\r\n- {} - {} шт'.format(text, item['name'], item['quantity'])
            text = u'{}\r\n\r\nИтоговая стоимость: {}'.format(text, ecoline.get_basket_cost())
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Заказать", callback_data='order')],
                                                [InlineKeyboardButton('Отменить заказ', callback_data='cancel')]])
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=text,
                reply_markup=reply_markup
            )
    except Exception as exc:
        error(bot, update, exc)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
        )
        try:
            ecoline.clear_basket()
        except Exception as exc:
            error(bot, update, exc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    logger = init_log(debug=args.debug)
    logger.info('Starting ecoline telegram bot')

    cfg = get_config()
    ecoline = ecoline_auth(debug=args.debug)

    # Ecoline site logic variables
    order_properties = {'orderType': 'phiz',
                        'ORDER_DESCRIPTION': '',
                        'ORDER_PROP_9': 'Y',
                        'ORDER_PROP_10': 'sykt'}

    time_periods = {'CT1': '9.00-11.00',
                    'CT2': '11.00-13.00',
                    'CT3': '14.00-16.00',
                    'CT4': '15.00-17.00',
                    'CT5': '16.00-18.00',
                    'CT6': '17.00-19.00',
                    'CT7': '18.00-20.00',
                    'CT8': '19.00-20.00'}

    updater = Updater(token=cfg['telegram']['token'])
    dp = updater.dispatcher

    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help)
    message_handler = MessageHandler(Filters.text, message_handler)
    unknown_handler = MessageHandler(Filters.command, unknown)

    dp.add_handler(CallbackQueryHandler(order_handler))
    dp.add_handler(start_handler)
    dp.add_handler(help_handler)
    dp.add_handler(message_handler)
    dp.add_handler(unknown_handler)

    updater.start_polling()
    updater.idle()

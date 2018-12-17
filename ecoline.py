#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import re
import datetime
import logging
from bs4 import BeautifulSoup


class EcolineTransportException(Exception):
    """An Ecoline site transport error occured."""


class EcolineAuthException(Exception):
    """An Ecoline site auth error occurred."""


class EcolineCommonException(Exception):
    """An Ecoline site common error occured."""


class Ecoline(object):

    def __init__(self, username='', password='', debug=None):
        self.username = username
        self.password = password
        self.base_url = 'https://www.ecoline-komi.ru'
        self.cookies = self.__auth()
        self.logger = self.__init_log(debug)

    def __init_log(self, debug=None):
        if debug:
            consolelog_level = logging.DEBUG
        else:
            consolelog_level = logging.WARNING

        logger = logging.getLogger('ecoline-api')
        logger.setLevel(logging.DEBUG)

        # create console handler with a higher log level
        consolelog = logging.StreamHandler()
        consolelog.setLevel(consolelog_level)

        # create formatter and add it to the handlers
        formatter = logging.Formatter(u'%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s')
        consolelog.setFormatter(formatter)

        # add the handlers to logger
        logger.addHandler(consolelog)

        return logger

    def __auth(self):
            payload = 'USER_LOGIN={}&USER_PASSWORD={}&TYPE=AUTH&AUTH_FORM=Y'.format(self.username, self.password)
            headers = {'content-type': 'application/x-www-form-urlencoded', 'cache-control': 'no-cache'}
            try:
                auth = requests.request('POST', '{}/auth/'.format(self.base_url), data=payload, headers=headers)
            except Exception as exc:
                raise EcolineAuthException(exc)
            else:
                if 'ECOLINE_SM_SALE_UID' in auth.cookies:
                    return auth.cookies
                else:
                    raise EcolineAuthException('Wrong username or password')

    def __get_product_id(self, name=''):
        if name:
            headers = {'referer': '{}/order/1/'.format(self.base_url)}
            try:
                products = requests.request('GET', '{}/order/1/'.format(self.base_url), cookies=self.cookies, headers=headers)
            except Exception as exc:
                raise EcolineTransportException(exc)
            else:
                if products:
                    filter = u'.*\<a href=\\"\/order\/\d+\/(\d+)\/\\" title=\\"{}\\"\>{}\<\/a\>'.format(name, name)
                    product_id = re.findall(filter, products.text, re.DOTALL)
                    if product_id:
                        return product_id[0]
                    else:
                        return False
                else:
                    return False
        else:
            raise EcolineCommonException('Empty attribute "name" in __get_product_id() method')

    def __check_order_status(self, order_result):
        parser = BeautifulSoup(order_result.text, 'html.parser')
        try:
            order_status = parser.find('div', class_='alert-success').h1.text
        except Exception as exc:
            raise EcolineTransportException(exc)
        else:
            if order_status == u'Ваш заказ принят':
                order_table = parser.find('table', class_='table')
                order_property = order_table.find_all('tr')[1].find_all('td')
                if order_property[0].text == self.name and int(order_property[1].text) == self.quantity:
                    result = {'status': 'ok', 'properties': 'ok'}
                else:
                    result = {'status': 'ok', 'properties': 'error'}
            else:
                result = {'status': 'error', 'properties': 'error'}

            return result

    def check_auth(self):
        try:
            html = requests.request('GET', '{}'.format(self.base_url), cookies=self.cookies)
        except Exception as exc:
            raise EcolineAuthException(exc)
        else:
            if re.search(u'.*logout=yes.*', html.text, re.DOTALL):
                return True
            else:
                return False

    def get_bonus(self):
        try:
            profile = requests.request('GET', '{}/profile/'.format(self.base_url), cookies=self.cookies)
        except Exception as exc:
            raise EcolineTransportException(exc)

        bonus = re.search(u'Бонусы:\s(\d+).*', profile.text, re.DOTALL)
        if bonus:
            return bonus.group(1)
        else:
            return False

    def get_last_order(self):
        result = {}
        try:
            profile = requests.request('GET', '{}/profile/orders/'.format(self.base_url), cookies=self.cookies)
        except Exception as exc:
            raise EcolineTransportException(exc)

        orders_date = re.findall(u'\<td\>(\d+\.\d+\.\d+).*\</td\>', profile.text, re.DOTALL)
        if orders_date:
            days = (datetime.datetime.now() - datetime.datetime.strptime(orders_date[0], '%d.%m.%Y')).days
            result.update({'date': orders_date[0], 'diff': days})
            return result
        else:
            return False

    def get_basket(self):
        headers = {'referer': '{}/order/make.php'.format(self.base_url)}
        result = []
        try:
            html = requests.request('GET', '{}/order/make.php'.format(self.base_url), cookies=self.cookies, headers=headers)
        except Exception as exc:
            raise EcolineTransportException(exc)
        else:
            if html:
                parser = BeautifulSoup(html.text, 'html.parser')
                basket = parser.find('table', id='basket_items')
                if basket:
                    products = basket.find_all('tr', id=True)
                    for product in products:
                        id = product.attrs['id']
                        name = product.find('h2', class_='bx_ordercart_itemtitle').a.string.replace('\t', '')
                        quantity = product.find('table', class_='counter').input.attrs['value']
                        delete_link = product.find('a', string=u'Удалить').attrs['href']
                        result.append({'id': id, 'name': name, 'quantity': quantity, 'delete_link': delete_link})
                    return result
                else:
                    return False
            else:
                return False

    def get_basket_cost(self):
        headers = {'referer': '{}/order/make.php'.format(self.base_url)}
        try:
            html = requests.request('GET', '{}/order/make.php'.format(self.base_url), cookies=self.cookies, headers=headers)
        except Exception as exc:
            raise EcolineTransportException(exc)
        else:
            if html:
                parser = BeautifulSoup(html.text, 'html.parser')
                cost = parser.find('td', id='allSum_FORMATED').string
                if cost:
                    return cost
                else:
                    return False
            else:
                False

    def get_order_properties(self):
        headers = {'referer': '{}/order/make.php'.format(self.base_url)}
        result = {}
        properties = ['ORDER_PROP_1',
                      'ORDER_PROP_2',
                      'ORDER_PROP_3',
                      'ORDER_PROP_5',
                      'ORDER_PROP_8']
        try:
            html = requests.request('GET', '{}/order/make.php'.format(self.base_url), cookies=self.cookies, headers=headers)
        except Exception as exc:
            raise EcolineTransportException(exc)
        else:
            if html:
                parser = BeautifulSoup(html.text, 'html.parser')
                for item in properties:
                    result[item] = parser.find('input', attrs={'name': item}).attrs['value']
        return result

    def clear_basket(self):
        headers = {'referer': '{}/order/make.php'.format(self.base_url)}
        basket = self.get_basket()
        if basket:
            for item in basket:
                try:
                    requests.request('GET', '{}{}'.format(self.base_url, item['delete_link']), cookies=self.cookies, headers=headers)
                except Exception as exc:
                    raise EcolineTransportException(exc)
        basket = self.get_basket()
        if basket:
            return False
        else:
            return True

    def add_to_basket(self, name='', quantity=1):
        headers = {'referer': '{}/order/1/'.format(self.base_url)}
        self.name = name
        self.quantity = int(quantity)
        id = self.__get_product_id(self.name)
        if id:
            try:
                requests.request('GET', '{}/order/1/?action=ADD2BASKET&id={}&quantity={}&prop[0]=0'.format(self.base_url, id, self.quantity), cookies=self.cookies, headers=headers)
            except Exception as exc:
                raise EcolineTransportException(exc)

    def checkout(self, properties={}):
        headers = {'referer': '{}/order/make.php'.format(self.base_url)}
        basket = self.get_basket()
        if basket:
            try:
                r = requests.request('POST', '{}/order/make.php'.format(self.base_url), data=properties, cookies=self.cookies, headers=headers)
            except Exception as exc:
                raise EcolineTransportException(exc)
            else:
                self.logger.debug(u'Checkout operation request success. Request data: {0}. Reply data: [{1}] Headers: {2} Message: {3}'.format(properties,
                                                                                                                                               r.status_code,
                                                                                                                                               r.headers,
                                                                                                                                               r.text))
            try:
                order_status = self.__check_order_status(r)
            except Exception as exc:
                raise EcolineTransportException(exc)
            else:
                return order_status

    def logout(self):
        try:
            requests.request('GET', '{}/?logout=yes'.format(self.base_url), cookies=self.cookies)
        except Exception as exc:
            raise EcolineTransportException(exc)

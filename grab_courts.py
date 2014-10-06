#  -*- coding: UTF-8 -*-
import csv
import urllib2
import logging
import os.path
import re
import time
import sys
from bs4 import BeautifulSoup
 
_logger = logging.getLogger('CourtsParser')
logging.basicConfig(format='%(asctime)s - %(name)s: %(message)s', level=logging.INFO)


class classproperty(property):
 
    def __get__(self, instance, owner):
        return self.fget.__get__(None, owner)()
 
 
def retry(times, delay=None):
    """
    Tries to execute function and if Exception is raised,
    waits couple of seconds and tries to execute it again.

    :param times: how many tries will be made
    :param delay: delay in seconds between each try
    :return: wrapped function
    """
    delay = 5 if delay is None else delay
 
    def wrap(f):
        a = range(times + 1)
 
        def f_with_retry(*args, **kwargs):
            while a:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    a.pop()
                    if not a:
                        raise e
                    _logger.info('Retrying `%s` in %s sec' % (f.func_name, delay))
                    time.sleep(delay)
        return f_with_retry
    return wrap
 
 
def handle(exception_type, message=None):
    """
    Handles exception and writes message into stdout.

    :param exception_type: exception which we want to handle
    :param message: text of message that will be warned into stdout
    :return:
    """
    def wrap(f):
        def f_handled(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except exception_type, e:
                if message:
                    _logger.warn(message)
                else:
                    _logger.warn(str(e))
        return f_handled
    return wrap
 
 
class Court(object):
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'courts.csv'
    api_url = 'http://court.gov.ua/sudy/'
    search_courts_url = 'http://court.gov.ua/search_court.php'
    page_encoding = 'windows-1251'
    _court_names = None
 
    def __init__(self, **kwargs):
        if kwargs['type_id'] in self.courts_types:
            self.type_id = kwargs['type_id']
            self.type_name = self.courts_types[kwargs['type_id']]
        self.region_id = kwargs.get('region_id', None)
        self.region_name = kwargs['region_name']
        self.district_id = kwargs.get('district_id', None)
        self.district_name = kwargs.get('district_name', None)
        self.city_name = kwargs.get('city_name', None)
        self.name = None
        self.address = None
        self.schedule = None
        self.phones = None
        self.email = None
        self.url = None
        self.site = None

    def _get_court_id(self, url=None):
        if url:
            try:
                return re.search('court\.gov\.ua/(sud\d+)', url).group(1)
            except AttributeError:
                return None

    def get_court_name(self, url):
        """
        Tries to grab court name from Court.search_courts_url.
        :param url: court's page URL
        :return: string with court name or None
        """
        if not Court._court_names:
            soup = BeautifulSoup(urllib2.urlopen(self.search_courts_url).read().decode(self.page_encoding))
            Court._court_names = {self._get_court_id(a.attrs['href']): a.text for a in soup.find_all('a')}

        return Court._court_names.get(self._get_court_id(url), None)

    @property
    def csv_headers(self):
        return self.csv_row.keys()
 
    @property
    def csv_row(self):
        props = {u'Назва суду': self.name,
                 u'Тип суду': self.type_name,
                 u'Адреса': self.address,
                 u'Область': self.region_name,
                 u'Розклад': self.schedule,
                 u'Телефони': self.phones,
                 u'email': self.email,
                 u'Сторінка суду': self.url,
                 u'Сайт суду': self.site,
                 u'Район': self.district_name,
                 u'Місто': self.city_name,
                 }

        return {
            k.encode('utf-8'): re.sub('[\n\s]+', ' ', v.strip().encode('utf-8')) if v else '' for k, v in props.items()
        }
 
    def _open_csv(self, file_name):
        if not os.path.isfile(file_name):
            with open(file_name, 'a') as f:
                csv.DictWriter(f, self.csv_headers).writeheader()
        return open(file_name, 'a')
 
    def save_to_csv(self, output_file=None):
        with self._open_csv(output_file or self.output_file) as f:
            writer = csv.DictWriter(f, self.csv_headers)
            writer.writerow(self.csv_row)

    def _grab_name(self, soup):
        """
        Grabs name from court's page.
        Most of Crimean courts keep their names in a quite different way. And in place of name there is some dummy info.
        Here we detect dummy string and try to get name from <h1> tag
        """
        name = soup.select('div#main')[0].string
        # name and 'Судова влада' in name
        if name and u'\u0421\u0443\u0434\u043e\u0432\u0430 \u0432\u043b\u0430\u0434\u0430' in name:
            name = getattr(soup.find('h1'), 'string', None)
        return name

    @retry(times=3)
    def grab_data(self):
        """
        Grabs main information from court's page
        """
        if self.url:
            try:
                soup = BeautifulSoup(urllib2.urlopen(self.url).read().decode(self.page_encoding))
                try:
                    self.name = self.get_court_name(self.url) or self._grab_name(soup)
                    _logger.info('Getting data for %s' % self.name)
                    self.address = soup.select("table.menur1 td.b2")[0].text
                    self.email = soup.select("table.menur1 td.b2 a[href*=@]")[0].text
                    self.site = soup.select("table.menur1 td.b2 a[href^=http]")[0].text
                    self.schedule = soup.select('table.menur2')[0].text.strip()[0:67]
                    self.phones = soup.select("table.menur1 td.b3")[0].text
                except IndexError:
                    _logger.info('There is no any data for `%s` at %s ' % (self.name, self.url))
            except urllib2.HTTPError:
                _logger.error('No such page %s' % self.url)

 
    @classproperty
    @classmethod
    def courts_types(cls):
        raise NotImplementedError
 
    def get_init_args(self):
        raise NotImplementedError
 
    def acquire_url(self):
        raise NotImplementedError
 
 
class RegionalCourt(Court):
 
    @classproperty
    @classmethod
    def courts_types(cls):
 
        return {
            1: u'Апеляційний суд',
            3: u'Апеляційний господарський суд',
            4: u'Апеляційний адміністративний суд',
            10: u'Місцевий господарський суд',
            11: u'Окружний адміністративний суд',
        }
 
    @classmethod
    def get_init_args(cls, court_type=None, soup=None):
        """
        :return: list of dicts with basic arguments for initialization of objects
        """
        regions = soup.find('input', attrs={'value': court_type, 'name': 'court_type'}).parent.select('option')
 
        return [dict(type_id=court_type,
                     region_name=region.contents[0].strip(),
                     region_id=region.attrs['value'].strip()) for region in regions]
 
    @retry(times=3)
    @handle(exception_type=urllib2.HTTPError)
    def acquire_url(self):
        if self.type_id and self.region_id:
            self.url = urllib2.urlopen(self.api_url, 'court_type=%s&reg_id=%s' % (self.type_id, self.region_id)).url
            _logger.debug('Acquired URL for court_type=%s&reg_id=%s' % (self.type_id, self.region_id))

 
class DistrictCourt(Court):

    _js_variables = None

    @classproperty
    @classmethod
    def courts_types(cls):
 
        return {
            5: u'Районний суд',
            6: u'Міськрайонний суд',
            7: u'Міський суд',
        }

    @classmethod
    def _get_js_vars(cls, soup, cond):
        if not cls._js_variables:
            cls._js_variables = soup.find('script', language='javascript', src=False,
                                          type=False, text=re.compile('\sobl1_2\s')).text

        return [tuple(d.split('=')) for d in cls._js_variables.split('\n') if ':' in d and d.startswith(cond)]

    @classmethod
    def get_init_args(cls, court_type=None, soup=None):
        """
        :return: list of dicts with basic arguments for initialization of objects
        """
        diff = 4  # Difference between obl_{id} (in javascript variables) and court_id
        options = soup.find('input', attrs={'value': court_type, 'name': 'court_type'}).parent.select('option')
        regions = {region.attrs['value'].strip(): {'name': region.contents[0].strip(),
                                                   'districts': []} for region in options}

        for i in cls._get_js_vars(soup, 'obl%s' % (court_type - diff)):
            region_id = re.search('^obl%s_(\d+)\[' % (court_type - diff), i[0]).group(1)
            region = regions[region_id]
            district_id, district_name = i[1][2:-2].split(':')
            region['districts'].append((district_id, district_name))
 
        return [dict(type_id=court_type,
                     region_id=region_id,
                     region_name=region['name'],
                     district_id=district[0],
                     district_name=district[1])
                for region_id, region in regions.items() for district in region['districts']]
 
    @retry(times=3)
    @handle(exception_type=urllib2.HTTPError)
    def acquire_url(self):
        if self.type_id and self.district_id:
            self.url = urllib2.urlopen(self.api_url, 'court_type=%s&reg_id=%s' % (self.type_id, self.district_id)).url
            _logger.debug('Acquired URL for court_type=%s&reg_id=%s' % (self.type_id, self.district_id))

 
class CityDistrictCourt(DistrictCourt):
    @classproperty
    @classmethod
    def courts_types(cls):

        return {
            8: u'Районний у місті суд',
        }

    @classmethod
    def get_init_args(cls, court_type=None, soup=None):
        """
        :return: list of dicts with basic arguments for initialization of objects
        """
        options = soup.find('input', attrs={'value': court_type, 'name': 'court_type'}).parent.select('option')
        regions = {region.attrs['value'].strip(): region.contents[0].strip() for region in options}
        cities = {}

        # select city info and add to dict: <city_id> => <name>, <region_name>, <list_of_districts>
        for i in cls._get_js_vars(soup, 'mis1'):
            region_id = re.search('^mis1_(\d+)\[', i[0]).group(1)
            city_id, city_name = i[1][2:-2].split(':')
            cities[city_id] = {
                'name': city_name,
                'region_name': regions[region_id],
                'districts': [],
            }

        # select districts and add to city
        for i in cls._get_js_vars(soup, 'raj1'):
            city_id = re.search('^raj1_(\d+)\[', i[0]).group(1)
            district_id, district_name = i[1][2:-2].split(':')
            cities[city_id]['districts'].append((district_id, district_name))

        return [dict(type_id=court_type,
                     region_name=city['region_name'],
                     district_id=district[0],
                     district_name=district[1],
                     city_name=city['name'])
                for city_id, city in cities.items() for district in city['districts']]

 
class CourtFactory(object):
 
    def __init__(self):
        self.soup = None
 
    def __enter__(self):
        return self
 
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
 
    def get_courts_with_base_info(self, court_cls):
        courts = []
 
        if not self.soup:
            source = urllib2.urlopen(court_cls.api_url).read().decode(court_cls.page_encoding)
            self.soup = BeautifulSoup(source)
            del source
 
        for court_type in court_cls.courts_types:
            for kwargs in court_cls.get_init_args(court_type=court_type, soup=self.soup):
                courts.append(court_cls(**kwargs))
 
        return courts
 
    def close(self):
        self.soup = None
 
 
def save_courts_to_csv(courts):
    if hasattr(courts, '__iter__'):
        for i in xrange(len(courts)):
            courts[i].acquire_url()
            courts[i].grab_data()
            courts[i].save_to_csv()
            courts[i] = None


def main():
    with CourtFactory() as factory:
        for cls in [CityDistrictCourt, RegionalCourt, DistrictCourt]:
            courts = factory.get_courts_with_base_info(cls)
            save_courts_to_csv(courts)
            del courts

    return 0

if __name__ == '__main__':
    sys.exit(main())

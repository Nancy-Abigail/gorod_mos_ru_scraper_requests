from lov import dates, districts, tabs, months
from lxml import html
from orm import Author, Object, Report
from orm import new_session
import threading
import re
import requests


def log_error(type: str, **kwargs):
    # Fill error log row
    row = '{'
    row += f'"type":"{type}"'
    for key, value in kwargs.items():
        row += f',"{key}":"{value}"'
    row += '}\n'

    # Add row to log file
    with open('error_log.txt', 'a+') as file:
        file.write(row)


# noinspection PyBroadException
def create_object(link: str):
    request = requests.get(link)
    html_page = html.fromstring(request.content)

    if request.status_code != 404:
        try:
            # Get script with object info
            script_text = ''
            scripts = html_page.xpath("//script[@type='text/javascript']")
            for script in scripts:
                if script.text_content()[0:15] == ';FE.manageEvent':
                    script_text = script.text_content()

            # Fill object
            object = Object()
            object.id = int(re.findall('"objectId":[0-9]+', script_text)[0][11:])
            object.type = html_page.xpath('//div[@class="col_3c"]/div')[0].text_content()
            object.address = re.findall('"address": "[^"]*"', script_text)[0][12:-1]
            object.lat = re.findall('"objectLat": [0-9.]+,', script_text)[0][12:-1]
            object.lon = re.findall('"objectLon": [0-9.]+,', script_text)[0][12:-1]

            # Push object to DB
            session = new_session()
            object.push(session)
            session.commit()
            session.close()
        except Exception as e:
            print(f'Error at create_object: "{link}". {e}')
            log_error(type='create_object', link=link)
    else:
        print(f'Error at create_object: "{link}". Error 404, object not found')


def create_author(element):
    # Check if user id is valid
    id_search_result = re.findall('user_id=[0-9]+', element.get('href'))
    if not id_search_result:
        return 0

    # Create and fill author
    author = Author()
    author.id = int(id_search_result[0][8:])
    author.full_name = element.text_content()

    result = author.id

    # Push author to DB
    session = new_session()
    author.push(session)
    session.commit()
    session.close()

    return result


# noinspection PyBroadException
def create_report(element: html.HtmlElement, object_id: int):
    # Check that req_num is correct
    req_num = element.get('reqnum')
    if req_num == '':
        return

    # Create author
    author_element = element.xpath('.//div[contains(@class,"m-name")]/a')[0]
    author_id = create_author(author_element)

    # Create and fill report
    report = Report()
    report.id = int(req_num)
    report.object_id = object_id
    report.author_id = author_id

    # These variables will be filled later
    report.theme = ''
    report.date = ''
    report.text = ''
    report.image_links = ''

    # Get and fill theme
    try:
        report.theme = element.xpath('.//div[@class="themeText bold"]')[0].text_content()
    except Exception:
        pass

    # Get and fill text
    try:
        report.text = element.xpath('.//div[@class="messageText"]/p')[0].text_content()
    except Exception:
        pass

    # Get and fill report date
    try:
        date_row = element.xpath('.//div[@class="m-date"]')[0].text_content()
        day = re.findall(' [0-9]{2} ', date_row)[0][1:-1]
        month_text = re.findall('Января|Февраля|Марта|Апреля|Мая|Июня|Июля|Августа|Сентября|Октября|Ноября|Декабря',
                                date_row)[0]
        month = months[month_text]
        year = re.findall(' [0-9]{4} ', date_row)[0][1:-1]
        time = re.findall(' [0-9]{2}:[0-9]{2},', date_row)[0][1:-1]

        report.date = f'{year}-{month}-{day} {time}'

    except Exception:
        pass

    # Get first image
    try:
        report.image_links += element.xpath('.//div[@class="messageText"]/div[@class="img-mes"]'
                                            '/div[@class="img-mes-bg yug"]')[0].get('original')
    except Exception:
        pass

    # Get other images
    try:
        add_images = element.xpath('.//div[@class="messageText"]/div[@class="g-box"]/div')
        for image in add_images:
            report.image_links += ';' + image.get('original')
    except Exception:
        pass

    # Push report to DB
    session = new_session()
    report.push(session)
    session.commit()
    session.close()


def read_page(html_page: html.HtmlElement, zone, district, tab, year, month, page):

    try:
        # Get all elements
        elements = html_page.xpath('//div[@class="message-content ctrl-enter-ban"]/div')

        # Objects and reports are represented as flat list. We need to save object before reading a report.
        object_id = ''

        # Iterate through all elements
        for element in elements:

            # If element is an object:
            if element.get('class') == 'headerCategory':
                # Get object link and ID
                object_link = 'https://gorod.mos.ru/index.php' + element.xpath('./div/a')[0].get('href')
                object_id = int(re.findall('objects&id=[0-9]+', object_link)[0][11:])

                # Call create object
                if not Object.already_exist(object_id):
                    create_object(object_link)

            # If element is a report:
            else:
                create_report(element, object_id)
    except Exception as e:
        print(f'Error at zone={zone}, district={district}, year={year}, month={month}, page=1: {e}')
        log_error(type='read_page', zone=zone, district=district, tab=tab, year=year, month=month, page=page)


def count_pages(html_page: html.HtmlElement) -> int:
    max_page = 0
    # noinspection PyBroadException
    try:
        paginator = html_page.xpath('//div[@class="pagination"]')[0]
        page_elements = paginator.xpath('./a')
        for page_element in page_elements:
            page_number = int(page_element.get('data-page'))
            if page_number > max_page:
                max_page = page_number
    except Exception:
        pass

    return max_page


def read_all_pages(zone, district, tab, year, month):
    try:
        # Get first page
        request = requests.get('https://gorod.mos.ru/index.php?show=problem'
                               f'&tab={tab}&zone={zone}&district={district}'
                               f'&m={month}&y={year}')
        html_page = html.fromstring(request.content)

        # Read first page
        read_page(html_page, zone, district, tab, year, month, 1)

        # Check if there are other pages and read them
        pages_amount = count_pages(html_page)
        for page in range(2, pages_amount + 1):
            request = requests.get(
                'https://gorod.mos.ru/index.php?show=problem'
                f'&tab={tab}&zone={zone}&district={district}'
                f'&m={month}&y={year}&page={page}'
            )
            html_page = html.fromstring(request.content)
            read_page(html_page, zone, district, tab, year, month, page)
    except Exception as e:
        print(f'Error at zone={zone}, district={district}, year={year}, month={month}: {e}')
        log_error(type='read_all_pages', zone=zone, district=district, tab=tab, year=year, month=month)


def read_all_dates(zone, district, tab):
    try:
        for date in dates:
            read_all_pages(zone, district, tab, date['year'], date['month'])
    except Exception as e:
        print(f'Error at zone={zone}, district={district}, all dates: {e}')
        log_error(type='read_all_dates', zone=zone, district=district, tab=tab)


def run_district_group(district_group, tab):
    for district in district_group:
        read_all_dates(district['zone'], district['district'], tab)


def run_all_districts():
    thread_amount = 10  # Number of parallel threads (was done to increase parser's speed)
    district_groups = []
    for i in range(thread_amount):
        district_groups.append([])

    for i in range(len(districts)):
        district_groups[i % thread_amount].append(districts[i])

    for district_group in district_groups:
        for tab in tabs:
            threading.Thread(target=run_district_group, args=(district_group, tab)).start()


def run_all_districts_alt():
    for district in districts:
        for tab in tabs:
            threading.Thread(target=read_all_dates, args=(district['zone'], district['district'], tab)).start()


def main():
    # Dear Lord, save us all
    run_all_districts_alt()


if __name__ == '__main__':
    main()

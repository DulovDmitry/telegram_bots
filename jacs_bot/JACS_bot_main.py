import logging
import asyncio
import os
import time
import json

from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.exceptions import AiogramError
from bs4 import BeautifulSoup as bs
from playwright.async_api import async_playwright, Playwright
from pathlib import Path

from db import BotDataBase
from my_config import API_TOKEN
from my_config import MY_TG_ID
from my_config import DUMP_PATH

avaliable_commands = ["/start", "/help", "/stop"]
JACS_ASAP_URL = "https://pubs.acs.org/toc/jacsat/0/0"
CHANNEL_ID = -1002569257994

article_types = [", Articles ASAP  (Communication)", ", Articles ASAP  (Perspective)", ", Articles ASAP  (Article)"]

logging.basicConfig(level=logging.INFO) #,
#		format="%(asctime)s - [%(levelname)s] - %(app)s - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

database = BotDataBase()


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` command
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    if not (database.user_is_already_added(user_id)):
    	database.insert_user({ "telegram_id" : user_id,	"telegram_name" : user_name })

    print(database.get_all_user_ids())
    print(user_id)
    print(user_name)
    await bot.send_message(user_id, "Hi there!\n\nI’m the JASC Bot, your helper for staying updated with the latest research. I automatically send new ASAP articles from the Journal of the American Chemical Society (JACS) to this Telegram channel: JACS Articles.\n\nIf you want the newest publications delivered straight to you, just subscribe!")
    await bot.send_message(user_id, "Send /help to see the list of avaliable commands")


@dp.message(Command("help"))
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/help` command
    """
    await bot.send_message(message.from_user.id, "The list of avaliable commands:\n" + "\n".join(avaliable_commands))


@dp.message(Command("stop"))
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/stop' command
    """
    database.exclude_user(message.from_user.id)
    await bot.send_message(message.from_user.id, "Bye!")


@dp.message()
async def unrecognized_message_handler(message: types.Message):
	try:
		await message.send_copy(chat_id=MY_TG_ID)
	except TypeError:
		await message.answer("Nice try!")

	await bot.send_message(MY_TG_ID, "Unrecognized message from " + message.from_user.full_name)
	await bot.send_message(message.from_user.id, "Don't understand!\nSend /help")


async def sceduled_func(sleep_for: int):
	"""
	Run function every sleep_for seconds
	"""
	while True:
		await asyncio.sleep(sleep_for)

		success_flag = False
		i = 1
		while i<=3 and not success_flag:
			try:
				print(datetime.now(), f"Request attempt #{i}")
				logging.info(f"Request attempt #{i}")
				await retrieve_articles_from_website()
			except Exception as e:
				print(datetime.now())
				print(e)
			except:
				print("Unrecognized error")
			else:
				success_flag = True
				continue
			i+=1
			await asyncio.sleep(30)


async def retrieve_articles_from_website():
	"""
	Send request to the website and parse the response
	"""
	async with async_playwright() as playwright:
		browser = await playwright.chromium.launch(headless=False)
		context = await browser.new_context(
		    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
		    viewport={"width": 1920, "height": 1080}
		)

		await context.add_cookies(json.loads(Path("jacs_cookies.json").read_text()))
		page = await context.new_page()
		await page.goto(JACS_ASAP_URL, timeout=0)
		time.sleep(10)

		html_page = await page.content()

		soup = bs(html_page, "html.parser")
		articles_html = soup.findAll('div', class_='issue-item clearfix')

		if len(articles_html) == 0:
			print(datetime.now(), "Some problem with page loading")
			logging.info("Some problem with page loading")
			await bot.send_message(MY_TG_ID, "Some problem with page loading")

			outfile = open(DUMP_PATH, 'w')
			outfile.write(html_page)
			outfile.close()

			raise Exception("Some problem with page loading")
#			return

		logging.info("Page has been loaded and parsed")
		await bot.send_message(MY_TG_ID, "Page has been loaded and parsed")

		cookies = await context.cookies()
		Path("jacs_cookies.json").write_text(json.dumps(cookies))
		await page.close()

		await fill_articles_table_in_database(articles_html)
		await send_new_article_to_users()


async def fill_articles_table_in_database(articles_html):
	"""
	Fill database with new articles
	"""
	for article in articles_html:
		if article.find('span', class_="issue-item_type").text in '\t'.join(article_types):
			article_name = article.find('h5', class_='issue-item_title').text
			authors_list_html = article.find_all('span', class_='hlFld-ContribAuthor')
			article_authors = []

			for author in authors_list_html:
				article_authors.append(author.text)

			article_abstract = article.find('span', class_='hlFld-Abstract').text
			article_link = "https://pubs.acs.org" + article.find('a').get('href')

			ga_sublink = article.find('img', class_='lazy').get('data-src')
			if ga_sublink == None:
				ga_sublink = article.find('img', class_='lazy').get('src')
			article_graphical_abstract_link = "https://pubs.acs.org" + ga_sublink

			if not (database.article_is_already_added(article_link)):
				database.insert_article({
					"name" : article_name,
					"authors" : ", ".join(article_authors),
					"abstract" : article_abstract,
					"link" : article_link,
					"image_link" : article_graphical_abstract_link,
					"was_sent" : False
					})


async def send_new_article_to_users():
	"""
	Send all unsent articles to all users
	"""
	unsent_articles = database.get_unsent_articles()
	number_of_new_articles = len(unsent_articles)

	if number_of_new_articles == 0:
		print(datetime.now(), "There is no new articles")
		logging.info("There is no new articles")
		return

	logging.info(f"There is {number_of_new_articles} new article(s)")

	for article in unsent_articles:
		# Create message to be sent
		message = "<b>" + article[0] + "</b>\n\n"		# add title
		message += "<i>" + article[1] + "</i>\n\n"		# add authors
		message += "<u>Abstract:</u> " + article[2] + "\n\n"    # add abstract
		message += "<a href=\"" + article[3] + "\">❯ Link to the article</a>"	# add link to the webpage

		# Send message to the channel
		# The message consist of the above formed text and Graphical abstract
		# If the text is too long (more than 1023 symbols), then the message will be sent without picture
		try:
			await bot.send_photo(chat_id=CHANNEL_ID, photo=article[4], caption=message, parse_mode='html')
		except:
			try:
				await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='html')
			except AiogramError as e:
				print(datetime.now(), "[error] Aiogram exception. Message has not been sent. The article was marked as \"was send\"")
				print(datetime.now(), e)
				logging.error("Aiogram exception. Message has not been sent. The article was marked as \"was send\"")
				number_of_new_articles -= 1

		database.article_was_sent(article[3])

	print(datetime.now(), f"All new articles ({number_of_new_articles}) has been sent") # to all users ({number_of_users})")
	logging.info(f"All new articles ({number_of_new_articles}) has been sent") # to all users ({number_of_users})")


async def main():
	logging.info("Bot has been started")

	loop = asyncio.get_event_loop()
	loop.create_task(sceduled_func(21600)) # make request every 24 hours = 86400
	await dp.start_polling(bot)


if __name__ == '__main__':
	asyncio.run(main())


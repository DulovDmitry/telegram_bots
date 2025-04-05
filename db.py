import os
from typing import Dict, List, Tuple
import sqlite3

from my_config import DB_PATH

class BotDataBase(object):

	def __init__(self):
		self.conn = sqlite3.connect(DB_PATH)
		self.cursor = self.conn.cursor()

	def insert_user(self, column_values: Dict):
		table = "users"
		columns = ', '.join( column_values.keys() )
		values = [tuple(column_values.values())]
		placeholders = ", ".join( "?" * len(column_values.keys()) )
		self.cursor.executemany(
			f"INSERT INTO {table} "
			f"({columns}) "
			f"VALUES ({placeholders})",
			values)
		self.conn.commit()

	def exclude_user(self, user_id: int):
		self.cursor.execute("DELETE FROM users WHERE telegram_id = '%s'" % user_id)
		self.conn.commit()

	def insert_article(self, column_values: Dict):
		table = "articles"
		columns = ', '.join( column_values.keys() )
		values = [tuple(column_values.values())]
		placeholders = ", ".join( "?" * len(column_values.keys()) )
		self.cursor.executemany(
			f"INSERT INTO {table} "
			f"({columns}) "
			f"VALUES ({placeholders})",
			values)
		self.conn.commit()

	def user_is_already_added(self, telegram_id: int):
		id_list = self.get_all_user_ids()
		if (telegram_id in id_list):
			return True
		else:
			return False

	def article_is_already_added(self, article_link: str):
		link_list = self.get_all_article_links()
		if (article_link in link_list):
			return True
		else:
			return False

	def get_all_user_ids(self):
		self.cursor.execute("SELECT * FROM 'users'")
		all_rows = self.cursor.fetchall()
		id_list = []
		for row in all_rows:
			id_list.append(row[0])
		return id_list

	def get_all_article_links(self):
		self.cursor.execute("SELECT * FROM 'articles'")
		all_rows = self.cursor.fetchall()
		link_list = []
		for row in all_rows:
			link_list.append(row[3])
		return link_list

	def get_unsent_articles(self):
		self.cursor.execute("SELECT * FROM 'articles'")
		all_articles = self.cursor.fetchall()
		unsent_articles = []
		for article in all_articles:
			if (article[5] == 0):
				unsent_articles.append(article)
		return unsent_articles

	def get_image_link(self, article_link):
		self.cursor.execute("SELECT image_link FROM articles WHERE link = '%s'" % article_link)
		image_link = self.cursor.fetchall()
		return image_link[0]

	def article_was_sent(self, link: str):
		self.cursor.execute("UPDATE articles SET was_sent = 1 WHERE link = '%s'" % link)
		self.conn.commit()
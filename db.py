import datetime
import sqlite3
import os
import datetime
import time

import pandas as pd


class Database:

    def __init__(self, data_path: str):
        self.connection = sqlite3.connect(os.path.join(data_path, "database.db"))
        self._create_tables()

    def _create_tables(self):
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS market_sold ("
            "listing_id INTEGER PRIMARY KEY,"
            "item_id INTEGER,"
            "off_stat TEXT,"
            "off_stat_amount REAL,"
            "price INTEGER,"
            "listing_time INTEGER,"
            "listing_duration_seconds INTEGER"
            ")"
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS market_listings ("
            "listing_id INTEGER PRIMARY KEY,"
            "item_id INTEGER,"
            "off_stat TEXT,"
            "off_stat_amount REAL,"
            "price INTEGER,"
            "listing_time INTEGER"
            ")"
        )

    def insert_market_listing(self, listing_id: int, item_id: int, off_stat: str, off_stat_amount: float, price: int,
                              listing_time: datetime.datetime):
        cursor = self.connection.cursor()
        cursor.execute(f"INSERT OR IGNORE INTO market_listings VALUES("
                       f"{listing_id},"
                       f"{item_id},"
                       f"'{off_stat}',"
                       f"{off_stat_amount},"
                       f"{price},"
                       f"{int(listing_time.timestamp())}"
                       f")")
        cursor.execute(f"DELETE FROM market_listings WHERE listing_time < {int(datetime.datetime.utcnow().timestamp()) - 3600*24}")
        self.connection.commit()

    def get_last_listing_id(self) -> int:
        cursor = self.connection.cursor()
        data = cursor.execute("SELECT listing_id FROM market_listings ORDER BY listing_id DESC LIMIT 1").fetchone()
        if data and len(data) > 0:
            return data[0]
        else:
            return 0

    def get_listings(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * from market_listings", self.connection)

    def mark_sold(self, listing_id: int, sold_time: int):
        cursor = self.connection.cursor()
        data = cursor.execute(f"SELECT * FROM market_listings WHERE listing_id = {listing_id}").fetchall()
        if len(data) == 1:
            cursor.execute(f"INSERT OR IGNORE INTO market_sold VALUES("
                           f"{data[0][0]},"
                           f"{data[0][1]},"
                           f"'{data[0][2]}',"
                           f"{data[0][3]},"
                           f"{data[0][4]},"
                           f"{data[0][5]},"
                           f"{sold_time - data[0][5]}"
                           f")")
        cursor.execute(f"DELETE FROM market_listings WHERE listing_id = {listing_id}")
        self.connection.commit()
        pass

    def get_sold_prices(self, item_id: int, stat_name: str, stat_amount: float, stat_amount_range: float = 0.2) -> pd.DataFrame:
        cursor = self.connection.cursor()
        df = pd.read_sql_query(f"SELECT * FROM market_sold "
                              f"WHERE item_id = {item_id} "
                              f"AND off_stat = '{stat_name}' "
                              f"AND off_stat_amount > {stat_amount * (1 - stat_amount_range)} "
                              f"AND off_stat_amount < {stat_amount * (1 + stat_amount_range)}", self.connection)
        return df

    def delete_all_market_listings(self):
        cursor = self.connection.cursor()
        cursor.execute(f"DELETE FROM market_listings")
        self.connection.commit()
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from db import Database
import logging as log


def get_item_from_texts(texts) -> (str, int):
    index = 2
    item = texts[index]
    if '"' in item:
        log.info(f"\" in \"{item}\"")
        for next_item in texts[3:]:
            index += 1
            item += f" {next_item}"
            if '"' in next_item:
                break
    else:
        log.info(f"\" not in \"{item}\"")
    item = item.replace('"', "")
    return item, index


class TelegramBot:
    def __init__(self, config, market, items, fleet_listener, db: Database):
        self._config = config
        self._token = config["token"]
        self._chat_id = config["chat_id"]
        self._bot = Bot(self._token, parse_mode="HTML")
        self._dp = Dispatcher(bot=self._bot)
        self._market = market
        self._items = items
        self._fleet_listener = fleet_listener
        self._db = db
        self._setup_message_handlers()

    def _setup_message_handlers(self):
        handlers = [
            (self._start_command_callback, ['start']),
            (self._market_command_callback, ['market']),
            (self._trader_command_callback, ['trader']),
            (self._fleet_command_callback, ['fleet']),
            (self._price_command_callback, ['price']),
            (self._echo_handler, None)
        ]

        for handler in handlers:
            self._dp.register_message_handler(handler[0], commands=handler[1])

    async def _trader_command_callback(self, message: Message) -> None:
        try:
            texts = message.text.split(" ")

            if len(texts) >= 2:
                command = texts[1]
            else:
                command = None

            reply = ""
            item = ""
            stats = []
            fail = False
            all_stats = self._market.get_stat_keys()

            if command == "add":
                if len(texts) >= 3:
                    item, index = get_item_from_texts(texts)
                    design_id = self._items.get_design_id_by_name(item)
                    if design_id is None:
                        fail = True
                        reply = f"Unknown item name {item}. "
                else:
                    fail = True

                if not fail:
                    await self._market.add_trader_item(item)
                    reply = "Added successfully."
            elif command == "remove":
                item, _ = get_item_from_texts(texts)
                if not self._market.remove_trader_item(item):
                    fail = True
                    reply = "No such item."
                else:
                    reply = "Removed successfully."
            else:
                trader_list = self._market.list_trader_items()
                reply = f"Current trader items:"
                for item in trader_list:
                    reply += f"\n{self._items.get_name_by_design_id(item)}"
                fail = True

            if fail:
                await message.answer(f"{reply}\nUsage:\n/trader add \"King Husky\"\n/trader remove \"King Husky\"")
            else:
                await message.answer(f"{reply}")
        except Exception as e:
            log.info(f"EXCEPTION {e}")

    async def _market_command_callback(self, message: Message) -> None:
        try:
            texts = message.text.split(" ")

            if len(texts) >= 2:
                command = texts[1]
            else:
                command = None

            reply = ""
            item = ""
            stats = []
            fail = False
            all_stats = self._market.get_stat_keys()

            if command == "add":
                if len(texts) >= 3:
                    item, index = get_item_from_texts(texts)
                    design_id = self._items.get_design_id_by_name(item)
                    if design_id is None:
                        fail = True
                        reply = f"Unknown item name {item}. "
                    else:
                        stats = texts[index + 1:]

                        if self._items.item_can_have_substats(design_id):
                            if len(stats) > 0:
                                for stat in stats:
                                    if stat not in all_stats:
                                        fail = True
                                        reply = f"Stat not in {stats}."
                            else:
                                stats = all_stats
                        else:
                            stats = []
                else:
                    fail = True

                if not fail:
                    await self._market.add_interest_items(item, stats)
                    reply = "Added successfully."
            elif command == "remove":
                item, _ = get_item_from_texts(texts)
                if not self._market.remove_interest_items(item):
                    fail = True
                    reply = "No such item."
                else:
                    reply = "Removed successfully."
            else:
                market_list = self._market.list()
                reply = f"Current items:"
                for item in market_list:
                    reply += f"\n{item}: \"{self._items.get_name_by_design_id(item)}\": {' '.join(market_list[item]['stats'])}"
                fail = True

            if fail:
                await message.answer(f"{reply}\nUsage:\n/market add \"King Husky\" {' '.join(all_stats)}\n/market remove \"King Husky\"")
            else:
                await message.answer(f"{reply}")
        except Exception as e:
            log.info(f"EXCEPTION {e}")

    async def _fleet_command_callback(self, message: Message) -> None:
        texts = message.text.split(" ")
        reply = "Invalid command. Usage:\n/fleet name \"Fleet name\"\n/fleet addcrew \"WPN 10\"\n/fleet removecrew \"WPN\"\n/fleet"
        if len(texts) > 1:
            command = texts[1]
            if command == "addcrew":
                items = texts[2:]
                if len(items) != 2:
                    pass
                else:
                    stat = items[0]
                    try:
                        amount = float(items[1])
                    except:
                        amount = None
                        reply = f"{items[1]} is not a number"

                    if amount is not None:
                        all_stats = self._market.get_stat_keys()
                        if stat not in all_stats:
                            reply = f"Stat {stat} not in ({list(all_stats)})!"
                        else:
                            self._fleet_listener.add_interest_crew(stat, amount)
                            reply = f"{stat} - {amount} added."
            elif command == "removecrew":
                if len(texts) != 3:
                    pass
                else:
                    stat = texts[2]
                    all_stats = self._market.get_stat_keys()
                    if stat not in all_stats:
                        reply = f"Stat {stat} not in ({list(all_stats)})!"
                    else:
                        self._fleet_listener.remove_interest_crew(stat)
                        reply = f"{stat} removed."
            elif command == "name":
                name, index = get_item_from_texts(texts)
                success = await self._fleet_listener.set_fleet(name)
                if not success:
                    reply = f"No such fleet: {name}"
                else:
                    reply = f"Started monitoring {name}"
            else:
                reply = f"Unknown command {command}"
        else:
            texts = []
            async for text in self._fleet_listener.get_current_messages():
                texts.append(text)

            if len(texts) > 0:
                joined_texts = '\n'.join(texts)
                reply = f"Current crew matching criteria:\n{joined_texts}"
        await message.answer(f"{reply}")

    async def _price_command_callback(self, message: Message) -> None:
        texts = message.text.split(" ")
        reply = "Invalid command. Usage:\n/price King Husky 1 HP"
        name_parts = []
        stat_amount = None
        stat = ""
        if len(texts) > 2:
            for part in texts:
                if not part.isnumeric():
                    if stat_amount is None:
                        name_parts.append(part)
                    else:
                        stat = part
                else:
                    stat_amount = float(part)

            all_stats = self._market.get_stat_keys()
            if stat not in all_stats:
                reply = f"Stat {stat} not in ({list(all_stats)})!"
            else:
                name = ' '.join(name_parts[1:])
                item_id = self._items.get_design_id_by_name(name)
                df = self._db.get_sold_prices(item_id, stat, stat_amount)
                if len(df) > 0:
                    reply = f"{name} - {len(df)} samples - min {df.mean()['price']} - max {df.max()['price']} - mean {df.mean(numeric_only=True)['price']}"
                else:
                    reply = "No data"

        await message.answer(f"{reply}")


    async def _start_command_callback(self, message: Message) -> None:
        """
        This handler receive messages with `/start` command
        """
        # Most event objects have aliases for API methods that can be called in events' context
        # For example if you want to answer to incoming message you can use `message.answer(...)` alias
        # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
        # method automatically or call API method directly via
        # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
        await message.answer(f"Hello, <b>{message.from_user.full_name}!</b>")

    async def _echo_handler(self, message: types.Message) -> None:
        """
        Handler will forward received message back to the sender

        By default, message handler will handle all message types (like text, photo, sticker and etc.)
        """
        try:
            # Send copy of the received message
            await message.send_copy(chat_id=message.chat.id)
        except TypeError:
            # But not all the types is supported to be copied so need to handle it
            await message.answer("Nice try!")

    async def run(self):
        await self._dp.start_polling(self._bot)

    async def send_message(self, message: str, html=False):
        if html:
            await self._bot.send_message(self._chat_id, message, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await self._bot.send_message(self._chat_id, message, disable_web_page_preview=True)

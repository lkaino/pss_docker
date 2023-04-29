import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import logging as log

class TelegramBot:
    def __init__(self, config, market, items):
        self._config = config
        self._token = config["token"]
        self._chat_id = config["chat_id"]
        self._bot = Bot(self._token, parse_mode="HTML")
        self._dp = Dispatcher(bot=self._bot)
        self._market = market
        self._items = items
        self._setup_message_handlers()

    def _setup_message_handlers(self):
        handlers = [
            (self._start_command_callback, ['start']),
            (self._market_command_callback, ['market']),
            (self._trader_command_callback, ['trader']),
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

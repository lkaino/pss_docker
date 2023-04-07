import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message


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
            (self._echo_handler, None)
        ]

        for handler in handlers:
            self._dp.register_message_handler(handler[0], commands=handler[1])

    async def _market_command_callback(self, message: Message) -> None:
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
            for next_item in texts[3:]:
                index += 1
                item += f" {next_item}"
                if '"' in next_item:
                    break
            item = item.replace('"', "")
            return item, index

        if command == "add":
            if len(texts) >= 4:
                item, index = get_item_from_texts(texts)
                if self._items.get_design_id_by_name(item) is None:
                    fail = True
                    reply = f"Unknown item name {item}. "
                stats = texts[index + 1:]
                for stat in stats:
                    if stat not in stats:
                        fail = True
                        reply = f"Stat not in {stats}. "
                        break
            else:
                fail = True

            if not fail:
                self._market.add_interest_items(item, stats)
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

    async def send_message(self, message: str):
        await self._bot.send_message(self._chat_id, message)

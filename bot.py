import asyncio

import toml
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_storage import StateMemoryStorage
from telebot.util import quick_markup

from telegram_vip_group.config import config

bot = AsyncTeleBot(config['BOT_TOKEN'], state_storage=StateMemoryStorage())


class BotStatesGroup(StatesGroup):
    on_change_message = State()


@bot.message_handler(commands=['start', 'help'])
async def start(message):
    if message.chat.username == config['ADMIN_USERNAME']:
        await bot.send_message(
            message.chat.id,
            'Escolha uma opção:',
            reply_markup=quick_markup(
                {
                    'Alterar mensagem 1': {
                        'callback_data': 'change_message:0'
                    },
                    'Alterar mensagem 2': {
                        'callback_data': 'change_message:1'
                    },
                }
            ),
        )
    else:
        await bot.send_message(
            message.chat.id,
            config['MESSAGES'][0],
            reply_markup=quick_markup(
                {'Comprar': {'callback_data': 'purchase:0'}}
            ),
        )


@bot.callback_query_handler(func=lambda c: 'change_message' in c.data)
async def change_message(callback_query):
    index = int(callback_query.data.split(':')[-1])
    await bot.send_message(
        callback_query.message.chat.id, 'Digite a mensagem:'
    )
    await bot.set_state(
        callback_query.message.chat.id,
        BotStatesGroup.on_change_message,
        callback_query.message.chat.id,
    )
    async with bot.retrieve_data(
        callback_query.message.chat.id, callback_query.message.chat.id
    ) as data:
        data['index'] = index


@bot.message_handler(state=BotStatesGroup.on_change_message)
async def change_message_action(message):
    async with bot.retrieve_data(message.chat.id, message.chat.id) as data:
        config['MESSAGES'][data['index']] = message.text
        toml.dump(config, open('.config.toml', 'w'))
    await bot.delete_state(message.chat.id, message.chat.id)
    await bot.send_message(message.chat.id, 'Mensagem Alterada')
    await start(message)


@bot.callback_query_handler(func=lambda c: 'purchase' in c.data)
async def purchase(callback_query):
    purchase_id = int(callback_query.data.split(':')[-1])
    if purchase_id == 0:
        await bot.send_message(
            callback_query.message.chat.id,
            config['MESSAGES'][1],
            reply_markup=quick_markup(
                {'Comprar': {'callback_data': 'purchase:1'}}
            ),
        )


if __name__ == '__main__':
    bot.add_custom_filter(asyncio_filters.StateFilter(bot))
    asyncio.run(bot.polling())

import asyncio
import os
from datetime import date, datetime, timedelta
from uuid import uuid4

import mercadopago
import segno
import toml
from sqlalchemy import select
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_storage import StateMemoryStorage
from telebot.util import quick_markup

from telegram_vip_group.config import config
from telegram_vip_group.database import Session
from telegram_vip_group.models import Client, Payment, Signature

bot = AsyncTeleBot(config['BOT_TOKEN'], state_storage=StateMemoryStorage())

sdk = mercadopago.SDK(config['MERCADOPAGO_TOKEN'])


class BotStatesGroup(StatesGroup):
    on_change_message = State()


async def main():
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
            file_path = [f for f in os.listdir('.') if 'message_1' in f][0]
            if 'mp4' in file_path:
                await bot.send_video(
                    message.chat.id,
                    open(file_path, 'rb'),
                    supports_streaming=True,
                    caption=config['MESSAGES'][0],
                    reply_markup=quick_markup(
                        {'QUERO COMPRAR ✅': {'callback_data': 'purchase:0'}}
                    ),
                )
            else:
                await bot.send_photo(
                    message.chat.id,
                    open(file_path, 'rb'),
                    caption=config['MESSAGES'][0],
                    reply_markup=quick_markup(
                        {'QUERO COMPRAR ✅': {'callback_data': 'purchase:0'}}
                    ),
                )

    @bot.callback_query_handler(func=lambda c: 'change_message' in c.data)
    async def change_message(callback_query):
        index = int(callback_query.data.split(':')[-1])
        try:
            os.remove(
                [f for f in os.listdir('.') if f'message_{index + 1}' in f][0]
            )
        except IndexError:
            pass
        await bot.set_state(
            callback_query.message.chat.id,
            BotStatesGroup.on_change_message,
            callback_query.message.chat.id,
        )
        async with bot.retrieve_data(
            callback_query.message.chat.id, callback_query.message.chat.id
        ) as data:
            data['index'] = index
        await bot.send_message(
            callback_query.message.chat.id, 'Digite a mensagem:'
        )

    @bot.message_handler(
        state=BotStatesGroup.on_change_message,
        content_types=['photo', 'video'],
    )
    async def on_change_message(message):
        async with bot.retrieve_data(message.chat.id, message.chat.id) as data:
            if message.photo:
                media = message.photo[-1]
            else:
                media = message.video
            file_info = await bot.get_file(media.file_id)
            downloaded_file = await bot.download_file(file_info.file_path)
            file_extension = file_info.file_path.split('.')[-1]
            with open(
                f'message_{data["index"] + 1}.{file_extension}', 'wb'
            ) as file:
                file.write(downloaded_file)
            config['MESSAGES'][data['index']] = message.caption
            toml.dump(config, open('.config.toml', 'w'))
        await bot.delete_state(message.chat.id, message.chat.id)
        await bot.send_message(message.chat.id, 'Mensagem Alterada')
        await start(message)

    @bot.callback_query_handler(func=lambda c: 'purchase' in c.data)
    async def purchase(callback_query):
        index = int(callback_query.data.split(':')[-1])
        # amount = 9.90 if index == 0 else 15.90
        amount = 0.01
        payment_data = {
            'transaction_amount': amount,
            'payment_method_id': 'pix',
            'payer': {
                'email': config['ADMIN_EMAIL'],
            },
        }
        response = sdk.payment().create(payment_data)['response']
        qr_code = response['point_of_interaction']['transaction_data'][
            'qr_code'
        ]
        qr_image = segno.make_qr(qr_code)
        qrcode_image_path = f'{uuid4()}.png'
        qr_image.save(qrcode_image_path, scale=5)
        await bot.send_photo(
            callback_query.message.chat.id, open(qrcode_image_path, 'rb')
        )
        await bot.send_message(
            callback_query.message.chat.id, 'Chave Pix abaixo:'
        )
        await bot.send_message(callback_query.message.chat.id, qr_code)
        os.remove(qrcode_image_path)
        with Session() as session:
            payment = Payment(
                payment_id=response['id'],
                user_id=str(callback_query.message.chat.id),
                chat_index=index,
            )
            session.add(payment)
            session.commit()

    bot.add_custom_filter(asyncio_filters.StateFilter(bot))

    last_update_id = 0

    while True:
        updates = await bot.get_updates(
            offset=(last_update_id + 1), timeout=20
        )
        try:
            last_update_id = updates[-1].update_id
        except IndexError:
            pass
        await bot.process_new_updates(updates)
        with Session() as session:
            for payment in session.scalars(select(Payment)).all():
                response = sdk.payment().get(payment.payment_id)['response']
                if response['status'] == 'approved':
                    invite = await bot.create_chat_invite_link(
                        config['CHATS'][payment.chat_index], member_limit=1
                    )
                    await bot.send_message(
                        payment.user_id,
                        'Pagamento realizado! Esperamos que goste',
                        reply_markup=quick_markup(
                            {'Entrar no grupo': {'url': invite.invite_link}}
                        ),
                    )
                    if payment.chat_index == 0:
                        client = Client(user_id=payment.user_id)
                        session.add(client)
                        session.commit()
                        file_path = [
                            f for f in os.listdir('.') if 'message_2' in f
                        ][0]
                        if 'mp4' in file_path:
                            await bot.send_video(
                                payment.user_id,
                                open(file_path, 'rb'),
                                supports_streaming=True,
                                caption=config['MESSAGES'][1],
                                reply_markup=quick_markup(
                                    {
                                        'QUERO COMPRAR ✅': {
                                            'callback_data': 'purchase:1'
                                        }
                                    }
                                ),
                            )
                        else:
                            await bot.send_photo(
                                payment.user_id,
                                open(file_path, 'rb'),
                                caption=config['MESSAGES'][1],
                                reply_markup=quick_markup(
                                    {
                                        'QUERO COMPRAR ✅': {
                                            'callback_data': 'purchase:1'
                                        }
                                    }
                                ),
                            )
                    else:
                        signature = Signature(
                            chat_id=str(config['CHATS'][payment.chat_index]),
                            user_id=payment.user_id,
                        )
                        session.add(signature)
                        session.commit()
                    session.delete(payment)
                    session.commit()
                if datetime.now() - payment.payment_datetime > timedelta(
                    minutes=30
                ):
                    await bot.send_message(
                        payment.user_id, 'Pagamento não finalizado'
                    )
                    session.delete(payment)
                    session.commit()
            query = select(Signature).where(Signature.end_date < date.today())
            signatures = session.scalars(query).all()
            for signature in signatures:
                await bot.kick_chat_member(
                    chat_id=signature.chat_id,
                    user_id=signature.user_id,
                )
                session.delete(signature)
                session.commit()


if __name__ == '__main__':
    asyncio.run(main())

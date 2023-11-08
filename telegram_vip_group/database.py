from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from telegram_vip_group.config import config

db = create_engine(config['DATABASE_URI'])
Session = sessionmaker(db)

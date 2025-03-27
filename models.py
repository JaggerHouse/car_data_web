from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    company_name = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    subscription_status = Column(String(20), default='free')  # free, premium
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    last_used_ip = Column(String(45), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 创建SQLite数据库连接
DATABASE_URL = 'sqlite:///car_data.db'
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})

# 创建新的数据库表（如果不存在）
Base.metadata.create_all(engine)

# 创建会话工厂
Session = sessionmaker(bind=engine)

def get_db_session():
    import time
    max_retries = 3
    retry_delay = 1
    for attempt in range(max_retries):
        try:
            return Session()
        except Exception as e:
            if 'locked' in str(e).lower() or 'access' in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"数据库文件被锁定，无法访问。请检查是否有其他进程正在使用数据库文件。原始错误: {str(e)}")
            else:
                raise e
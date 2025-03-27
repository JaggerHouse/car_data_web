import stripe
import streamlit as st
import os
import logging
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

def init_stripe():
    logging.info("Initializing Stripe configuration")
    return {
        "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY"),
        "secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET")
    }

# 用户数据持久化
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load users: {e}")
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        logging.info("Users data saved successfully")
    except Exception as e:
        logging.error(f"Failed to save users: {e}")

def create_checkout_session(price_id: str, user_email: str):
    try:
        logging.info(f"Creating checkout session for {user_email} with price_id: {price_id}")
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'alipay', 'wechat_pay'],
            payment_method_options={
                'wechat_pay': {
                    'client': 'web'
                }
            },
            line_items=[{
                'price_data': {
                    'currency': 'cny',
                    'unit_amount': 29900,  # 299元，单位为分
                    'product_data': {
                        'name': '高级版订阅（1个月）',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url="https://xiaomaoassistant.streamlit.app/?success=true",
            cancel_url="https://xiaomaoassistant.streamlit.app/?canceled=true",
            customer_email=user_email,
        )
        logging.info(f"Checkout session created: {checkout_session.url}")
        return checkout_session
    except Exception as e:
        logging.error(f"Failed to create checkout session: {str(e)}")
        st.error(f"创建支付会话失败: {str(e)}")
        return None


def handle_subscription_status(user_email: str) -> str:
    users = load_users()
    query_params = st.query_params
    if "success" in query_params and query_params["success"] == "true":
        if user_email in users:
            users[user_email]['subscription_status'] = 'premium'
            users[user_email]['subscription_expiry'] = (datetime.now() + timedelta(days=30)).isoformat()
            save_users(users)
            logging.info(f"User {user_email} upgraded to premium, expiry: {users[user_email]['subscription_expiry']}")
            return "premium"

    if user_email in users and users[user_email]['subscription_status'] == 'premium':
        expiry_date = datetime.fromisoformat(users[user_email]['subscription_expiry'])
        if datetime.now() < expiry_date:
            return "premium"
        else:
            users[user_email]['subscription_status'] = 'free'
            users[user_email]['subscription_expiry'] = None
            save_users(users)
            logging.info(f"User {user_email} subscription expired")
    return "free"


def display_subscription_plans():
    logging.info("Displaying subscription plans")
    plans = {
        "premium": {
            "name": "高级版",
            "price": 299,
            "price_id": os.getenv("STRIPE_PREMIUM_PRICE_ID", "price_premium"),
            "features": ["无限次数据查询", "实时数据更新", "高级数据分析", "自定义报表", "API访问权限"]
        }
    }

    st.subheader("订阅计划")
    st.markdown(f"### {plans['premium']['name']}")
    st.markdown(f"¥{plans['premium']['price']}（一次性支付，1个月）")
    for feature in plans['premium']['features']:
        st.markdown(f"- {feature}")

    if 'user_email' in st.session_state:
        if st.button("选择高级版", key="premium"):
            logging.info("Button '选择高级版' clicked")
            session = create_checkout_session(
                plans['premium']['price_id'],
                st.session_state['user_email']
            )
            if session:
                st.success("支付会话创建成功！")
                st.write(f"支付链接: {session.url}")
                st.markdown(f'<a href="{session.url}" target="_blank">点击此处前往支付页面</a>', unsafe_allow_html=True)
    else:
        st.warning("请先登录")
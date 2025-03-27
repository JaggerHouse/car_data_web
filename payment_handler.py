import stripe
import streamlit as st
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def init_stripe():
    logging.info("Initializing Stripe configuration")
    return {
        "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY"),
        "secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET")
    }

def create_checkout_session(price_id: str, user_email: str):
    try:
        logging.info(f"Creating checkout session for {user_email} with price_id: {price_id}")
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'alipay', 'wechat_pay'],
            line_items=[{
                'price_data': {
                    'currency': 'cny',
                    'unit_amount': 29900,  # 299元，单位为分
                    'product_data': {
                        'name': '高级版订阅',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',  # 改为单次支付
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
    query_params = st.query_params
    if "success" in query_params and query_params["success"] == "true":
        logging.info(f"User {user_email} upgraded to premium")
        return "premium"
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
    st.markdown(f"¥{plans['premium']['price']}（一次性支付）")
    for feature in plans['premium']['features']:
        st.markdown(f"- {feature}")

    if 'user_email' in st.session_state:
        st.write(f"调试：当前用户邮箱 - {st.session_state['user_email']}")
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
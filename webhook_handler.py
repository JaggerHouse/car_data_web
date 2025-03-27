import stripe
from flask import Flask, request, jsonify
import logging
from datetime import datetime
from models import User, get_db_session
from dotenv import load_dotenv
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# 加载环境变量
load_dotenv()

# 初始化Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

@app.route('/webhook', methods=['POST'])
def webhook():
    # 获取webhook secret
    if not webhook_secret:
        logging.error("Webhook secret not configured")
        return jsonify({'error': 'Webhook secret not configured'}), 500
    
    # 获取请求数据
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # 验证webhook签名
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        logging.error(f"无效的payload: {e}")
        return jsonify({'error': '无效的payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"签名验证失败: {e}")
        return jsonify({'error': '签名验证失败'}), 400
    
    # 处理事件
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_email')
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        
        # 获取数据库会话
        db_session = get_db_session()
        try:
            # 查找用户
            user = db_session.query(User).filter_by(email=customer_email).first()
            if not user:
                logging.error(f"找不到用户: {customer_email}")
                return jsonify({'error': '找不到用户'}), 404
            
            # 获取订阅详情
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # 更新用户订阅信息
            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = subscription_id
            user.subscription_status = 'premium' if subscription.plan.amount >= 19900 else 'basic'
            user.subscription_end_date = datetime.fromtimestamp(subscription.current_period_end)
            
            # 提交更改
            db_session.commit()
            logging.info(f"用户 {customer_email} 订阅更新成功")
            
        except Exception as e:
            db_session.rollback()
            logging.error(f"更新用户订阅失败: {str(e)}")
            return jsonify({'error': '更新用户订阅失败'}), 500
        finally:
            db_session.close()
        
        logging.info(f"支付成功！客户邮箱: {customer_email}, 订阅ID: {subscription_id}")
        
        # 获取订阅详情
        subscription = stripe.Subscription.retrieve(subscription_id)
        plan_id = subscription.plan.id
        
        # 确定订阅类型
        subscription_type = 'basic' if 'basic' in plan_id.lower() else 'premium'
        
        # 更新数据库中的用户订阅状态
        db_session = get_db_session()
        try:
            user = db_session.query(User).filter_by(email=customer_email).first()
            if user:
                user.subscription_status = subscription_type
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = subscription_id
                user.subscription_end_date = datetime.utcfromtimestamp(subscription.current_period_end)
                db_session.commit()
                logging.info(f"用户订阅状态已更新: {customer_email} -> {subscription_type}")
            else:
                logging.error(f"未找到用户: {customer_email}")
        except Exception as e:
            logging.error(f"更新用户订阅状态失败: {str(e)}")
            db_session.rollback()
        finally:
            db_session.close()
        
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'received'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
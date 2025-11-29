import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, 
    Filters, CallbackContext, CallbackQueryHandler
)
from database import Database
from config import BOT_TOKEN, ADMIN_IDS
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

class PaymentBot:
    def __init__(self):
        self.db = Database()
        self.updater = Updater(token=BOT_TOKEN, use_context=True)
        self.setup_handlers()
    
    def setup_handlers(self):
        dp = self.updater.dispatcher
        
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help_command))
        dp.add_handler(CommandHandler("my_payments", self.my_payments))
        dp.add_handler(CommandHandler("admin", self.admin_panel))
        dp.add_handler(CommandHandler("send_reminders", self.send_reminders))
        dp.add_handler(CommandHandler("force_all", self.force_send_all))
        dp.add_handler(CommandHandler("create_payments", self.create_payments))
        dp.add_handler(CommandHandler("stats", self.stats))
        
        dp.add_handler(CallbackQueryHandler(self.button_handler, pattern="^payment_"))
        dp.add_handler(CallbackQueryHandler(self.button_handler, pattern="^receipt_"))
    
    def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        parent = self.db.get_parent_by_chat_id(chat_id)
        
        if parent:
            welcome_text = f'''Привет, {parent.first_name}! 👋

Я бот для напоминаний об оплате занятий.

Ваши данные:
👤 Имя: {parent.first_name}
👶 Ребенок: {parent.child_name}
🏫 Школа: {parent.grade.school.name}
📚 Класс: {parent.grade.grade_name}
💳 Сумма оплаты: {parent.grade.monthly_payment} руб./мес
📞 Телефон: {parent.phone_number or 'не указан'}'''
        else:
            welcome_text = f'''Привет, {user.first_name}! 👋

Я бот для напоминаний об оплате занятий.'''
        
        update.message.reply_text(welcome_text)
    
    def help_command(self, update: Update, context: CallbackContext):
        help_text = '''📋 Команды бота:

/start - начать работу
/admin - панель администратора
/send_reminders - отправить напоминания (авто)
/force_all - принудительно отправить ВСЕМ
/create_payments - создать платежи
/stats - статистика
/my_payments - мои платежи'''
        update.message.reply_text(help_text)
    
    def admin_panel(self, update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        parents = self.db.get_all_active_parents()
        unpaid_payments = self.db.get_unpaid_payments()
        schools = self.db.get_schools()
        
        stats_text = f'''🛠 Панель администратора

📊 Статистика:
🏫 Школ: {len(schools)}
👥 Родителей: {len(parents)}
💰 Неоплаченных платежей: {len(unpaid_payments)}

Команды:
/send_reminders - авто-напоминания
/force_all - принудительно ВСЕМ
/create_payments - создать платежи
/stats - подробная статистика'''
        
        update.message.reply_text(stats_text)
    
    def send_reminders(self, update: Update, context: CallbackContext):
        """Автоматические напоминания (по условиям)"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        update.message.reply_text('📤 Отправляю напоминания...')
        sent_count = self.send_payment_reminders(context)
        update.message.reply_text(f'✅ Напоминания отправлены! Получили: {sent_count} человек')
    
    def force_send_all(self, update: Update, context: CallbackContext):
        """ПРИНУДИТЕЛЬНАЯ отправка ВСЕМ родителям"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        update.message.reply_text('🔄 Принудительно отправляю напоминания ВСЕМ родителям...')
        
        parents = self.db.get_parents_with_chat_id()
        sent_count = 0
        
        for parent in parents:
            try:
                # Находим неоплаченный платеж для этого родителя
                unpaid_payments = self.db.get_unpaid_payments()
                current_payment = None
                
                for payment in unpaid_payments:
                    if payment.parent_id == parent.id:
                        current_payment = payment
                        break
                
                if current_payment:
                    message_text = f'''💳 Напоминание об оплате

Уважаемый(ая) {parent.first_name}!

Напоминаем об оплате занятий за {current_payment.month}:
🏫 {parent.grade.school.name}
📚 {parent.grade.grade_name} класс
👶 {parent.child_name}
💳 Сумма: {current_payment.amount} руб.
📅 Срок оплаты: {current_payment.due_date.strftime('%d.%m.%Y')}

После оплаты нажмите кнопку \"✅ Оплатил\".'''
                    
                    keyboard = [[InlineKeyboardButton('✅ Оплатил', callback_data=f'payment_{current_payment.id}')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    context.bot.send_message(
                        chat_id=parent.chat_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                    print(f'✅ Отправлено {parent.first_name} (chat_id: {parent.chat_id})')
                    
            except Exception as e:
                print(f'❌ Ошибка отправки {parent.chat_id}: {e}')
        
        update.message.reply_text(f'✅ Принудительно отправлено: {sent_count} человек')
    
    def send_payment_reminders(self, context: CallbackContext):
        payments_to_remind = self.db.get_payments_for_reminder()
        sent_count = 0
        
        for payment in payments_to_remind:
            if payment.parent.chat_id:
                try:
                    message_text = f'''💳 Напоминание об оплате

Уважаемый(ая) {payment.parent.first_name}!

Напоминаем об оплате занятий за {payment.month}:
🏫 {payment.parent.grade.school.name}
📚 {payment.parent.grade.grade_name} класс
👶 {payment.parent.child_name}
💳 Сумма: {payment.amount} руб.'''
                    
                    keyboard = [[InlineKeyboardButton('✅ Оплатил', callback_data=f'payment_{payment.id}')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    context.bot.send_message(
                        chat_id=payment.parent.chat_id,
                        text=message_text,
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f'Ошибка отправки: {e}')
        
        return sent_count
    
    def create_payments(self, update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        next_month = (datetime.now() + timedelta(days=32)).strftime('%Y-%m')
        update.message.reply_text(f'📅 Создаю платежи на {next_month}...')
        created_count = self.db.create_monthly_payments(next_month)
        update.message.reply_text(f'✅ Создано {created_count} платежей на {next_month}')
    
    def stats(self, update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        parents = self.db.get_all_active_parents()
        unpaid_payments = self.db.get_unpaid_payments()
        
        stats_text = f'📊 Статистика\n👥 Родителей: {len(parents)}\n💰 Неоплаченных платежей: {len(unpaid_payments)}'
        update.message.reply_text(stats_text)
    
    def my_payments(self, update: Update, context: CallbackContext):
        update.message.reply_text('💳 Ваши платежи будут здесь')
    
    def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()
        query.edit_message_text('✅ Обработано!')
    
    def run(self):
        print('🚀 Бот запущен! Команды:')
        print('   /send_reminders - авто-напоминания')
        print('   /force_all - принудительно ВСЕМ')
        self.updater.start_polling()
        self.updater.idle()

if __name__ == '__main__':
    bot = PaymentBot()
    bot.run()

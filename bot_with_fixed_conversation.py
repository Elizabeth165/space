import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, 
    Filters, CallbackContext, CallbackQueryHandler,
    ConversationHandler
)
from database import Database
from config import BOT_TOKEN, ADMIN_IDS
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Состояния для добавления родителя
ADD_NAME, ADD_CHILD, ADD_SCHOOL, ADD_GRADE, ADD_PHONE, ADD_CHAT_ID = range(6)

class PaymentBot:
    def __init__(self):
        self.db = Database()
        self.updater = Updater(token=BOT_TOKEN, use_context=True)
        self.setup_handlers()
    
    def setup_handlers(self):
        dp = self.updater.dispatcher
        
        # Основные команды
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help_command))
        dp.add_handler(CommandHandler("my_payments", self.my_payments))
        dp.add_handler(CommandHandler("admin", self.admin_panel))
        dp.add_handler(CommandHandler("send_reminders", self.send_reminders))
        dp.add_handler(CommandHandler("force_all", self.force_send_all))
        dp.add_handler(CommandHandler("create_payments", self.create_payments))
        dp.add_handler(CommandHandler("stats", self.stats))
        dp.add_handler(CommandHandler("paid_list", self.show_paid_list))
        dp.add_handler(CommandHandler("unpaid_list", self.show_unpaid_list))
        
        # Обработчики inline кнопок
        dp.add_handler(CallbackQueryHandler(self.button_handler, pattern="^payment_"))
        dp.add_handler(CallbackQueryHandler(self.button_handler, pattern="^receipt_"))
        
        # Обработчики текстовых сообщений для кнопок
        dp.add_handler(MessageHandler(Filters.text("👥 Добавить родителя"), self.add_parent_start))
        dp.add_handler(MessageHandler(Filters.text("📊 Статистика"), self.show_stats))
        dp.add_handler(MessageHandler(Filters.text("💳 Создать платежи"), self.create_payments_button))
        dp.add_handler(MessageHandler(Filters.text("📤 Отправить напоминания"), self.send_reminders_button))
        dp.add_handler(MessageHandler(Filters.text("🔄 Принудительно всем"), self.force_all_button))
        dp.add_handler(MessageHandler(Filters.text("📋 Список родителей"), self.show_parents_list))
        dp.add_handler(MessageHandler(Filters.text("✅ Оплатившие"), self.show_paid_list_button))
        dp.add_handler(MessageHandler(Filters.text("📝 Неоплатившие"), self.show_unpaid_list))
        
        # ConversationHandler для добавления родителя
        add_parent_conv = ConversationHandler(
            entry_points=[
                CommandHandler('add_parent', self.add_parent_start),
                MessageHandler(Filters.text("👥 Добавить родителя"), self.add_parent_start)
            ],
            states={
                ADD_NAME: [MessageHandler(Filters.text & ~Filters.command, self.add_parent_name)],
                ADD_CHILD: [MessageHandler(Filters.text & ~Filters.command, self.add_parent_child)],
                ADD_SCHOOL: [MessageHandler(Filters.text & ~Filters.command, self.add_parent_school)],
                ADD_GRADE: [MessageHandler(Filters.text & ~Filters.command, self.add_parent_grade)],
                ADD_PHONE: [
                    MessageHandler(Filters.text & ~Filters.command, self.add_parent_phone),
                    MessageHandler(Filters.contact, self.add_parent_phone_contact)
                ],
                ADD_CHAT_ID: [MessageHandler(Filters.text & ~Filters.command, self.add_parent_chat_id)],
            },
            fallbacks=[CommandHandler('cancel', self.add_parent_cancel)],
        )
        
        dp.add_handler(add_parent_conv)
    
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

Я бот для напоминаний об оплате занятий.

Если вы должны получать уведомления об оплате, но не получаете их, 
свяжитесь с администратором.'''
        
        # Для админов показываем кнопки
        if chat_id in ADMIN_IDS:
            keyboard = [
                ['👥 Добавить родителя', '📊 Статистика'],
                ['💳 Создать платежи', '📤 Отправить напоминания'],
                ['🔄 Принудительно всем', '📋 Список родителей'],
                ['✅ Оплатившие', '📝 Неоплатившие']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            update.message.reply_text(welcome_text, reply_markup=reply_markup)
        else:
            update.message.reply_text(welcome_text)
    
    def admin_panel(self, update: Update, context: CallbackContext):
        """Панель администратора с кнопками"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        parents = self.db.get_all_active_parents()
        unpaid_payments = self.db.get_unpaid_payments()
        schools = self.db.get_schools()
        
        # Создаем клавиатуру с кнопками
        keyboard = [
            ['👥 Добавить родителя', '📊 Статистика'],
            ['💳 Создать платежи', '📤 Отправить напоминания'],
            ['🔄 Принудительно всем', '📋 Список родителей'],
            ['✅ Оплатившие', '📝 Неоплатившие']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        stats_text = f'''🛠 Панель администратора

📊 Статистика:
🏫 Школ: {len(schools)}
👥 Родителей: {len(parents)}
💰 Неоплаченных платежей: {len(unpaid_payments)}

Выберите действие:'''
        
        update.message.reply_text(stats_text, reply_markup=reply_markup)
    
    # ========== ФУНКЦИИ ДЛЯ ОПЛАТИВШИХ ==========
    
    def show_paid_list(self, update: Update, context: CallbackContext):
        """Показать список оплативших родителей"""
        self._show_paid_list(update, context)
    
    def show_paid_list_button(self, update: Update, context: CallbackContext):
        """Обработчик кнопки Оплатившие"""
        self._show_paid_list(update, context)
    
    def show_unpaid_list(self, update: Update, context: CallbackContext):
        """Показать список неоплативших родителей"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        # Получаем все платежи
        all_payments = self.db.get_unpaid_payments()  # Этот метод возвращает ВСЕ платежи, фильтруем неоплаченные
        
        # Фильтруем только неоплаченные
        unpaid_payments = [p for p in all_payments if not p.is_paid]
        
        if not unpaid_payments:
            update.message.reply_text('🎉 Все родители оплатили! Неоплативших нет.')
            return
        
        current_month = datetime.now().strftime('%Y-%m')
        unpaid_this_month = [p for p in unpaid_payments if p.month == current_month]
        
        if not unpaid_this_month:
            update.message.reply_text(f'📝 На {current_month} неоплативших нет.')
            return
        
        unpaid_text = f'📝 Неоплатившие за {current_month}:\n\n'
        
        for i, payment in enumerate(unpaid_this_month, 1):
            parent = payment.parent
            grade = self.db.get_grade(parent.grade_id)
            
            unpaid_text += f'''{i}. {parent.first_name}
   👶 {parent.child_name}
   🏫 {grade.school.name}, {grade.grade_name}
   💳 {payment.amount} руб.
   📞 {parent.phone_number or 'нет телефона'}
   
'''
        
        if len(unpaid_text) > 4000:
            parts = [unpaid_text[i:i+4000] for i in range(0, len(unpaid_text), 4000)]
            for part in parts:
                update.message.reply_text(part)
        else:
            update.message.reply_text(unpaid_text)
    
    def _show_paid_list(self, update: Update, context: CallbackContext):
        """Внутренняя функция для показа оплативших"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        # Получаем все платежи
        all_payments = self.db.get_unpaid_payments()  # Этот метод возвращает ВСЕ платежи
        
        # Фильтруем оплаченные
        paid_payments = [p for p in all_payments if p.is_paid]
        
        if not paid_payments:
            update.message.reply_text('💰 Оплативших пока нет.')
            return
        
        # Группируем по месяцам
        paid_by_month = {}
        for payment in paid_payments:
            if payment.month not in paid_by_month:
                paid_by_month[payment.month] = []
            paid_by_month[payment.month].append(payment)
        
        result_text = '✅ Список оплативших:\n\n'
        
        for month in sorted(paid_by_month.keys(), reverse=True):
            result_text += f'📅 {month}:\n'
            
            for i, payment in enumerate(paid_by_month[month], 1):
                parent = payment.parent
                grade = self.db.get_grade(parent.grade_id)
                
                payment_date = payment.payment_date.strftime('%d.%m.%Y %H:%M') if payment.payment_date else 'дата не указана'
                receipt_status = '✅ чек отправлен' if payment.is_receipt_sent else '❌ чек не отправлен'
                
                result_text += f'''{i}. {parent.first_name}
   👶 {parent.child_name}
   🏫 {grade.school.name}, {grade.grade_name}
   💳 {payment.amount} руб.
   🕒 {payment_date}
   📄 {receipt_status}
   
'''
            
            result_text += '\n'
        
        # Добавляем статистику
        total_paid = len(paid_payments)
        total_with_receipt = len([p for p in paid_payments if p.is_receipt_sent])
        
        result_text += f'📊 Итого:\n'
        result_text += f'• Всего оплат: {total_paid}\n'
        result_text += f'• С чеками: {total_with_receipt}\n'
        result_text += f'• Без чеков: {total_paid - total_with_receipt}'
        
        if len(result_text) > 4000:
            parts = [result_text[i:i+4000] for i in range(0, len(result_text), 4000)]
            for part in parts:
                update.message.reply_text(part)
        else:
            update.message.reply_text(result_text)
    
    # ========== ОБРАБОТЧИКИ КНОПОК ==========
    
    def show_stats(self, update: Update, context: CallbackContext):
        """Обработчик кнопки Статистика"""
        self.stats(update, context)
    
    def create_payments_button(self, update: Update, context: CallbackContext):
        """Обработчик кнопки Создать платежи"""
        self.create_payments(update, context)
    
    def send_reminders_button(self, update: Update, context: CallbackContext):
        """Обработчик кнопки Отправить напоминания"""
        self.send_reminders(update, context)
    
    def force_all_button(self, update: Update, context: CallbackContext):
        """Обработчик кнопки Принудительно всем"""
        self.force_send_all(update, context)
    
    def show_parents_list(self, update: Update, context: CallbackContext):
        """Показать список всех родителей"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        parents = self.db.get_all_active_parents()
        
        if not parents:
            update.message.reply_text('📋 Список родителей пуст')
            return
        
        parents_text = '📋 Список всех родителей:\n\n'
        
        for i, parent in enumerate(parents, 1):
            grade = self.db.get_grade(parent.grade_id)
            chat_status = '✅' if parent.chat_id else '❌'
            parents_text += f'''{i}. {parent.first_name}
   👶 {parent.child_name}
   🏫 {grade.school.name}, {grade.grade_name}
   📞 {parent.phone_number or 'не указан'}
   🆔 Chat ID: {chat_status} {parent.chat_id or 'не указан'}
   
'''
        
        # Разбиваем на части если слишком длинное сообщение
        if len(parents_text) > 4000:
            parts = [parents_text[i:i+4000] for i in range(0, len(parents_text), 4000)]
            for part in parts:
                update.message.reply_text(part)
        else:
            update.message.reply_text(parents_text)
    
    # ========== ФУНКЦИИ ДОБАВЛЕНИЯ РОДИТЕЛЯ ==========
    
    def add_parent_start(self, update: Update, context: CallbackContext):
        """Начало процесса добавления родителя"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return ConversationHandler.END
        
        # Сбрасываем данные
        context.user_data.clear()
        
        # Убираем клавиатуру для удобства ввода
        remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
        
        update.message.reply_text(
            '👥 Добавление нового родителя\n\n'
            'Введите имя и фамилию родителя:',
            reply_markup=remove_keyboard
        )
        return ADD_NAME
    
    def add_parent_name(self, update: Update, context: CallbackContext):
        """Обработка имени родителя"""
        name = update.message.text.strip()
        if not name:
            update.message.reply_text('❌ Имя не может быть пустым. Введите имя и фамилию родителя:')
            return ADD_NAME
        
        context.user_data['parent_name'] = name
        
        update.message.reply_text('Введите имя ребенка:')
        return ADD_CHILD
    
    def add_parent_child(self, update: Update, context: CallbackContext):
        """Обработка имени ребенка"""
        child_name = update.message.text.strip()
        if not child_name:
            update.message.reply_text('❌ Имя ребенка не может быть пустым. Введите имя ребенка:')
            return ADD_CHILD
        
        context.user_data['child_name'] = child_name
        
        # Получаем список школ
        schools = self.db.get_schools()
        if not schools:
            update.message.reply_text('❌ В системе нет школ. Сначала добавьте школы через базу данных.')
            return ConversationHandler.END
        
        # Создаем клавиатуру со школами
        keyboard = [[school.name] for school in schools]
        keyboard.append(['❌ Отменить'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        school_list = '\n'.join([f'{i+1}. {school.name}' for i, school in enumerate(schools)])
        update.message.reply_text(
            f'Выберите школу:\n\n{school_list}',
            reply_markup=reply_markup
        )
        return ADD_SCHOOL
    
    def add_parent_school(self, update: Update, context: CallbackContext):
        """Обработка выбора школы"""
        school_name = update.message.text
        
        if school_name == '❌ Отменить':
            return self.add_parent_cancel(update, context)
        
        schools = self.db.get_schools()
        
        # Находим выбранную школу
        selected_school = None
        for school in schools:
            if school.name == school_name:
                selected_school = school
                break
        
        if not selected_school:
            update.message.reply_text('❌ Школа не найдена. Попробуйте еще раз:')
            return ADD_SCHOOL
        
        context.user_data['school_id'] = selected_school.id
        context.user_data['school_name'] = selected_school.name
        
        # Получаем классы для выбранной школы
        grades = self.db.get_grades_by_school(selected_school.id)
        if not grades:
            update.message.reply_text('❌ В этой школе нет классов.')
            return ConversationHandler.END
        
        # Создаем клавиатуру с классами
        keyboard = [[f"{grade.grade_name} ({grade.monthly_payment} руб.)"] for grade in grades]
        keyboard.append(['❌ Отменить'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        grade_list = '\n'.join([f'{i+1}. {grade.grade_name} - {grade.monthly_payment} руб.' for i, grade in enumerate(grades)])
        update.message.reply_text(
            f'Выберите класс в школе "{selected_school.name}":\n\n{grade_list}',
            reply_markup=reply_markup
        )
        return ADD_GRADE
    
    def add_parent_grade(self, update: Update, context: CallbackContext):
        """Обработка выбора класса"""
        grade_text = update.message.text
        
        if grade_text == '❌ Отменить':
            return self.add_parent_cancel(update, context)
        
        school_id = context.user_data['school_id']
        
        # Извлекаем название класса из текста
        grade_name = grade_text.split(' (')[0]
        
        grades = self.db.get_grades_by_school(school_id)
        
        # Находим выбранный класс
        selected_grade = None
        for grade in grades:
            if grade.grade_name == grade_name:
                selected_grade = grade
                break
        
        if not selected_grade:
            update.message.reply_text('❌ Класс не найден. Попробуйте еще раз:')
            return ADD_GRADE
        
        context.user_data['grade_id'] = selected_grade.id
        context.user_data['grade_name'] = selected_grade.grade_name
        context.user_data['monthly_payment'] = selected_grade.monthly_payment
        
        # Предлагаем поделиться номером телефона
        keyboard = [
            [KeyboardButton("📞 Поделиться номером", request_contact=True)],
            ['Пропустить', '❌ Отменить']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            'Отправьте номер телефона родителя:\n\n'
            'Можно:\n'
            '• Нажать кнопку "📞 Поделиться номером"\n'
            '• Ввести номер вручную\n'
            '• Написать "Пропустить" чтобы не указывать телефон',
            reply_markup=reply_markup
        )
        return ADD_PHONE
    
    def add_parent_phone(self, update: Update, context: CallbackContext):
        """Обработка номера телефона из текста"""
        phone_text = update.message.text
        
        if phone_text == '❌ Отменить':
            return self.add_parent_cancel(update, context)
        elif phone_text.lower() == 'пропустить':
            context.user_data['phone'] = None
        else:
            # Простая валидация номера телефона
            phone = phone_text.strip()
            if not any(char.isdigit() for char in phone):
                update.message.reply_text('❌ Номер телефона должен содержать цифры. Введите снова:')
                return ADD_PHONE
            context.user_data['phone'] = phone
        
        return self.ask_chat_id(update, context)
    
    def add_parent_phone_contact(self, update: Update, context: CallbackContext):
        """Обработка номера телефона из контакта"""
        phone = update.message.contact.phone_number
        context.user_data['phone'] = phone
        return self.ask_chat_id(update, context)
    
    def ask_chat_id(self, update: Update, context: CallbackContext):
        """Запрос Chat ID"""
        keyboard = [['❌ Отменить']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        update.message.reply_text(
            'Введите Chat ID родителя (цифры):\n\n'
            '💡 Chat ID можно узнать:\n'
            '• Через бота @userinfobot\n'
            '• Или родитель пишет /start нашему боту\n\n'
            'Введите цифры:',
            reply_markup=reply_markup
        )
        return ADD_CHAT_ID
    
    def add_parent_chat_id(self, update: Update, context: CallbackContext):
        """Обработка chat_id и сохранение родителя"""
        chat_id_text = update.message.text
        
        if chat_id_text == '❌ Отменить':
            return self.add_parent_cancel(update, context)
        
        try:
            chat_id = int(chat_id_text)
        except ValueError:
            update.message.reply_text('❌ Chat ID должен быть числом. Введите снова:')
            return ADD_CHAT_ID
        
        # Сохраняем родителя в базу
        try:
            parent = self.db.add_parent(
                first_name=context.user_data['parent_name'],
                child_name=context.user_data['child_name'],
                grade_id=context.user_data['grade_id'],
                phone_number=context.user_data['phone'],
                chat_id=chat_id
            )
            
            success_text = f'''✅ Родитель успешно добавлен!

👤 Родитель: {parent.first_name}
👶 Ребенок: {parent.child_name}
🏫 Школа: {context.user_data['school_name']}
📚 Класс: {context.user_data['grade_name']}
💳 Сумма: {context.user_data['monthly_payment']} руб./мес
📞 Телефон: {parent.phone_number or 'не указан'}
🆔 Chat ID: {parent.chat_id}

Родитель будет получать напоминания об оплате.'''

            # Возвращаем основную клавиатуру
            keyboard = [
                ['👥 Добавить родителя', '📊 Статистика'],
                ['💳 Создать платежи', '📤 Отправить напоминания'],
                ['🔄 Принудительно всем', '📋 Список родителей'],
                ['✅ Оплатившие', '📝 Неоплатившие']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            update.message.reply_text(success_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка добавления родителя: {e}")
            update.message.reply_text(f'❌ Ошибка при добавлении: {e}')
        
        context.user_data.clear()
        return ConversationHandler.END
    
    def add_parent_cancel(self, update: Update, context: CallbackContext):
        """Отмена добавления родителя"""
        # Возвращаем основную клавиатуру
        keyboard = [
            ['👥 Добавить родителя', '📊 Статистика'],
            ['💳 Создать платежи', '📤 Отправить напоминания'],
            ['🔄 Принудительно всем', '📋 Список родителей'],
            ['✅ Оплатившие', '📝 Неоплатившие']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text('❌ Добавление родителя отменено.', reply_markup=reply_markup)
        context.user_data.clear()
        return ConversationHandler.END
    
    # ========== ФУНКЦИИ РАССЫЛКИ ==========
    
    def send_reminders(self, update: Update, context: CallbackContext):
        """Автоматическая рассылка напоминаний"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_IDS:
            update.message.reply_text('❌ Нет прав доступа')
            return
        
        update.message.reply_text('📤 Отправляю напоминания...')
        sent_count = self.send_payment_reminders(context)
        update.message.reply_text(f'✅ Напоминания отправлены! Получили: {sent_count} человек')
    
    def force_send_all(self, update: Update, context: CallbackContext):
        """ПРИНУДИТЕЛЬНАЯ рассылка ВСЕМ родителям"""
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

После оплаты нажмите кнопку "✅ Оплатил".'''
                    
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
        """Автоматическая отправка напоминаний по условиям"""
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
    
    # ========== ОСТАЛЬНЫЕ ФУНКЦИИ ==========
    
    def help_command(self, update: Update, context: CallbackContext):
        help_text = '''📋 Команды бота:

Для всех:
/start - начать работу
/my_payments - мои платежи

Для администратора:
/admin - панель управления
/add_parent - добавить родителя
/send_reminders - отправить напоминания
/force_all - принудительно всем
/create_payments - создать платежи
/stats - статистика
/paid_list - список оплативших
/unpaid_list - список неоплативших'''
        update.message.reply_text(help_text)
    
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
        schools = self.db.get_schools()
        
        # Считаем оплативших
        all_payments = self.db.get_unpaid_payments()  # Все платежи
        paid_payments = [p for p in all_payments if p.is_paid]
        current_month = datetime.now().strftime('%Y-%m')
        paid_this_month = [p for p in paid_payments if p.month == current_month]
        
        stats_text = f'''📊 Подробная статистика

🏫 Школ: {len(schools)}
👥 Родителей: {len(parents)}
💰 Неоплаченных платежей: {len(unpaid_payments)}

📅 За {current_month}:
✅ Оплатили: {len(paid_this_month)}
❌ Не оплатили: {len([p for p in unpaid_payments if p.month == current_month])}

Всего оплат: {len(paid_payments)}
С чеками: {len([p for p in paid_payments if p.is_receipt_sent])}'''
        
        update.message.reply_text(stats_text)
    
    def my_payments(self, update: Update, context: CallbackContext):
        update.message.reply_text('💳 Ваши платежи будут здесь')
    
    def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        query.answer()
        query.edit_message_text('✅ Обработано!')
    
    def run(self):
        print('🚀 Бот запущен с расширенными функциями!')
        print('✨ Новые возможности:')
        print('   • ✅ Список оплативших родителей')
        print('   • 📝 Список неоплативших')
        print('   • 👥 Добавление родителей через бота')
        print('   • 📤 Принудительная рассылка всем')
        print('   • 📋 Просмотр списка родителей')
        print('   • 📊 Подробная статистика')
        print('   • 💳 Создание платежей')
        print('\n📝 Используйте /admin для доступа к панели управления')
        self.updater.start_polling()
        self.updater.idle()

if __name__ == '__main__':
    bot = PaymentBot()
    bot.run()

from database import Database
from datetime import datetime

def add_parent_manually():
    """Инструмент для ручного добавления родителей"""
    db = Database()
    
    # Показываем доступные школы
    schools = db.get_schools()
    print("\n🏫 Доступные школы:")
    for i, school in enumerate(schools, 1):
        print(f"{i}. {school.name}")
    
    school_choice = int(input("\nВыберите школу (номер): ")) - 1
    selected_school = schools[school_choice]
    
    # Показываем классы в выбранной школе
    grades = db.get_grades_by_school(selected_school.id)
    print(f"\n📚 Классы в {selected_school.name}:")
    for i, grade in enumerate(grades, 1):
        print(f"{i}. {grade.grade_name} ({grade.monthly_payment} руб./мес)")
    
    grade_choice = int(input("\nВыберите класс (номер): ")) - 1
    selected_grade = grades[grade_choice]
    
    # Вводим данные родителя
    print("\n👤 Введите данные родителя:")
    first_name = input("Имя: ")
    last_name = input("Фамилия (необязательно): ") or None
    child_name = input("Имя ребенка: ")
    phone_number = input("Телефон (необязательно): ") or None
    telegram_username = input("Username в Telegram (необязательно, без @): ") or None
    chat_id = input("Chat ID в Telegram (необязательно): ") or None
    
    if chat_id:
        chat_id = int(chat_id)
    
    # Добавляем родителя
    parent = db.add_parent(
        first_name=first_name,
        last_name=last_name,
        child_name=child_name,
        grade_id=selected_grade.id,
        phone_number=phone_number,
        telegram_username=telegram_username,
        chat_id=chat_id
    )
    
    print(f"\n✅ Родитель успешно добавлен!")
    print(f"ID: {parent.id}")
    print(f"Имя: {parent.first_name} {parent.last_name or ''}")
    print(f"Ребенок: {parent.child_name}")
    print(f"Школа: {selected_school.name}")
    print(f"Класс: {selected_grade.grade_name}")
    print(f"Сумма оплаты: {selected_grade.monthly_payment} руб./мес")

if __name__ == '__main__':
    add_parent_manually()